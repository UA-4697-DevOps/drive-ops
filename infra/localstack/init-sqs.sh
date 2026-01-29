#!/bin/bash
echo "Creating SQS queues..."
awslocal sqs create-queue --queue-name driver-assigned
echo "SQS queues created."
