"""
Publish repetitive ERROR logs to Cloud Logging to exercise concurrency handling.

Unlike mock_log_generator (mixed severities / many templates), this tool:
  1. Emits ERROR only, and only two distinct error shapes
  2. Inserts a short delay between each publish so Eventarc/Cloud Run see a burst
     of near-concurrent events without slamming Gemini with unique incidents

Typical use: flood duplicates so signature dedup and DLQ/idempotency paths are stressed.
"""

import os
import random
import time

from dotenv import load_dotenv
from google.cloud.logging_v2 import Client, Resource

load_dotenv()
PROJECT_ID = os.getenv("PROJECT_ID")

# Delay between publishes in a batch (milliseconds). Keeps events tightly clustered
# without issuing every write in the same instant.
DEFAULT_DELAY_MS = 5


class MockRepetitiveLogGenerator:
    def __init__(self, project: str, delay_ms: int = DEFAULT_DELAY_MS):
        self.client = Client(project=project)
        self.project = project
        self.delay_ms = delay_ms

        self.resource = {
            "type": "cloud_run_revision",
            "labels": {"location": "us-west1"},
        }

        # Exactly two distinguishable ERROR templates for concurrency / dedup tests.
        self.error_templates = [
            {
                "message": "Failed to write record to secondary database cluster",
                "error_code": "DB_CONN_TIMEOUT",
                "service_name": "postgres-replication",
            },
            {
                "message": "Token verification signature mismatch",
                "error_code": "AUTH_INVALID_JWT",
                "service_name": "auth-service",
            },
        ]

    def create_log(self, template_index: int | None = None):
        """
        Build one ERROR log.

        Args:
            template_index: 0 or 1 to force a specific error; None picks randomly.
        """
        if template_index is None:
            template = random.choice(self.error_templates).copy()
        else:
            template = self.error_templates[template_index].copy()

        service_name = template.pop("service_name")
        labels = {**self.resource["labels"], "service_name": service_name}
        resource_with_service = {**self.resource, "labels": labels}

        return resource_with_service, "ERROR", template, labels

    def batch(
        self,
        size: int,
        *,
        template_index: int | None = None,
        delay_ms: int | None = None,
    ) -> None:
        """
        Publish ``size`` ERROR logs to Cloud Logging.

        Each log is followed by a short sleep so Pub/Sub/Eventarc receive a burst
        of near-concurrent messages rather than one giant synchronous dump.

        Args:
            size: Number of logs to publish.
            template_index: If 0 or 1, all logs use that single error shape
                (maximum repetition). If None, randomly mix the two errors.
            delay_ms: Override inter-publish delay; defaults to instance delay_ms.
        """
        pause_s = (self.delay_ms if delay_ms is None else delay_ms) / 1000.0

        for i in range(size):
            resource, severity, log_template, labels = self.create_log(template_index)
            self.client.logger("sample_log").log_struct(
                info={
                    "labels": labels,
                    **log_template,
                },
                resource=Resource(**resource),
                severity=severity,
            )
            if i < size - 1 and pause_s > 0:
                time.sleep(pause_s)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Publish repetitive ERROR logs for concurrency / dedup load tests."
    )
    parser.add_argument(
        "-n",
        "--size",
        type=int,
        default=100,
        help="Number of ERROR logs to publish (default: 100)",
    )
    parser.add_argument(
        "--error",
        type=int,
        choices=[0, 1],
        default=None,
        help="Force only error template 0 or 1; omit to randomly mix both",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=DEFAULT_DELAY_MS,
        help=f"Milliseconds between each publish (default: {DEFAULT_DELAY_MS})",
    )
    args = parser.parse_args()

    generator = MockRepetitiveLogGenerator(project=PROJECT_ID, delay_ms=args.delay_ms)
    generator.batch(args.size, template_index=args.error)
    print(
        f"Published {args.size} ERROR log(s) "
        f"(template={'mixed' if args.error is None else args.error}, "
        f"delay_ms={args.delay_ms})"
    )
