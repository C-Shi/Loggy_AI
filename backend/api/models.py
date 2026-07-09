from pydantic import BaseModel
from typing import Optional, List, Dict

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