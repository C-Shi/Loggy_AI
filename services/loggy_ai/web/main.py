import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import LoggyAI
from app.helper.error import LogPayloadLimitError, PromptValidationError

load_dotenv()

app = FastAPI()
logger = logging.getLogger("uvicorn.error")


class ConfigItem(BaseModel):
    """Request body for the /run log analysis endpoint."""

    provider: str = "google"
    project: Optional[str] = None
    limit: int = 100
    log: Optional[str] = None
    severity: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    keywords: Optional[List[str]] = None


class PubSubMessage(BaseModel):
    """Pub/Sub message envelope from a CloudEvent push subscription."""

    data: str
    messageId: str
    publishTime: str
    attributes: Dict[str, str] = {}


class MessagePublishedData(BaseModel):
    """CloudEvent payload for log-triggered analysis."""

    subscription: str
    message: PubSubMessage


@app.get("/health")
def health():
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/run")
def run(config: ConfigItem):
    """Fetch logs from the configured provider and return AI analysis."""
    logAI = LoggyAI.create(config.provider)
    if config.start:
        start_time = datetime.strptime(config.start, "%Y-%m-%d %H:%M:%S")
    else:
        start_time = datetime.now() - timedelta(days=1)

    if config.end:
        end_time = datetime.strptime(config.end, "%Y-%m-%d %H:%M:%S")
    else:
        end_time = datetime.now()

    logs = logAI.fetch_logs(
        limit=config.limit,
        log_name=config.log,
        severity_level=config.severity,
        keywords=config.keywords,
        start_time=start_time,
        end_time=end_time,
    )

    try:
        response = logAI.analyze(logs)
        return response
    except (PromptValidationError, LogPayloadLimitError) as e:
        raise HTTPException(400, detail=e.message)


@app.post("/trigger")
def trigger(payload: MessagePublishedData):
    """
    Analyze a single log entry pushed via Pub/Sub and persist the report to Firestore.
    """
    logger.info(f"Received CloudEvent Data: {json.dumps(payload.model_dump())}")

    encoded_log = payload.message.data

    decoded_log = base64.b64decode(encoded_log).decode("utf-8")
    log_entry = json.loads(decoded_log)

    logAI = LoggyAI.create(provider=ConfigItem().provider)

    try:
        response = logAI.analyze([log_entry])
        logAI.save_report(response, source_log=log_entry)
        return {"status": "ok"}
    except (PromptValidationError, LogPayloadLimitError) as e:
        raise HTTPException(400, detail=e.message)
