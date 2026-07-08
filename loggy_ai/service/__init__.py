from service.core.gcp_adapter import GoogleCloudLoggingAdapter
from service.core.base import LogIngestor


class LoggyAI:
    # Factory Pattern
    @classmethod
    def create(cls, provider: str, project_id: str = None) -> LogIngestor:
        if provider.lower() == "google":
            return GoogleCloudLoggingAdapter(project_id)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
