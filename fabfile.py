#!/usr/bin/python
# coding: utf-8

# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file.
# This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

#
# fabfile.py
#

#
# A Python fabric file for setting up and managing the AWS ECS POV-Ray worker demo.
# This file assumes python2 is installed on the system as the default.
#

# Imports
from fabric.api import local, quiet, env, run, put, cd
from ConfigParser import ConfigParser
import boto
import boto.s3
from boto.exception import BotoServerError
from zipfile import ZipFile, ZIP_DEFLATED
import os
import json
import time
from urllib2 import unquote
from cStringIO import StringIO

# Constants (User configurable), imported from config.py

from config import *

# Constants (Application specific)
BUCKET_POSTFIX = '-pov-ray-bucket'  # Gets put after the unix user ID to create the bucket name.
SSH_KEY_DIR = os.environ['HOME'] + '/.ssh'
SQS_QUEUE_NAME = APP_NAME + 'Queue'
LAMBDA_FUNCTION_NAME = 'ecs-worker-launcher'
LAMBDA_FUNCTION_DEPENDENCIES = 'async'
ECS_TASK_NAME = APP_NAME + 'Task'

# Constants (OS specific)
USER = os.environ['HOME'].split('/')[-1]
AWS_BUCKET = USER + BUCKET_POSTFIX
AWS_CONFIG_FILE_NAME = os.environ['HOME'] + '/.aws/config'

# Constants
AWS_CLI_STANDARD_OPTIONS = (
    '    --region ' + AWS_REGION +
    '    --profile ' + AWS_PROFILE +
    '    --output json'
)

SSH_USER = 'ec2-user'
CPU_SHARES = 512  # POV-Ray needs at least half a CPU to work nicely.
MEMORY = 512
ZIPFILE_NAME = LAMBDA_FUNCTION_NAME + '.zip'

BUCKET_PERMISSION_SID = APP_NAME + 'Permission'
WAIT_TIME = 5  # seconds to allow for eventual consistency to kick in.
RETRIES = 5  # Number of retries before we give up on something.

# Templates and embedded scripts

LAMBDA_EXECUTION_ROLE_NAME = APP_NAME + '-Lambda-Execution-Role'
LAMBDA_EXECUTION_ROLE_POLICY_NAME = 'AWSLambdaExecutionPolicy'
LAMBDA_EXECUTION_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:*",
                "sqs:SendMessage",
                "ecs:RunTask"
            ],
            "Resource": [
                "arn:aws:logs:*:*:*",
                "arn:aws:sqs:*:*:*",
                "arn:aws:ecs:*:*:*"
            ]
        }
    ]
}

LAMBDA_EXECUTION_ROLE_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

LAMBDA_FUNCTION_CONFIG = {
    "s3_key_suffix_whitelist": ['.zip'],  # Only S3 keys with this URL will be accepted.
    "queue": '',  # To be filled in with the queue ARN.
    "task": ECS_TASK_NAME
}

LAMBDA_FUNCTION_CONFIG_PATH = './' + LAMBDA_FUNCTION_NAME + '/config.json'

BUCKET_NOTIFICATION_CONFIGURATION = {
    "LambdaFunctionConfigurations": [
        {
            "Id": APP_NAME,
            "LambdaFunctionArn": "",
            "Events": [
                "s3:ObjectCreated:*"
            ]
        }
    ]
}

ECS_ROLE_BUCKET_ACCESS_POLICY_NAME = APP_NAME + "BucketAccessPolicy"
ECS_ROLE_BUCKET_ACCESS_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListAllMyBuckets"
            ],
            "Resource": "arn:aws:s3:::*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": ""  # To be filled in by a function below.
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": ""  # To be filled in by a function below.
        }
    ]
}

WORKER_PATH = 'ecs-worker'
WORKER_FILE = 'ecs-worker.sh'

DOCKERFILE = """
# POV-Ray Amazon ECS Worker

FROM ubuntu:14.04

MAINTAINER %(name)s

# Libraries and dependencies

RUN \
  apt-get update && apt-get -y install \
  autoconf \
  build-essential \
  git \
  libboost-thread-dev \
  libjpeg-dev \
  libpng-dev \
  libtiff-dev \
  python \
  python-dev \
  python-distribute \
  python-pip \
  unzip \
  zlib1g-dev

# Compile and install POV-Ray

RUN \
  mkdir /src && \
  cd /src && \
  git clone https://github.com/POV-Ray/povray.git && \
  cd povray/unix && \
  ./prebuild.sh && \
  cd .. && \
  ./configure COMPILED_BY="%(name)s" && \
  make && \
  make install

# Install AWS CLI

RUN \
  pip install awscli

WORKDIR /

COPY %(worker_file)s /

CMD [ "./%(worker_file)s" ]
"""

TASK_DEFINITION = {
    "family": APP_NAME,
    "containerDefinitions": [
        {
            "environment": [
                {
                    "name": "AWS_REGION",
                    "value": AWS_REGION
                }
            ],
            "name": APP_NAME,
            "image": DOCKERHUB_TAG,
            "cpu": CPU_SHARES,
            "memory": MEMORY,
            "essential": True
        }
    ]
}

POV_RAY_SCENE_NAME = 'ECSLogo'
POV_RAY_SCENE_FILE = POV_RAY_SCENE_NAME + '.zip'
POV_RAY_SCENE_FILES = [
    'AWS_Logo_PoweredBy_300px.png',
    'ECSLogo.ini',
    'ECSLogo.pov'
]

# Functions


# Dependencies and credentials.


def update_dependencies():
    local('pip2 install -r requirements.txt')
    local('cd ' + LAMBDA_FUNCTION_NAME + '; npm install ' + LAMBDA_FUNCTION_DEPENDENCIES)


def get_aws_credentials():
    config = ConfigParser()
    config.read(AWS_CONFIG_FILE_NAME)
    return config.get(AWS_PROFILE, 'aws_access_key_id'), config.get(AWS_PROFILE, 'aws_secret_access_key')

# AWS IAM


def get_iam_connection():
    aws_access_key_id, aws_secret_access_key = get_aws_credentials()
    return boto.connect_iam(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

# AWS Lambda


def dump_lambda_function_configuration():
    print('Writing config for Lambda function...')
    lambda_function_config = LAMBDA_FUNCTION_CONFIG.copy()
    lambda_function_config['queue'] = get_queue_url()
    with open(LAMBDA_FUNCTION_CONFIG_PATH, 'w') as fp:
        fp.write(json.dumps(lambda_function_config))


def create_lambda_deployment_package():
    print('Creating ZIP file: ' + ZIPFILE_NAME + '...')
    with ZipFile(ZIPFILE_NAME, 'w', ZIP_DEFLATED) as z:
        saved_dir = os.getcwd()
        os.chdir(LAMBDA_FUNCTION_NAME)
        for root, dirs, files in os.walk('.'):
            for basename in files:
                filename = os.path.join(root, basename)
                print('Adding: ' + filename + '...')
                z.write(filename)
        os.chdir(saved_dir)
        z.close()


def get_or_create_lambda_execution_role():
    iam = get_iam_connection()
    target_policy = json.dumps(LAMBDA_EXECUTION_ROLE_TRUST_POLICY, sort_keys=True)

    try:
        result = iam.get_role(LAMBDA_EXECUTION_ROLE_NAME)
        print('Found role: ' + LAMBDA_EXECUTION_ROLE_NAME + '.')

        policy = result['get_role_response']['get_role_result']['role']['assume_role_policy_document']
        if (
            policy is not None and
            json.dumps(json.loads(unquote(policy)), sort_keys=True) == target_policy
        ):
            print('Assume role policy for: ' + LAMBDA_EXECUTION_ROLE_NAME + ' verified.')
        else:
            print('Updating assume role policy for: ' + LAMBDA_EXECUTION_ROLE_NAME + '.')
            iam.update_assume_role_policy(LAMBDA_EXECUTION_ROLE_NAME, target_policy)
            time.sleep(WAIT_TIME)
    except BotoServerError:
        print('Creating role: ' + LAMBDA_EXECUTION_ROLE_NAME + '...')
        iam.create_role(
            LAMBDA_EXECUTION_ROLE_NAME,
            assume_role_policy_document=target_policy
        )
        result = iam.get_role(LAMBDA_EXECUTION_ROLE_NAME)

    role_arn = result['get_role_response']['get_role_result']['role']['arn']

    return role_arn


def check_lambda_execution_role_policies():
    iam = get_iam_connection()

    response = iam.list_role_policies(LAMBDA_EXECUTION_ROLE_NAME)
    policy_names = response['list_role_policies_response']['list_role_policies_result']['policy_names']

    found = False
    for p in policy_names:
        found = (p == LAMBDA_EXECUTION_ROLE_POLICY_NAME)
        if found:
            print('Found policy: ' + LAMBDA_EXECUTION_ROLE_POLICY_NAME + '.')
            break

    if not found:
        print('Attaching policy: ' + LAMBDA_EXECUTION_ROLE_POLICY_NAME + '.')
        iam.put_role_policy(
            LAMBDA_EXECUTION_ROLE_NAME,
            'AWSLambdaExecute',
            json.dumps(LAMBDA_EXECUTION_ROLE_POLICY)
        )

    return


def get_lambda_function_arn():
    result = json.loads(
        local(
            'aws lambda list-functions' +
            AWS_CLI_STANDARD_OPTIONS,
            capture=True
        )
    )
    if result is not None and isinstance(result, dict):
        for f in result.get('Functions', []):
            if f['FunctionName'] == LAMBDA_FUNCTION_NAME:
                return f['FunctionArn']

    return None


def delete_lambda_function():
    local(
        'aws lambda delete-function' +
        '    --function-name ' + LAMBDA_FUNCTION_NAME +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    )


def update_lambda_function():
    dump_lambda_function_configuration()
    create_lambda_deployment_package()
    role_arn = get_or_create_lambda_execution_role()
    check_lambda_execution_role_policies()

    if get_lambda_function_arn() is not None:
        print('Deleting existing Lambda function ' + LAMBDA_FUNCTION_NAME + '.')
        delete_lambda_function()

    local(
        'aws lambda create-function' +
        '    --function-name ' + LAMBDA_FUNCTION_NAME +
        '    --zip-file fileb://./' + ZIPFILE_NAME +
        '    --role ' + role_arn +
        '    --handler ' + LAMBDA_FUNCTION_NAME + '.handler' +
        '    --runtime nodejs' +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    )


def show_lambda_execution_role_policy():
    print json.dumps(LAMBDA_EXECUTION_ROLE_POLICY, sort_keys=True)


# Amazon S3


def get_s3_connection():
    aws_access_key_id, aws_secret_access_key = get_aws_credentials()
    return boto.s3.connect_to_region(
        AWS_REGION,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )


def get_or_create_bucket():
    s3 = get_s3_connection()
    b = s3.lookup(AWS_BUCKET)
    if b is None:
        print('Creating bucket: ' + AWS_BUCKET + ' in region: ' + AWS_REGION + '...')
        b = s3.create_bucket(AWS_BUCKET, location=AWS_REGION)
    else:
        print('Found bucket: ' + AWS_BUCKET + '.')

    return b


def check_bucket_permissions():
    with quiet():
        result = local(
            'aws lambda get-policy' +
            '    --function-name ' + LAMBDA_FUNCTION_NAME +
            AWS_CLI_STANDARD_OPTIONS,
            capture=True
        )

    if result.failed or result == '':
        return False

    result_decoded = json.loads(result)
    if not isinstance(result_decoded, dict):
        return False

    policy = json.loads(result_decoded.get('Policy', '{}'))
    if not isinstance(policy, dict):
        return False

    statements = policy.get('Statement', [])
    for s in statements:
        if s.get('Sid', '') == BUCKET_PERMISSION_SID:
            return True

    return False


def update_bucket_permissions():
    get_or_create_bucket()
    if check_bucket_permissions():
        print('Lambda invocation permission for bucket: ' + AWS_BUCKET + ' is set.')
    else:
        print('Setting Lambda invocation permission for bucket: ' + AWS_BUCKET + '.')
        local(
            'aws lambda add-permission' +
            '    --function-name ' + LAMBDA_FUNCTION_NAME +
            '    --region ' + AWS_REGION +
            '    --statement-id ' + BUCKET_PERMISSION_SID +
            '    --action "lambda:InvokeFunction"' +
            '    --principal s3.amazonaws.com' +
            '    --source-arn arn:aws:s3:::' + AWS_BUCKET +
            '    --profile ' + AWS_PROFILE,
            capture=True
        )


def check_bucket_notifications():
    result = local(
        'aws s3api get-bucket-notification-configuration' +
        '    --bucket ' + AWS_BUCKET +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    )

    if result.failed or result == '':
        return False

    result_decoded = json.loads(result)
    if not isinstance(result_decoded, dict):
        return False


def setup_bucket_notifications():
    update_lambda_function()
    update_bucket_permissions()

    notification_configuration = BUCKET_NOTIFICATION_CONFIGURATION.copy()
    lambda_function_arn = get_lambda_function_arn()
    notification_configuration['LambdaFunctionConfigurations'][0]['LambdaFunctionArn'] = lambda_function_arn

    if check_bucket_notifications():
        print('Bucket notification configuration for bucket: ' + AWS_BUCKET + ' is set.')
    else:
        print('Setting bucket notification configuration for bucket: ' + AWS_BUCKET + '.')
        local(
            'aws s3api put-bucket-notification-configuration' +
            '    --bucket ' + AWS_BUCKET +
            '    --notification-configuration \'' + json.dumps(notification_configuration, sort_keys=True) + '\'' +
            AWS_CLI_STANDARD_OPTIONS,
            capture=True
        )


# Amazon EC2

def get_instance_ip_from_id(instance_id):
    result = json.loads(local(
        'aws ec2 describe-instances' +
        '    --instance ' + instance_id +
        '    --query Reservations[0].Instances[0].PublicIpAddress' +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    ))
    print ('IP address for instance ' + instance_id + ' is: ' + result)
    return result


def get_instance_profile_name(instance_id):
    result = json.loads(local(
        'aws ec2 describe-instances' +
        '    --instance ' + instance_id +
        '    --query Reservations[0].Instances[0].IamInstanceProfile.Arn' +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    )).split('/')[-1]
    print('IAM instance profile for instance ' + instance_id + ' is: ' + result)
    return result


def get_instance_role(instance_id):
    profile = get_instance_profile_name(instance_id)
    result = json.loads(local(
        'aws iam get-instance-profile' +
        '    --instance-profile-name ' + profile +
        '    --query InstanceProfile.Roles[0].RoleName' +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    ))
    print('Role for instance ' + instance_id + ' is: ' + result)
    return result


# Amazon ECS


def get_container_instances():
    result = json.loads(local(
        'aws ecs list-container-instances' +
        '    --query containerInstanceArns' +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    ))
    print('Container instances: ' + ','.join(result))
    return result


def get_first_ecs_instance():
    container_instances = get_container_instances()

    result = json.loads(local(
        'aws ecs describe-container-instances' +
        '    --cluster ' + ECS_CLUSTER +
        '    --container-instances ' + container_instances[0] +
        '    --query containerInstances[0].ec2InstanceId' +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    ))
    print('First container instance: ' + result)
    return result


def get_first_ecs_instance_ip():
    i = get_first_ecs_instance()
    return get_instance_ip_from_id(i)


def prepare_env():
    env.host_string = get_first_ecs_instance_ip()
    env.user = SSH_USER
    env.key_filename = SSH_KEY_DIR + '/' + SSH_KEY_NAME


def generate_dockerfile():
    return DOCKERFILE % {'name': FULL_NAME_AND_EMAIL, 'worker_file': WORKER_FILE}


def show_dockerfile():
    print generate_dockerfile()


def update_ecs_image():
    prepare_env()
    run('mkdir -p ' + APP_NAME)

    dockerfile_string = generate_dockerfile()
    dockerfile = StringIO(dockerfile_string)
    put(dockerfile, remote_path='~/' + APP_NAME + '/Dockerfile', mode=0644)

    with open(os.path.join(WORKER_PATH, WORKER_FILE), "r") as fp:
        put(fp, remote_path='~/' + APP_NAME + '/' + WORKER_FILE, mode=0755)

    # Build the docker image and upload it to Dockerhub. This will prompt the user for their password.
    with cd('~/' + APP_NAME):
        run('docker build -t ' + DOCKERHUB_TAG + ' .')
        run('docker login -u ' + DOCKERHUB_USER + ' -e ' + DOCKERHUB_EMAIL)
        run('docker push ' + DOCKERHUB_TAG)

    # Cleanup.
    run('/bin/rm -rf ' + APP_NAME)


def generate_task_definition():
    task_definition = TASK_DEFINITION.copy()
    task_definition['containerDefinitions'][0]['environment'].append(
        {
            'name': 'SQS_QUEUE_URL',
            'value': get_queue_url()
        }
    )
    return task_definition


def show_task_definition():
    print json.dumps(generate_task_definition(), indent=4)


def update_ecs_task_definition():
    task_definition_string = json.dumps(generate_task_definition())

    local(
        'aws ecs register-task-definition' +
        '    --family ' + ECS_TASK_NAME +
        '    --cli-input-json \'' + task_definition_string + '\'' +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    )


def generate_ecs_role_policy():
    result = ECS_ROLE_BUCKET_ACCESS_POLICY.copy()
    result['Statement'][1]['Resource'] = 'arn:aws:s3:::' + AWS_BUCKET
    result['Statement'][2]['Resource'] = 'arn:aws:s3:::' + AWS_BUCKET + '/*'
    return result


def show_ecs_role_policy():
    policy = generate_ecs_role_policy()
    print json.dumps(policy, indent=4, sort_keys=True)


def check_ecs_role_policy():
    role = get_instance_role(get_first_ecs_instance())
    iam = get_iam_connection()

    policy = None
    # noinspection PyBroadException
    try:
        response = iam.get_role_policy(role, ECS_ROLE_BUCKET_ACCESS_POLICY_NAME)
        policy_raw = response['get_role_policy_response']['get_role_policy_result']['policy_document']
        policy = json.dumps(json.loads(unquote(policy_raw)), sort_keys=True)
    except Exception:
        pass

    if policy is None:
        print('ECS role policy ' + role + 'is missing.')
        return False
    else:
        target_policy = json.dumps(generate_ecs_role_policy(), sort_keys=True)
        if policy == target_policy:
            print('ECS role policy ' + role + ' is present and correct.')
            return True
        else:
            print('ECS role policy ' + role + ' is present, but different.')
            return False


def update_ecs_role_policy():
    if check_ecs_role_policy():
        return True
    else:
        role = get_instance_role(get_first_ecs_instance())
        policy = json.dumps(generate_ecs_role_policy())
        iam = get_iam_connection()
        print('Putting policy: ' + ECS_ROLE_BUCKET_ACCESS_POLICY_NAME + ' into role: ' + role)
        iam.put_role_policy(
            role,
            ECS_ROLE_BUCKET_ACCESS_POLICY_NAME,
            policy
        )


# Amazon SQS


def get_queue_url():
    result = local(
        'aws sqs list-queues' +
        AWS_CLI_STANDARD_OPTIONS,
        capture=True
    )

    if result is not None and result != '':
        result_struct = json.loads(result)
        if isinstance(result_struct, dict) and 'QueueUrls' in result_struct:
            for u in result_struct['QueueUrls']:
                if u.split('/')[-1] == SQS_QUEUE_NAME:
                    return u

    return None


def get_or_create_queue():
    u = get_queue_url()
    if u is None:
        local(
            'aws sqs create-queue' +
            '    --queue-name ' + SQS_QUEUE_NAME +
            AWS_CLI_STANDARD_OPTIONS,
            capture=True
        )

        tries = 0
        while True:
            time.sleep(WAIT_TIME)
            u = get_queue_url()

            if u is not None and tries < RETRIES:
                return u

            tries += 1


# Putting together the demo POV-Ray file.

def create_pov_ray_zip():
    if os.path.exists(POV_RAY_SCENE_FILE):
        print('Deleting old ZIP file: ' + POV_RAY_SCENE_FILE)
        os.remove(POV_RAY_SCENE_FILE)

    print('Creating ZIP file: ' + POV_RAY_SCENE_FILE + '...')
    with ZipFile(POV_RAY_SCENE_FILE, 'w', ZIP_DEFLATED) as z:
        saved_dir = os.getcwd()
        os.chdir(POV_RAY_SCENE_NAME)
        for f in POV_RAY_SCENE_FILES:
            print('Adding: ' + f + '...')
            z.write(f)
        os.chdir(saved_dir)
        z.close()

# High level functions. Call these as "fab <function>"


def update_bucket():
    get_or_create_bucket()


def update_lambda():
    update_lambda_function()
    update_bucket_permissions()
    setup_bucket_notifications()


def update_ecs():
    update_ecs_image()
    update_ecs_task_definition()


def update_queue():
    get_or_create_queue()


def setup():
    update_bucket()
    update_queue()
    update_lambda()
    update_ecs()
    update_ecs_role_policy()
    create_pov_ray_zip()
