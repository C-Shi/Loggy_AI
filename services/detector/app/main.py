from app.core.gcp_adapter import GoogleCloudLoggingAdapter
from app.helper.mock_log_generator import MockLogGenerator

if __name__ == "__main__":
    logger = GoogleCloudLoggingAdapter(project_id="devops-cert-440119")
    logs = logger.fetch_logs(
        limit=100, severity_level="ERROR", keywords=["us-central1-a"]
    )
    print((logs))
    print(len(logs))
    # mock = MockLogGenerator(project="devops-cert-440119")
    # mock.batch(100)
