"""
Simulate the production event path:

  Cloud Logging sink  ->  Pub/Sub (loggy-ai-pubsub)  ->  Eventarc  ->  Cloud Run /trigger

The sink publishes a base64-encoded LogEntry as the Pub/Sub message data.
Eventarc delivers it to Cloud Run as a CloudEvents HTTP request:
  - ce-* headers carry CloudEvent metadata
  - body is MessagePublishedData (Pub/Sub push format)
"""

import base64
import json
import os
import uuid
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID", "my-project")
TOPIC = "loggy-ai-pubsub"
TRIGGER_NAME = "loggy-ai-trigger"
REGION = "us-west1"


def build_log_entry(
    *,
    project_id: str = PROJECT_ID,
    severity: str = "ERROR",
    service_name: str = "auth-service",
    message: str = "Failed to write record to secondary database cluster",
    error_code: str = "DB_CONN_TIMEOUT",
    insert_id: str | None = None,
    timestamp: str | None = None,
) -> dict:
    """Build a LogEntry as exported by a Cloud Logging sink to Pub/Sub."""
    timestamp = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    insert_id = insert_id or str(uuid.uuid4())

    return {
        "insertId": insert_id,
        "logName": f"projects/{project_id}/logs/run.googleapis.com%2Fstdout",
        "timestamp": timestamp,
        "receiveTimestamp": timestamp,
        "severity": severity,
        "resource": {
            "type": "cloud_run_revision",
            "labels": {
                "project_id": project_id,
                "service_name": service_name,
                "location": REGION,
            },
        },
        "jsonPayload": {
            "message": message,
            "error_code": error_code,
        },
    }


def build_pubsub_payload(
    log_entry: dict,
    *,
    project_id: str = PROJECT_ID,
    subscription: str | None = None,
    message_id: str | None = None,
    publish_time: str | None = None,
) -> dict:
    """
    Build MessagePublishedData per google.events.cloud.pubsub.v1.MessagePublishedData.

  The message.data field is the base64-encoded LogEntry JSON, matching what the
  logging sink writes to the Pub/Sub topic.
    """
    message_id = message_id or str(uuid.uuid4())
    publish_time = publish_time or log_entry.get("timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    encoded_log = base64.b64encode(json.dumps(log_entry).encode()).decode()

    return {
        "subscription": subscription or f"projects/{project_id}/subscriptions/eventarc-{REGION}-{TRIGGER_NAME}-sub-000",
        "message": {
            "data": encoded_log,
            "messageId": message_id,
            "publishTime": publish_time,
            "attributes": {
                "logging.googleapis.com/timestamp": log_entry.get("timestamp", publish_time),
            },
        },
    }


def build_cloudevent_headers(
    *,
    project_id: str = PROJECT_ID,
    topic: str = TOPIC,
    message_id: str,
    publish_time: str,
) -> dict[str, str]:
    """Build CloudEvents HTTP headers as Eventarc delivers to Cloud Run."""
    return {
        "ce-specversion": "1.0",
        "ce-type": "google.cloud.pubsub.topic.v1.messagePublished",
        "ce-source": f"//pubsub.googleapis.com/projects/{project_id}/topics/{topic}",
        "ce-id": message_id,
        "ce-time": publish_time,
        "Content-Type": "application/json; charset=utf-8",
    }


def send_event(
    url: str = "http://127.0.0.1:8000/trigger",
    log_entry: dict | None = None,
    *,
    project_id: str = PROJECT_ID,
    topic: str = TOPIC,
    subscription: str | None = None,
) -> requests.Response:
    """POST an Eventarc-formatted Pub/Sub event to the /trigger endpoint."""
    log_entry = log_entry or build_log_entry(project_id=project_id)
    payload = build_pubsub_payload(
        log_entry,
        project_id=project_id,
        subscription=subscription,
    )
    message = payload["message"]
    headers = build_cloudevent_headers(
        project_id=project_id,
        topic=topic,
        message_id=message["messageId"],
        publish_time=message["publishTime"],
    )
    return requests.post(url, headers=headers, json=payload)


if __name__ == "__main__":
    response = send_event()
    print(f"Status: {response.status_code}, Response: {response.text}")
