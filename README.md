Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License").
You may not use this file except in compliance with the License.
A copy of the License is located at

    http://aws.amazon.com/apache2.0/

or in the "license" file accompanying this file.
This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.

# Lambda ECS Worker Pattern

This code example illustrates the concept of using Amazon ECS Tasks to extend the functionality of AWS Lambda.

In this pattern, an AWS Lambda function is triggered by an Amazon S3 event. The AWS Lambda function then pushes the
event data into an Amazon SQS queue and starts an Amazon ECS Task. A simple shell script running inside the Amazon ECS
Task’s container fetches the message from the Amazon SQS queue and processes it.

![Architecture overview of the Lambda ECS Worker Pattern](LambdaECSWorkerPattern.png)

As a demo, we use this pattern to implement a ray-tracing worker using the popular open source
[POV-Ray](http://www.povray.org/) ray-tracer that can be triggered by uploading a POV-Ray scene description wrapped
into a .ZIP file into an Amazon S3 bucket. Running a ray-tracer inside AWS Lambda would probably take more than the
limit of 60 seconds to complete, so we use Lambda to push the Amazon S3 Notification data into an Amazon SQS queue and
start an Amazon ECS Task for the actual processing. The shell script running in the Amazon ECS Task’s container takes
care of fetching the input data from Amazon S3, running the POV-Ray ray-tracing software and uploading the result image
back into the Amazon S3 bucket.

## Files

The following files are included in this repository:

* README.txt: This file.
* LICENSE.txt: Apache 2.0 license under which this code is licensed.
* NOTICE.txt: Notice about the licensing of this code.
* ECSLogo: A directory containing the POV-Ray source for a demo image.
  * AWS_Logo_PoweredBy_300px.png: Official "Powered by AWS" logo image.
  * ECSLogo.ini: A POV-Ray .INI file containing rendering parameters.
  * ECSLogo.poc: A POV-Ray scene description file that renders the Amazon ECS Logo as a demo.
* ecs-worker: A directory containing the worker shell script for the Amazon ECS Task.
  * ecs-worker.sh : The shell script to be run in a Docker Container as part of the Amazon ECS task.
* ecs-worker-launcher: A directory containing the AWS Lambda function.
  * ecs-worker-launcher.js: A Lambda function that sends event data into Amazon SQS and starts an Amazon ECS Task.
* fabfile.py: A Python Fabric script that configures all of the necessary components for this demo.
* config.py: User-specific constants for fabfile.py. Edit these with your own values.
* requirements.py: Python requirements file for fabfile.py.
* LambdaECSWorkerPattern.png: The image you see above.

