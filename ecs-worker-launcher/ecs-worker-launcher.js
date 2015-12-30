// Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License").
// You may not use this file except in compliance with the License.
// A copy of the License is located at
//
//    http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file.
// This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and limitations under the License.

// This AWS Lambda function forwards the given event data into an Amazon SQS queue, then starts an Amazon ECS task to
// process that event.

var fs = require('fs');
var async = require('async');
var aws = require('aws-sdk');
var sqs = new aws.SQS({apiVersion: '2012-11-05'});
var ecs = new aws.ECS({apiVersion: '2014-11-13'});

// Check if the given key suffix matches a suffix in the whitelist. Return true if it matches, false otherwise.
exports.checkS3SuffixWhitelist = function(key, whitelist) {
    if(!whitelist){ return true; }
    if(typeof whitelist == 'string'){ return key.match(whitelist + '$') }
    if(Object.prototype.toString.call(whitelist) === '[object Array]') {
        for(var i = 0; i < whitelist.length; i++) {
            if(key.match(whitelist[i] + '$')) { return true; }
        }
        return false;
    }
    console.log(
        'Unsupported whitelist type (' + Object.prototype.toString.call(whitelist) +
        ') for: ' + JSON.stringify(whitelist)
    );
    return false;
};

exports.handler = function(event, context) {
    console.log('Received event:');
    console.log(JSON.stringify(event, null, '  '));

    var config = JSON.parse(fs.readFileSync('config.json', 'utf8'));
    if(!config.hasOwnProperty('s3_key_suffix_whitelist')) {
        config.s3_key_suffix_whitelist = false;
    }
    console.log('Config: ' + JSON.stringify(config));

    var key = event.Records[0].s3.object.key;

    if(!exports.checkS3SuffixWhitelist(key, config.s3_key_suffix_whitelist)) {
        context.fail('Suffix for key: ' + key + ' is not in the whitelist')
    }

    // We can now go on. Put the Amazon S3 URL into Amazon SQS and start an Amazon ECS task to process it.
    async.waterfall([
            function (next) {
                var params = {
                    MessageBody: JSON.stringify(event),
                    QueueUrl: config.queue
                };
                sqs.sendMessage(params, function (err, data) {
                    if (err) { console.warn('Error while sending message: ' + err); }
                    else { console.info('Message sent, ID: ' + data.MessageId); }
                    next(err);
                });
            },
            function (next) {
                // Starts an ECS task to work through the feeds.
                var params = {
                    taskDefinition: config.task,
                    count: 1,
                    cluster: 'default'
                };
                ecs.runTask(params, function (err, data) {
                    if (err) { console.warn('error: ', "Error while starting task: " + err); }
                    else { console.info('Task ' + config.task + ' started: ' + JSON.stringify(data.tasks))}
                    next(err);
                });
            }
        ], function (err) {
            if (err) {
                context.fail('An error has occurred: ' + err);
            }
            else {
                context.succeed('Successfully processed Amazon S3 URL.');
            }
        }
    );
};
