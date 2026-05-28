from app.core.gcp_adapter import GoogleCloudLoggingAdapter
from app.core.base import LogIngestor


class LogLenseAI:
    # Factory Pattern
    @classmethod
    def create(cls, provider: str, project_id: str) -> LogIngestor:
        if provider.lower() == "google":
            return GoogleCloudLoggingAdapter(project_id)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
