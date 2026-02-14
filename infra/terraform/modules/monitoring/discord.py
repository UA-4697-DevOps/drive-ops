import urllib3
import json
import os

# Initialize PoolManager outside the handler to reuse connections across executions
http = urllib3.PoolManager()
url = os.environ.get('DISCORD_WEBHOOK_URL')

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    if not url:
        print("ERROR: DISCORD_WEBHOOK_URL environment variable is missing.")
        return {"status": 400}

    try:
        # 1. Defensive Check: Ensure this is an SNS event
        if 'Records' not in event or not event['Records']:
            print("Event does not contain 'Records'. Ignoring.")
            return {"status": 200, "message": "Not an SNS event"}

        # 2. Extract the message content
        sns_record = event['Records'][0]['Sns']
        message = sns_record['Message']
        
        # 3. Message Parsing: Handle CloudWatch JSON vs. Raw Text
        try:
            data = json.loads(message)
            # Handle structured CloudWatch Alarm JSON
            alarm_name = data.get('AlarmName', 'Unknown')
            new_state = data.get('NewStateValue', 'ALERT')
            reason = data.get('NewStateReason', 'No reason provided')
            
            title = f"{new_state}: {alarm_name}"
            desc = reason
            
            # Color Mapping: Red for ALARM, Green for OK, Yellow for others
            if new_state == 'ALARM':
                color = 15548997 # Red
            elif new_state == 'OK':
                color = 5763719  # Green
            else:
                color = 16776960 # Yellow
                
        except json.JSONDecodeError:
            # Fallback: Handle raw text messages (non-JSON)
            title = sns_record.get('Subject', 'Notification')
            desc = str(message)
            color = 16776960 # Yellow

        # 4. Content Truncation: Prevent Discord 4096 character limit crashes
        if len(desc) > 2000:
            desc = desc[:2000] + "\n... [Truncated]"

        # 5. Prepare Discord Payload
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

        # --- CodeRabbitAI Improvements ---
        # Set timeouts: 5s to connect, 10s to read (prevents Lambda hanging)
        timeout = urllib3.Timeout(connect=5.0, read=10.0)

        resp = http.request(
            'POST', 
            url, 
            body=encoded_data, 
            headers={'Content-Type': 'application/json'},
            timeout=timeout
        )
        
        # Log response status; provide warning details for non-2xx statuses
        if resp.status >= 300:
            print(f"WARNING: Discord returned {resp.status}: {resp.data.decode('utf-8', errors='replace')}")
        else:
            print(f"Discord response: {resp.status}")

        return {"status": resp.status}

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        # Catch errors to prevent infinite Lambda retries on poisonous messages
        return {"status": 500, "error": str(e)}
