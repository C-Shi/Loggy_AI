import random
from google.cloud.logging_v2 import Client, Resource
from dotenv import load_dotenv
import os

load_dotenv()
PROJECT_ID = os.getenv("PROJECT_ID")


class MockLogGenerator:
    def __init__(self, project: str):
        self.client = Client(project=project)
        self.project = project

        self.resource_pools = [
            {"type": "gce_instance", "labels": {"zone": "us-central1-a"}},
            {"type": "cloud_run_revision", "labels": {"service_name": "auth-service"}},
            {"type": "cloud_run_revision", "labels": {"service_name": "payment-gateway"}},
            {"type": "k8s_container", "labels": {"cluster_name": "prod-cluster", "namespace": "default"}}
        ]

        self.severities = ["INFO", "WARNING", "ERROR", "CRITICAL"]
        self.weight = [0.6, 0.25, 0.10, 0.05]

        self.log_templates = {
            "INFO": [
                {"message": "User login successful", "http_status": 200, "latency_ms": random.randint(10, 150)},
                {"message": "Database connection pool checked out", "active_connections": 12}
            ],
            "WARNING": [
                {"message": "High memory consumption detected", "memory_utilization_pct": 84.5},
                {"message": "API rate limit approaching for client token", "remaining_requests": 150}
            ],
            "ERROR": [
                {"message": "Failed to write record to secondary database cluster", "error_code": "DB_CONN_TIMEOUT"},
                {"message": "Token verification signature mismatch", "error_code": "AUTH_INVALID_JWT"},
                {"message": "Email test@gmail.com already existed.", "error_code": "DUPLICATE_EMAIL"},
            ],
            "CRITICAL": [
                {"message": "Cascading thread exhaustion across cluster pool", "error_code": "SYS_FATAL_OOM"},
                {"message": "Potential SQL Injection pattern intercepted at firewall", "attack_vector": "payload_sqli"}
            ]
        }

    def create_log(self):
        resource = random.choice(self.resource_pools)
        severity = random.choices(self.severities, weights=self.weight)[0]
        log_template = random.choice(self.log_templates[severity])
        return resource, severity, log_template
    
    def batch(self, size: int) -> None:
        for _ in range(size):
            resource, severity, log_template = self.create_log()
            self.client.logger("sample_log").log_struct(
                info={
                    "labels": resource["labels"],
                    **log_template
                },
                resource=Resource(**resource),
                severity=severity
            )

if __name__ == "__main__":
    generator = MockLogGenerator(project=PROJECT_ID)
    generator.batch(10)