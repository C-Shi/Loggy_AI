import random
from google.cloud.logging_v2 import Client, Resource
from dotenv import load_dotenv
import os

load_dotenv()
PROJECT_ID = os.getenv("PROJECT_ID")

MOCK_SERVICE_NAMES = {
    "auth": "auth-service",
    "user_registration": "user-registration-service",
    "postgres_pool": "postgres-connection-pool",
    "postgres_replication": "postgres-replication",
    "api_gateway": "api-gateway",
    "metrics_collector": "metrics-collector",
    "background_worker": "background-job-worker",
    "edge_waf": "edge-waf-proxy",
}


class MockLogGenerator:
    def __init__(self, project: str):
        self.client = Client(project=project)
        self.project = project

        self.resource_pools = [
            {"type": "gce_instance", "labels": {"zone": "us-central1-a"}},
            {"type": "cloud_run_revision", "labels": {"location": "us-central1"}},
            {"type": "k8s_container", "labels": {"cluster_name": "prod-cluster", "namespace": "default"}},
        ]

        self.severities = ["INFO", "WARNING", "ERROR", "CRITICAL"]
        self.weight = [0.6, 0.25, 0.10, 0.05]

        self.log_templates = {
            "INFO": [
                {
                    "message": "User login successful",
                    "http_status": 200,
                    "latency_ms": random.randint(10, 150),
                    "service_name": MOCK_SERVICE_NAMES["auth"],
                },
                {
                    "message": "Database connection pool checked out",
                    "active_connections": 12,
                    "service_name": MOCK_SERVICE_NAMES["postgres_pool"],
                },
            ],
            "WARNING": [
                {
                    "message": "High memory consumption detected",
                    "memory_utilization_pct": 84.5,
                    "service_name": MOCK_SERVICE_NAMES["metrics_collector"],
                },
                {
                    "message": "API rate limit approaching for client token",
                    "remaining_requests": 150,
                    "service_name": MOCK_SERVICE_NAMES["api_gateway"],
                },
            ],
            "ERROR": [
                {
                    "message": "Failed to write record to secondary database cluster",
                    "error_code": "DB_CONN_TIMEOUT",
                    "service_name": MOCK_SERVICE_NAMES["postgres_replication"],
                },
                {
                    "message": "Token verification signature mismatch",
                    "error_code": "AUTH_INVALID_JWT",
                    "service_name": MOCK_SERVICE_NAMES["auth"],
                },
                {
                    "message": "Email test@gmail.com already existed.",
                    "error_code": "DUPLICATE_EMAIL",
                    "service_name": MOCK_SERVICE_NAMES["user_registration"],
                },
            ],
            "CRITICAL": [
                {
                    "message": "Cascading thread exhaustion across cluster pool",
                    "error_code": "SYS_FATAL_OOM",
                    "service_name": MOCK_SERVICE_NAMES["background_worker"],
                },
                {
                    "message": "Potential SQL Injection pattern intercepted at firewall",
                    "attack_vector": "payload_sqli",
                    "service_name": MOCK_SERVICE_NAMES["edge_waf"],
                },
            ],
        }

    def create_log(self):
        resource = random.choice(self.resource_pools)
        severity = random.choices(self.severities, weights=self.weight)[0]
        log_template = random.choice(self.log_templates[severity]).copy()
        service_name = log_template.pop("service_name")

        labels = {**resource["labels"], "service_name": service_name}
        resource_with_service = {**resource, "labels": labels}

        return resource_with_service, severity, log_template, labels

    def batch(self, size: int) -> None:
        for _ in range(size):
            resource, severity, log_template, labels = self.create_log()
            self.client.logger("sample_log").log_struct(
                info={
                    "labels": labels,
                    **log_template,
                },
                resource=Resource(**resource),
                severity=severity,
            )

if __name__ == "__main__":
    generator = MockLogGenerator(project=PROJECT_ID)
    generator.batch(10)