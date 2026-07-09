from datetime import datetime
from unittest.mock import patch

import pytest

from service.core.models import LogAnalysisReport
from service.helper.error import LogPayloadLimitError, PromptValidationError
from tests.conftest import make_pubsub_payload


class TestHealth:
    def test_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestRun:
    def test_success(self, client, patch_loggy_ai_create):
        create_mock, adapter = patch_loggy_ai_create
        report = LogAnalysisReport(incidents=[])
        adapter.analyze.return_value = report

        response = client.post("/run", json={"provider": "google", "limit": 10})

        assert response.status_code == 200
        assert response.json() == {"incidents": []}
        create_mock.assert_called_once_with("google")
        adapter.fetch_logs.assert_called_once()
        adapter.analyze.assert_called_once()

    def test_custom_start_and_end(self, client, patch_loggy_ai_create):
        _, adapter = patch_loggy_ai_create

        client.post(
            "/run",
            json={
                "start": "2026-01-01 10:00:00",
                "end": "2026-01-02 10:00:00",
            },
        )

        kwargs = adapter.fetch_logs.call_args.kwargs
        assert kwargs["start_time"] == datetime(2026, 1, 1, 10, 0, 0)
        assert kwargs["end_time"] == datetime(2026, 1, 2, 10, 0, 0)

    @pytest.mark.parametrize(
        "error_cls,message",
        [
            (PromptValidationError, "unsafe prompt"),
            (LogPayloadLimitError, "too many logs"),
        ],
    )
    def test_validation_errors_return_400(
        self, client, patch_loggy_ai_create, error_cls, message
    ):
        _, adapter = patch_loggy_ai_create
        adapter.analyze.side_effect = error_cls(message)

        response = client.post("/run", json={})

        assert response.status_code == 400
        assert response.json()["detail"] == message


class TestTrigger:
    def test_success(self, client, patch_loggy_ai_create):
        _, adapter = patch_loggy_ai_create
        log_entry = {"severity": "ERROR", "textPayload": "boom"}
        adapter.analyze.return_value = LogAnalysisReport(incidents=[])

        response = client.post("/trigger", json=make_pubsub_payload(log_entry))

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        adapter.analyze.assert_called_once_with([log_entry])
        adapter.save_report.assert_called_once()

    @pytest.mark.parametrize(
        "error_cls,message",
        [
            (PromptValidationError, "unsafe prompt"),
            (LogPayloadLimitError, "payload too large"),
        ],
    )
    def test_validation_errors_return_400(
        self, client, patch_loggy_ai_create, error_cls, message
    ):
        _, adapter = patch_loggy_ai_create
        adapter.analyze.side_effect = error_cls(message)
        log_entry = {"severity": "ERROR", "textPayload": "boom"}

        response = client.post("/trigger", json=make_pubsub_payload(log_entry))

        assert response.status_code == 400
        assert response.json()["detail"] == message
