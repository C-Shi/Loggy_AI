from app.core.gcp_adapter import GoogleCloudLoggingAdapter
from app.helper.mock_log_generator import MockLogGenerator
if __name__ == '__main__':
    logger = GoogleCloudLoggingAdapter(project_id="devops-cert-440119")
    # logger.fetch_logs()
    # mock = MockLogGenerator(project="devops-cert-440119")
    # mock.batch(100)