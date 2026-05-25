from typing import Any, Dict, List
from google.cloud import logging
from app.core.base import LogIngestor

class GoogleCloudLoggingAdapter(LogIngestor):
    """Concrete adapter handling the plumbing with GCP Cloud Logging."""

    def __init__(self, project_id: str) -> None:
        # initalize Logging Client without Credential. Rely on ADC behavior
        self.client = logging.Client(project=project_id)

    def fetch_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        # TODO: Research self.client.list_entries()
        for entry in self.client.list_entries(
            page_size=limit,
            order_by=logging.DESCENDING
        ):
            print(entry.payload)