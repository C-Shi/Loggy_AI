import base64
import json
import logging
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from app import LoggyAI
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, List
from app.helper.error import PromptValidationError, LogPayloadLimitError
from .helper import write_to_bucket

load_dotenv()

app = FastAPI()
logger = logging.getLogger("uvicorn.error")


class ConfigItem(BaseModel):
    provider: str = "google"
    project: Optional[str] = None
    limit: int = 100
    log: Optional[str] = None
    severity: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    keywords: Optional[List[str]] = None

class CloudEvent(BaseModel):
    data: Dict[str, Any]


@app.get("/health")
def health():
    return 200, "OK"


@app.post("/run")
def run(config: ConfigItem):
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
# at the moment, this only accept on log
def trigger(payload: CloudEvent):
    logger.info(f"Received CloudEvent Data: ${json.dumps(payload.data)}")

    event_data = payload.data

    encoded_log = event_data.get("message", {}).get("data", {})

    decoded_log = base64.b64decode(encoded_log).decode("utf-8")
    log_entry = json.loads(decoded_log)

    insert_id = log_entry.get("insertId", None)
    logAI = LoggyAI.create(provider=ConfigItem().provider)

    try:
        response = logAI.analyze([log_entry])
        report = response.incidents[0].model_dump()
        report["insertId"] = insert_id

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        blob_name = f"report-{timestamp}.json"
        write_to_bucket(report, "loggy-ai-report", blob_name)
        return {"status": "ok", "report_path": f"gs://loggy-ai-report/{blob_name}"}
    except (PromptValidationError, LogPayloadLimitError) as e:
        raise HTTPException(400, detail=e.message)
