import json
import urllib3
import os
import logging

# Initialize logging for better CloudWatch visibility
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    http = urllib3.PoolManager()
    
    # Securely retrieve the webhook URL from environment variables
    url = os.environ.get('DISCORD_WEBHOOK_URL')
    
    if not url:
        logger.error("Environment variable DISCORD_WEBHOOK_URL is missing.")
        return {"status": 500, "error": "Missing Webhook URL"}

    try:
        # Extract SNS details from the event
        sns_record = event['Records'][0]['Sns']
        sns_message = sns_record['Message']
        sns_subject = sns_record.get('Subject', 'Drive-Ops Alert')

        logger.info(f"Received alarm: {sns_subject}")

        # Construct a more professional Discord message using 'embeds'
        # Color 15158528 is a standard 'Red' for alerts
        msg = {
            "embeds": [{
                "title": f"🚨 {sns_subject}",
                "description": sns_message,
                "color": 15158528,
                "footer": {"text": "AWS CloudWatch | Drive-Ops Monitoring"}
            }]
        }
        
        encoded_msg = json.dumps(msg).encode('utf-8')
        
        # Send the POST request to the Discord Webhook
        resp = http.request(
            'POST', 
            url, 
            body=encoded_msg, 
            headers={'Content-Type': 'application/json'}
        )
        
        logger.info(f"Discord response status: {resp.status}")
        return {"status": resp.status}

    except Exception as e:
        logger.error(f"Failed to process alarm. Error: {str(e)}")
        return {"status": 500, "error": str(e)}
