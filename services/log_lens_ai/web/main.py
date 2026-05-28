from fastapi import FastAPI
from app import LogLensAI
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()


class ConfigItem(BaseModel):
    provider: str
    project_id: str


@app.get("/health")
def health():
    return 200, "OK"


@app.post("/run")
def run(config: ConfigItem):
    logger = LogLensAI.create(config.provider, config.project_id)
    logs = logger.fetch_logs(
        limit=100,
        severity_level="ERROR",
        keywords=["us-central1-a"],
        start_time=datetime(2026, 5, 20),
    )

    return logs
