import base64
import json
import requests

# 1. The actual log content you want to test
gcp_error_log = {
    "textPayload": "Error: Connection timed out in service module.",
    "severity": "ERROR",
    "resource": {"type": "cloud_run_revision"}
}

# 2. Pub/Sub requires the data to be base64 encoded [cite: 7, 39]
encoded_log = base64.b64encode(json.dumps(gcp_error_log).encode()).decode()

# 3. Construct the CloudEvent envelope [cite: 5]
cloud_event = {
    "specversion": "1.0",
    "type": "google.cloud.pubsub.topic.v1.messagePublished",
    "source": "//pubsub.googleapis.com/projects/my-project/topics/my-topic",
    "id": "1234567890",
    "data": {
        "message": {
            "data": encoded_log,
            "messageId": "99999"
        }
    }
}

# 4. Send to your local FastAPI endpoint [cite: 40]
response = requests.post("http://127.0.0.1:8000/trigger", json=cloud_event)
print(f"Status: {response.status_code}, Response: {response.text}")