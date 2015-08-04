#!/bin/bash

# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
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
# Simple POV-Ray worker shell script.
#
# Uses the AWS CLI utility to fetch a message from SQS, fetch a ZIP file from S3 that was specified in the message,
# render its contents with POV-Ray, then upload the resulting .png file to the same S3 bucket.
#

region=${AWS_REGION}
queue=${SQS_QUEUE_URL}

# Fetch messages and render them until the queue is drained.
while [ /bin/true ]; do
    # Fetch the next message and extract the S3 URL to fetch the POV-Ray source ZIP from.
    echo "Fetching messages fom SQS queue: ${queue}..."
    result=$( \
        aws sqs receive-message \
            --queue-url ${queue} \
            --region ${region} \
            --wait-time-seconds 20 \
            --query Messages[0].[Body,ReceiptHandle] \
        | sed -e 's/^"\(.*\)"$/\1/'\
    )

    if [ -z "${result}" ]; then
        echo "No messages left in queue. Exiting."
        exit 0
    else
        echo "Message: ${result}."

        receipt_handle=$(echo ${result} | sed -e 's/^.*"\([^"]*\)"\s*\]$/\1/')
        echo "Receipt handle: ${receipt_handle}."

        bucket=$(echo ${result} | sed -e 's/^.*arn:aws:s3:::\([^\\]*\)\\".*$/\1/')
        echo "Bucket: ${bucket}."

        key=$(echo ${result} | sed -e 's/^.*\\"key\\":\s*\\"\([^\\]*\)\\".*$/\1/')
        echo "Key: ${key}."

        base=${key%.*}
        ext=${key##*.}

        if [ \
            -n "${result}" -a \
            -n "${receipt_handle}" -a \
            -n "${key}" -a \
            -n "${base}" -a \
            -n "${ext}" -a \
            "${ext}" = "zip" \
        ]; then
            mkdir -p work
            pushd work

            echo "Copying ${key} from S3 bucket ${bucket}..."
            aws s3 cp s3://${bucket}/${key} . --region ${region}

            echo "Unzipping ${key}..."
            unzip ${key}

            if [ -f ${base}.ini ]; then
                echo "Rendering POV-Ray scene ${base}..."
                if povray ${base}; then
                    if [ -f ${base}.png ]; then
                        echo "Copying result image ${base}.png to s3://${bucket}/${base}.png..."
                        aws s3 cp ${base}.png s3://${bucket}/${base}.png
                    else
                        echo "ERROR: POV-Ray source did not generate ${base}.png image."
                    fi
                else
                    echo "ERROR: POV-Ray source did not render successfully."
                fi
            else
                echo "ERROR: No ${base}.ini file found in POV-Ray source archive."
            fi

            echo "Cleaning up..."
            popd
            /bin/rm -rf work

            echo "Deleting message..."
            aws sqs delete-message \
                --queue-url ${queue} \
                --region ${region} \
                --receipt-handle "${receipt_handle}"

        else
            echo "ERROR: Could not extract S3 bucket and key from SQS message."
        fi
    fi
done
