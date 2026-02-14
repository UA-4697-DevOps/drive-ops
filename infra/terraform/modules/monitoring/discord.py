import urllib3
import json
import os

http = urllib3.PoolManager()
url = os.environ['DISCORD_WEBHOOK_URL']

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # 1. Defensive: Check if this is actually an SNS event
        if 'Records' not in event or not event['Records']:
            print("Event does not contain 'Records'. Ignoring.")
            return {"status": 200, "message": "Not an SNS event"}

        # 2. Extract the message
        sns_record = event['Records'][0]['Sns']
        message = sns_record['Message']
        
        # 3. Try to parse CloudWatch JSON format
        try:
            data = json.loads(message)
            # It's a structured CloudWatch Alarm
            alarm_name = data.get('AlarmName', 'Unknown')
            new_state = data.get('NewStateValue', 'ALERT')
            reason = data.get('NewStateReason', 'No reason provided')
            
            title = f"{new_state}: {alarm_name}"
            desc = reason
            
            # Red for ALARM, Green for OK, Yellow for others
            if new_state == 'ALARM':
                color = 15548997 # Red
            elif new_state == 'OK':
                color = 5763719  # Green
            else:
                color = 16776960 # Yellow
                
        except json.JSONDecodeError:
            # Fallback: It's just a raw text message (not JSON)
            title = sns_record.get('Subject', 'Notification')
            desc = str(message)
            color = 16776960 # Yellow

        # 4. TRUNCATE: Fix the 4096 character limit crash
        if len(desc) > 2000:
            desc = desc[:2000] + "\n... [Truncated]"

        # 5. Send to Discord
        payload = {
            "username": "AWS Alert Bot",
            "embeds": [{
                "title": title,
                "description": desc,
                "color": color,
                "footer": {"text": "Drive-Ops Monitoring"}
            }]
        }
        
        encoded_data = json.dumps(payload).encode('utf-8')
        resp = http.request(
            'POST', 
            url, 
            body=encoded_data, 
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Discord response: {resp.status}")
        return {"status": resp.status}

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        # We catch the error so Lambda doesn't keep retrying a bad message forever
        return {"status": 500, "error": str(e)}
