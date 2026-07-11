from datetime import datetime

import pytest
from google.genai import errors as genai_errors

from service.core.base import SignatureClaimResult
from service.core.models import LogAnalysisReport
from service.helper.error import LogPayloadLimitError, PromptValidationError
from tests.conftest import make_pubsub_payload, sample_incident


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
    def test_claimed_success(self, client, patch_loggy_ai_create):
        _, adapter = patch_loggy_ai_create
        log_entry = {"severity": "ERROR", "textPayload": "boom", "insertId": "ins-1"}
        incident = sample_incident()
        adapter.analyze.return_value = LogAnalysisReport(incidents=[incident])
        adapter.claim_or_follow_signature.return_value = SignatureClaimResult(
            outcome="claimed", signature="sig-1", report_id=None, count=1
        )

        response = client.post("/trigger", json=make_pubsub_payload(log_entry))

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        adapter.has_processed.assert_called_once_with(log_entry)
        adapter.claim_or_follow_signature.assert_called_once_with(log_entry)
        adapter.analyze.assert_called_once_with([log_entry])
        adapter.finalize_signature_report.assert_called_once_with(
            "sig-1", incident, source_log=log_entry
        )
        adapter.save_processed_event.assert_called_once_with(log_entry, "COMPLETED")
        adapter.release_signature_claim.assert_not_called()

    def test_followed_ready_records_follower(self, client, patch_loggy_ai_create):
        _, adapter = patch_loggy_ai_create
        log_entry = {"severity": "ERROR", "textPayload": "boom", "insertId": "ins-1"}
        adapter.claim_or_follow_signature.return_value = SignatureClaimResult(
            outcome="followed_ready",
            signature="sig-1",
            report_id="report-1",
            count=2,
        )

        response = client.post("/trigger", json=make_pubsub_payload(log_entry))

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        adapter.analyze.assert_not_called()
        adapter.finalize_signature_report.assert_not_called()
        adapter.record_signature_follower.assert_called_once_with(
            "sig-1", "report-1", source_log=log_entry
        )
        adapter.save_processed_event.assert_called_once_with(log_entry, "COMPLETED")

    def test_followed_pending_returns_503(self, client, patch_loggy_ai_create):
        _, adapter = patch_loggy_ai_create
        log_entry = {"severity": "ERROR", "textPayload": "boom", "insertId": "ins-1"}
        adapter.claim_or_follow_signature.return_value = SignatureClaimResult(
            outcome="followed_pending",
            signature="sig-1",
            report_id=None,
            count=1,
        )

        response = client.post("/trigger", json=make_pubsub_payload(log_entry))

        assert response.status_code == 503
        adapter.analyze.assert_not_called()
        adapter.save_processed_event.assert_not_called()

    def test_skips_already_processed_log(self, client, patch_loggy_ai_create):
        _, adapter = patch_loggy_ai_create
        log_entry = {"severity": "ERROR", "textPayload": "boom", "insertId": "ins-1"}
        adapter.has_processed.return_value = True

        response = client.post("/trigger", json=make_pubsub_payload(log_entry))

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "message": "Log has already been processed",
        }
        adapter.has_processed.assert_called_once_with(log_entry)
        adapter.claim_or_follow_signature.assert_not_called()
        adapter.analyze.assert_not_called()
        adapter.save_processed_event.assert_not_called()

    def test_gemini_failure_releases_claim(self, client, patch_loggy_ai_create):
        _, adapter = patch_loggy_ai_create
        log_entry = {"severity": "ERROR", "textPayload": "boom", "insertId": "ins-1"}
        adapter.claim_or_follow_signature.return_value = SignatureClaimResult(
            outcome="claimed", signature="sig-1", report_id=None, count=1
        )
        adapter.analyze.side_effect = genai_errors.ClientError(
            429, {"error": {"message": "RESOURCE_EXHAUSTED"}}
        )

        response = client.post("/trigger", json=make_pubsub_payload(log_entry))

        assert response.status_code == 500
        adapter.release_signature_claim.assert_called_once_with("sig-1")
        adapter.finalize_signature_report.assert_not_called()
        adapter.save_processed_event.assert_not_called()

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
        log_entry = {"severity": "ERROR", "textPayload": "boom", "insertId": "ins-1"}
        adapter.claim_or_follow_signature.return_value = SignatureClaimResult(
            outcome="claimed", signature="sig-1", report_id=None, count=1
        )

        response = client.post("/trigger", json=make_pubsub_payload(log_entry))

        assert response.status_code == 400
        assert response.json()["detail"] == message
        adapter.release_signature_claim.assert_called_once_with("sig-1")
        adapter.save_processed_event.assert_called_once_with(log_entry, "FAILED")
        adapter.has_processed.assert_called_once_with(log_entry)
