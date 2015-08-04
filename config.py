# Constants (User configurable)

FULL_NAME_AND_EMAIL = 'First Last <email@domain.com>'  # For Dockerfile/POV-Ray builds.
APP_NAME = 'ECSPOVRayWorker'  # Used to generate derivative names unique to the application.

DOCKERHUB_USER = 'username'
DOCKERHUB_EMAIL = 'email@domain.com'
DOCKERHUB_REPO = 'private'
DOCKERHUB_TAG = DOCKERHUB_USER + '/' + DOCKERHUB_REPO + ':' + APP_NAME

AWS_REGION = 'us-east-1'
AWS_PROFILE = 'default'  # The same profile used by your AWS CLI installation

SSH_KEY_NAME = 'your-ssh-key.pem'  # Expected to be in ~/.ssh
ECS_CLUSTER = 'default'
