from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from app import LoggyAI
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List
from app.helper.error import PromptValidationError, LogPayloadLimitError

load_dotenv()

app = FastAPI()


class ConfigItem(BaseModel):
    provider: str = "google"
    project: Optional[str] = None
    limit: int = 100
    log: Optional[str] = None
    severity: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    keywords: Optional[List[str]] = None


@app.get("/health")
def health():
    return 200, "OK"


@app.post("/run")
def run(config: ConfigItem):
    logger = LoggyAI.create(config.provider)
    if config.start:
        start_time = datetime.strptime(config.start, "%Y-%m-%d %H:%M:%S")
    else:
        start_time = datetime.now() - timedelta(days=1)

    if config.end:
        end_time = datetime.strptime(config.end, "%Y-%m-%d %H:%M:%S")
    else:
        end_time = datetime.now()

    logs = logger.fetch_logs(
        limit=config.limit,
        log_name=config.log,
        severity_level=config.severity,
        keywords=config.keywords,
        start_time=start_time,
        end_time=end_time,
    )

    try:
        response = logger.analyze(logs)
    except (PromptValidationError, LogPayloadLimitError) as e:
        raise HTTPException(400, detail=e.message)
    return response
