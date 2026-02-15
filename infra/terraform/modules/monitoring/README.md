# 📊 Monitoring & Alerting Module

This module provides a centralized observability and notification system for the **Drive-Ops** infrastructure. It is designed to be cost-efficient while providing sufficient visibility for MVP operations.

## 🏗️ Architecture
The monitoring stack consists of the following components:
* **CloudWatch Log Groups**: Centralized storage for application and system logs.
* **CloudWatch Alarms**: Monitors for critical resource metrics (RDS CPU, SQS message age, **EC2 Instance CPU**, and **System Status Checks**).
* **SNS Topic**: A notification hub named `drive-ops-dev-alerts` that receives alarm state changes.
* **Lambda Notifier**: A Python-based function that formats SNS messages and sends them to a Discord channel via a Webhook.

---

## 🚀 How to Test an Alarm End-to-End

To verify that the entire pipeline (CloudWatch → SNS → Lambda → Discord) is working correctly without stressing actual resources, use the AWS CLI to manually trigger an alarm.

### 1. Trigger the Alarm
Run this command in your terminal to force the RDS CPU alarm into an `ALARM` state:
```bash
aws cloudwatch set-alarm-state \
  --alarm-name "drive-ops-dev-rds-high-cpu" \
  --state-value ALARM \
  --state-reason "Manual End-to-End Test: Validating Discord notifications."
```

### 2. Verify Notification
* **Check Discord**: You should receive a formatted message with the alarm details (including a red status indicator) within 10 seconds.
* **(Optional) Lambda Logs**: If the message doesn't appear, check the logs in CloudWatch under the group: `/aws/lambda/drive-ops-dev-discord-notifier`.

### 3. Reset the Alarm
Once confirmed, return the alarm to its healthy (`OK`) state to ensure your monitoring dashboard reflects the actual state of the infrastructure:

```bash
aws cloudwatch set-alarm-state \
  --alarm-name "drive-ops-dev-rds-high-cpu" \
  --state-value OK \
  --state-reason "Test finished, clearing manual state."
```

## 🔐 Security & IAM Requirements

This module is compliant with the `DevOpsBound` permissions boundary. 

* **Naming Convention**: All IAM roles must start with the **`Training-`** prefix (e.g., `Training-drive-ops-dev-lambda-discord-role`) to satisfy `iam:PassRole` and `iam:CreateRole` restrictions.
* **Secrets**: The Discord Webhook URL must be provided via the `DISCORD_WEBHOOK_URL` environment variable and is handled as a sensitive value.

## 💰 Cost Optimization (Caution)

To minimize AWS costs during the MVP phase, this module implements:

* **Short Retention**: Log retention is set to **3 days** to stay within the CloudWatch Free Tier limits.
* **Minimal Metrics**: Only essential health metrics (CPU and Queue Age) are monitored.
* **Lambda Memory**: Restricted to **128MB** to minimize execution costs.
