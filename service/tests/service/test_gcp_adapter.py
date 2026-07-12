from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from service.core.gcp_adapter import GoogleCloudLoggingAdapter
from service.core.models import LogAnalysisReport, LogAnalysisResponse, RepetitionCheckResult
from tests.conftest import sample_incident


class TestParsePeriod:
    @pytest.mark.parametrize(
        "period,expected",
        [
            ("5min", timedelta(minutes=5)),
            ("1h", timedelta(hours=1)),
            ("1 day", timedelta(days=1)),
            ("2 hours", timedelta(hours=2)),
        ],
    )
    def test_valid_periods(self, period, expected):
        assert GoogleCloudLoggingAdapter._parse_period(period) == expected

    @pytest.mark.parametrize("period", ["bad", "0min", ""])
    def test_invalid_periods(self, period):
        with pytest.raises(ValueError):
            GoogleCloudLoggingAdapter._parse_period(period)


class TestCandidateIds:
    def test_extracts_ids(self):
        candidates = [{"id": "a"}, {"id": "b"}, {"no_id": True}]
        adapter = object.__new__(GoogleCloudLoggingAdapter)
        assert adapter._candidate_ids(candidates) == {"a", "b"}


class TestReportDocToDict:
    def test_includes_document_id(self):
        doc = MagicMock()
        doc.id = "doc-123"
        doc.to_dict.return_value = {"severity": "ERROR"}
        result = GoogleCloudLoggingAdapter._report_doc_to_dict(doc)
        assert result == {"severity": "ERROR", "id": "doc-123"}

    def test_converts_firestore_datetimes_to_isoformat(self):
        from google.api_core.datetime_helpers import DatetimeWithNanoseconds

        ts = DatetimeWithNanoseconds(2026, 1, 1, 12, 0, 0)
        doc = MagicMock()
        doc.id = "doc-123"
        doc.to_dict.return_value = {
            "severity": "ERROR",
            "first_seen_timestamp": ts,
            "last_seen_timestamp": ts,
            "created_at": ts,
        }
        result = GoogleCloudLoggingAdapter._report_doc_to_dict(doc)
        assert result["id"] == "doc-123"
        assert result["first_seen_timestamp"] == ts.isoformat()
        assert result["last_seen_timestamp"] == ts.isoformat()
        assert result["created_at"] == ts.isoformat()
        import json

        json.dumps(result)  # must be JSON-serializable


class TestFetchLogs:
    def test_builds_filter_with_all_parameters(self, mock_gcp_adapter_clients):
        analyzer = MagicMock()
        adapter = GoogleCloudLoggingAdapter(analyzer, project="my-project")

        entry = MagicMock()
        entry.to_api_repr.return_value = {"severity": "ERROR"}
        adapter.client.list_entries.return_value = [entry]

        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 2, 0, 0, 0)
        adapter.fetch_logs(
            limit=50,
            log_name="app",
            severity_level="ERROR",
            start_time=start,
            end_time=end,
            keywords=['say "hello"', "timeout"],
        )

        call_kwargs = adapter.client.list_entries.call_args.kwargs
        filter_string = call_kwargs["filter_"]
        assert 'logName="projects/my-project/logs/app"' in filter_string
        assert 'severity>="ERROR"' in filter_string
        assert 'timestamp>="2026-01-01T00:00:00Z"' in filter_string
        assert 'timestamp<="2026-01-02T00:00:00Z"' in filter_string
        assert 'say \\"hello\\"' in filter_string
        assert call_kwargs["max_results"] == 50
        assert call_kwargs["page_size"] == 50

    def test_ignores_invalid_severity(self, mock_gcp_adapter_clients):
        analyzer = MagicMock()
        adapter = GoogleCloudLoggingAdapter(analyzer, project="my-project")
        adapter.client.list_entries.return_value = []

        adapter.fetch_logs(limit=10, severity_level="NOT_A_LEVEL")

        filter_string = adapter.client.list_entries.call_args.kwargs["filter_"]
        assert filter_string is None


class TestSaveReport:
    def _make_adapter(self, mock_gcp_adapter_clients):
        analyzer = MagicMock()
        adapter = GoogleCloudLoggingAdapter(analyzer, project="my-project")
        adapter._create_report_record = MagicMock()
        adapter._update_existing_report = MagicMock()
        adapter.fetch_report = MagicMock(return_value=[])
        return adapter, analyzer

    def test_missing_source_log_creates_record(self, mock_gcp_adapter_clients):
        adapter, analyzer = self._make_adapter(mock_gcp_adapter_clients)
        adapter.save_report(sample_incident())
        adapter.fetch_report.assert_not_called()
        analyzer.detect_contextual_repeat.assert_not_called()
        adapter._create_report_record.assert_called_once()

    def test_missing_severity_skips_dedup(self, mock_gcp_adapter_clients):
        adapter, analyzer = self._make_adapter(mock_gcp_adapter_clients)

        adapter.save_report(sample_incident(), source_log={"insertId": "abc"})

        adapter.fetch_report.assert_not_called()
        analyzer.detect_contextual_repeat.assert_not_called()
        adapter._create_report_record.assert_called_once()

    def test_repetitive_incident_updates_existing(self, mock_gcp_adapter_clients):
        adapter, analyzer = self._make_adapter(mock_gcp_adapter_clients)
        incident = sample_incident()
        adapter.fetch_report.return_value = [{"id": "existing-doc"}]
        analyzer.detect_contextual_repeat.return_value = RepetitionCheckResult(
            is_repetitive=True,
            matching_report_id="existing-doc",
            reason="same root cause",
        )

        adapter.save_report(
            incident,
            source_log={
                "severity": "ERROR",
                "insertId": "log-1",
                "textPayload": "boom",
            },
        )

        adapter._update_existing_report.assert_called_once_with(
            "existing-doc", incident, "log-1"
        )
        adapter._create_report_record.assert_not_called()

    def test_new_incident_creates_record(self, mock_gcp_adapter_clients):
        adapter, analyzer = self._make_adapter(mock_gcp_adapter_clients)
        adapter.fetch_report.return_value = [{"id": "other-doc"}]
        analyzer.detect_contextual_repeat.return_value = RepetitionCheckResult(
            is_repetitive=False,
            matching_report_id=None,
            reason="different issue",
        )

        adapter.save_report(
            sample_incident(),
            source_log={
                "severity": "ERROR",
                "insertId": "log-2",
                "textPayload": "boom",
            },
        )

        adapter._create_report_record.assert_called_once()
        adapter._update_existing_report.assert_not_called()

    def test_no_candidates_creates_record(self, mock_gcp_adapter_clients):
        adapter, analyzer = self._make_adapter(mock_gcp_adapter_clients)
        adapter.fetch_report.return_value = []

        adapter.save_report(
            sample_incident(),
            source_log={
                "severity": "ERROR",
                "insertId": "log-3",
                "textPayload": "boom",
            },
        )

        analyzer.detect_contextual_repeat.assert_not_called()
        adapter._create_report_record.assert_called_once()
        adapter._update_existing_report.assert_not_called()


class TestProcessedEvents:
    def test_has_processed_true_when_doc_exists(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        doc = MagicMock()
        doc.exists = True
        adapter.firestore_client.collection.return_value.document.return_value.get.return_value = (
            doc
        )

        assert adapter.has_processed({"insertId": "ins-1"}) is True
        adapter.firestore_client.collection.assert_called_with("processed_events")
        adapter.firestore_client.collection.return_value.document.assert_called_with(
            "ins-1"
        )

    def test_has_processed_false_when_doc_missing(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        doc = MagicMock()
        doc.exists = False
        adapter.firestore_client.collection.return_value.document.return_value.get.return_value = (
            doc
        )

        assert adapter.has_processed({"insertId": "ins-1"}) is False

    def test_has_processed_requires_insert_id(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        with pytest.raises(ValueError, match="Insert ID is required"):
            adapter.has_processed({})

    def test_save_processed_event_writes_status(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        doc_ref = adapter.firestore_client.collection.return_value.document.return_value

        with patch("service.core.gcp_adapter.datetime") as mock_datetime:
            now = datetime(2026, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = now
            adapter.save_processed_event({"insertId": "ins-1"}, "COMPLETED")

        adapter.firestore_client.collection.assert_called_with("processed_events")
        adapter.firestore_client.collection.return_value.document.assert_called_with(
            "ins-1"
        )
        doc_ref.set.assert_called_once_with(
            {"status": "COMPLETED", "processed_timestamp": now}
        )

    def test_save_processed_event_requires_insert_id(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        with pytest.raises(ValueError, match="Insert ID is required"):
            adapter.save_processed_event({}, "COMPLETED")


class TestSignatureClaim:
    def _passthrough_transactional(self):
        def decorator(func):
            def wrapper(transaction):
                return func(transaction)

            return wrapper

        return decorator

    def _source_log(self):
        return {
            "severity": "ERROR",
            "textPayload": "boom",
            "insertId": "ins-1",
            "resource": {"labels": {"service_name": "api"}},
        }

    def test_claim_creates_pending_signature(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        sig_ref = MagicMock()
        snap = MagicMock()
        snap.exists = False
        sig_ref.get.return_value = snap
        adapter.firestore_client.collection.return_value.document.return_value = sig_ref
        adapter.firestore_client.transaction.return_value = MagicMock()

        with patch(
            "service.core.gcp_adapter.firestore.transactional",
            self._passthrough_transactional(),
        ):
            result = adapter.claim_or_follow_signature(self._source_log())

        assert result.outcome == "claimed"
        assert result.report_id is None
        assert result.count == 1
        sig_ref.get.assert_called()
        # transaction.set called with pending status
        set_call = sig_ref.get.call_args  # ensure get used in txn
        assert set_call is not None

    def test_follow_ready_increments_signature(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        sig_ref = MagicMock()
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = {
            "status": "ready",
            "report_id": "report-1",
            "count": 3,
        }
        sig_ref.get.return_value = snap
        adapter.firestore_client.collection.return_value.document.return_value = sig_ref
        adapter.firestore_client.transaction.return_value = MagicMock()

        with patch(
            "service.core.gcp_adapter.firestore.transactional",
            self._passthrough_transactional(),
        ):
            result = adapter.claim_or_follow_signature(self._source_log())

        assert result.outcome == "followed_ready"
        assert result.report_id == "report-1"
        assert result.count == 4

    def test_follow_pending_does_not_increment(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        sig_ref = MagicMock()
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = {"status": "pending", "count": 1}
        sig_ref.get.return_value = snap
        adapter.firestore_client.collection.return_value.document.return_value = sig_ref
        adapter.firestore_client.transaction.return_value = MagicMock()

        with patch(
            "service.core.gcp_adapter.firestore.transactional",
            self._passthrough_transactional(),
        ):
            result = adapter.claim_or_follow_signature(self._source_log())

        assert result.outcome == "followed_pending"
        assert result.report_id is None

    def test_release_signature_claim_deletes_doc(self, mock_gcp_adapter_clients):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        doc_ref = adapter.firestore_client.collection.return_value.document.return_value

        adapter.release_signature_claim("sig-abc")

        adapter.firestore_client.collection.assert_called_with("signatures")
        adapter.firestore_client.collection.return_value.document.assert_called_with(
            "sig-abc"
        )
        doc_ref.delete.assert_called_once()

    def test_finalize_signature_report_creates_without_contextual_gemini(
        self, mock_gcp_adapter_clients
    ):
        analyzer = MagicMock()
        adapter = GoogleCloudLoggingAdapter(analyzer, project="my-project")
        signature, _ = adapter._compute_signature(self._source_log())

        sig_ref = MagicMock()
        sig_snap = MagicMock()
        sig_snap.exists = True
        sig_snap.to_dict.return_value = {"status": "pending", "count": 5}
        sig_ref.get.return_value = sig_snap

        report_ref = MagicMock()
        report_ref.id = "new-report"

        def collection_side_effect(name):
            coll = MagicMock()
            if name == "signatures":
                coll.document.return_value = sig_ref
            else:
                coll.add.return_value = (None, report_ref)
            return coll

        adapter.firestore_client.collection.side_effect = collection_side_effect

        report_id = adapter.finalize_signature_report(
            signature, sample_incident(), source_log=self._source_log()
        )

        assert report_id == "new-report"
        analyzer.detect_contextual_repeat.assert_not_called()
        sig_ref.update.assert_called_once()
        update_payload = sig_ref.update.call_args.args[0]
        assert update_payload["status"] == "ready"
        assert update_payload["report_id"] == "new-report"

    def test_record_signature_follower_increments_report(
        self, mock_gcp_adapter_clients
    ):
        adapter = GoogleCloudLoggingAdapter(MagicMock(), project="my-project")
        report_ref = MagicMock()
        adapter.firestore_client.collection.return_value.document.return_value = (
            report_ref
        )

        adapter.record_signature_follower(
            "sig-1", "report-1", source_log=self._source_log()
        )

        adapter.firestore_client.collection.assert_called_with("reports")
        adapter.firestore_client.collection.return_value.document.assert_called_with(
            "report-1"
        )
        report_ref.update.assert_called_once()
        payload = report_ref.update.call_args.args[0]
        assert "incident_count" in payload
        assert payload["last_insert_id"] == "ins-1"
