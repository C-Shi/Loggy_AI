from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from service.core.gcp_adapter import GoogleCloudLoggingAdapter
from service.core.models import LogAnalysisReport, RepetitionCheckResult
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

    def test_empty_incidents_is_noop(self, mock_gcp_adapter_clients):
        adapter, _ = self._make_adapter(mock_gcp_adapter_clients)
        adapter.save_report(LogAnalysisReport(incidents=[]))
        adapter._create_report_record.assert_not_called()

    def test_missing_severity_skips_dedup(self, mock_gcp_adapter_clients):
        adapter, analyzer = self._make_adapter(mock_gcp_adapter_clients)
        report = LogAnalysisReport(incidents=[sample_incident()])

        adapter.save_report(report, source_log={"insertId": "abc"})

        adapter.fetch_report.assert_not_called()
        analyzer.check_repetition.assert_not_called()
        adapter._create_report_record.assert_called_once()

    def test_repetitive_incident_updates_existing(self, mock_gcp_adapter_clients):
        adapter, analyzer = self._make_adapter(mock_gcp_adapter_clients)
        incident = sample_incident()
        report = LogAnalysisReport(incidents=[incident])
        adapter.fetch_report.return_value = [{"id": "existing-doc"}]
        analyzer.check_repetition.return_value = RepetitionCheckResult(
            is_repetitive=True,
            matching_report_id="existing-doc",
            reason="same root cause",
        )

        adapter.save_report(
            report,
            source_log={"severity": "ERROR", "insertId": "log-1"},
        )

        adapter._update_existing_report.assert_called_once_with(
            "existing-doc", incident, "log-1"
        )
        adapter._create_report_record.assert_not_called()

    def test_new_incident_creates_record(self, mock_gcp_adapter_clients):
        adapter, analyzer = self._make_adapter(mock_gcp_adapter_clients)
        report = LogAnalysisReport(incidents=[sample_incident()])
        adapter.fetch_report.return_value = [{"id": "other-doc"}]
        analyzer.check_repetition.return_value = RepetitionCheckResult(
            is_repetitive=False,
            matching_report_id=None,
            reason="different issue",
        )

        adapter.save_report(
            report,
            source_log={"severity": "ERROR", "insertId": "log-2"},
        )

        adapter._create_report_record.assert_called_once()
        adapter._update_existing_report.assert_not_called()
