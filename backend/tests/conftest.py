import base64
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from service.core.models import LogAnalysisReport


class FakeLogIngestor:
    """Controllable stand-in for LoggyAI-backed adapters in API tests."""

    def __init__(self):
        self.fetch_logs = MagicMock(return_value=[{"severity": "ERROR"}])
        self.analyze = MagicMock(
            return_value=LogAnalysisReport(incidents=[])
        )
        self.save_report = MagicMock()
        self.has_processed = MagicMock(return_value=False)
        self.save_processed_event = MagicMock()
        self.detect_signature_repeat = MagicMock(return_value=False)


@pytest.fixture
def mock_loggy_ai():
    return FakeLogIngestor()


@pytest.fixture
def patch_loggy_ai_create(mock_loggy_ai):
    with patch("main.LoggyAI.create", return_value=mock_loggy_ai) as create_mock:
        yield create_mock, mock_loggy_ai


@pytest.fixture
def client(patch_loggy_ai_create):
    _create_mock, _adapter = patch_loggy_ai_create
    from main import app

    return TestClient(app)


@pytest.fixture
def mock_genai_client():
    with patch("service.core.google_ai.genai.Client") as client_cls:
        client = MagicMock()
        client_cls.return_value = client
        yield client


@pytest.fixture
def mock_gcp_adapter_clients():
    with (
        patch("service.core.gcp_adapter.default", return_value=(None, "test-project")),
        patch("service.core.gcp_adapter.cloud_logging.Client") as logging_cls,
        patch("service.core.gcp_adapter.firestore.Client") as firestore_cls,
    ):
        logging_client = MagicMock()
        firestore_client = MagicMock()
        logging_cls.return_value = logging_client
        firestore_cls.return_value = firestore_client
        yield {
            "logging_client": logging_client,
            "firestore_client": firestore_client,
        }


def make_pubsub_payload(log_entry: dict) -> dict:
    encoded = base64.b64encode(json.dumps(log_entry).encode("utf-8")).decode("utf-8")
    return {
        "subscription": "projects/test/subscriptions/test-sub",
        "message": {
            "data": encoded,
            "messageId": "msg-1",
            "publishTime": "2026-01-01T00:00:00.000Z",
            "attributes": {},
        },
    }


def sample_incident(**overrides):
    from service.core.models import ActionPlan, LogAnalysisResponse

    data = {
        "operational_summary": "Service unavailable",
        "service_name": "api",
        "business_impact": "HIGH",
        "root_cause": "Connection pool exhausted",
        "ai_suggestion": "Check database connections",
        "first_seen_timestamp": "2026-01-01T00:00:00Z",
        "last_seen_timestamp": "2026-01-01T01:00:00Z",
        "action_plan": [
            ActionPlan(step=1, action="Restart pods", warning="May cause brief outage")
        ],
    }
    data.update(overrides)
    return LogAnalysisResponse(**data)
