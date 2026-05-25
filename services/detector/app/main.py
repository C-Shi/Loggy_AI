from app.core.gcp_adapter import GoogleCloudLoggingAdapter
if __name__ == '__main__':
    logger = GoogleCloudLoggingAdapter(project_id="devops-cert-440119")
    logger.fetch_logs()