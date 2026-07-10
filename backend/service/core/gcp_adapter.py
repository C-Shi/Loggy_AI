import logging
import re
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.auth import default
from google.cloud import firestore, logging as cloud_logging

from service.core.base import LogIngestor
from service.core.models import LogAnalysisReport, LogAnalysisResponse
from service.core.base import GenAIAnalyzer
import service.helper.log_redactor as log_redactor

logger = logging.getLogger(__name__)

_UNSET = object()

_PERIOD_PATTERN = re.compile(
    r"^\s*(\d+)\s*"
    r"(s|sec|secs|second|seconds|"
    r"m|min|mins|minute|minutes|"
    r"h|hr|hrs|hour|hours|"
    r"d|day|days)\s*$",
    re.IGNORECASE,
)

_PERIOD_UNITS = {
    "s": "seconds",
    "sec": "seconds",
    "secs": "seconds",
    "second": "seconds",
    "seconds": "seconds",
    "m": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "minute": "minutes",
    "minutes": "minutes",
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
    "d": "days",
    "day": "days",
    "days": "days",
}


class GoogleCloudLoggingAdapter(LogIngestor):
    """
    GCP adapter for Cloud Logging ingestion, Gemini analysis, and Firestore report storage.

    Uses Application Default Credentials for all Google Cloud clients.
    """

    REPORT_DATABASE = "loggy-ai-report"
    REPORT_COLLECTION = "reports"
    PROCESSED_EVENTS_COLLECTION = "processed_events"

    SEVERITY_LEVEL = [
        "DEBUG",
        "INFO",
        "NOTICE",
        "WARNING",
        "ERROR",
        "CRITICAL",
        "ALERT",
        "EMERGENCY",
    ]

    def __init__(self, ai_tool: GenAIAnalyzer, project: str = None) -> None:
        """
        Initialize Cloud Logging, Firestore, and AI analyzer clients.

        Args:
            project: Optional GCP project ID. Defaults to ADC project.
            ai_tool: An instance of GenAIAnalyzer.
        """
        # Initialize clients without explicit credentials; rely on ADC.
        _, project_id = default()
        self.project = project_id

        if project:
            self.project = project

        self.client = cloud_logging.Client(project=self.project)
        self.firestore_client = firestore.Client(
            project=self.project, database=self.REPORT_DATABASE
        )
        self.analyzer = ai_tool
        self.redactor = log_redactor.LogRedactor()

    @staticmethod
    def _parse_period(period: str) -> timedelta:
        """Parse a lookback period string such as '5min', '1h', or '1 day'."""
        match = _PERIOD_PATTERN.match(period)
        if not match:
            raise ValueError(
                "Invalid period format. Use values like '5min', '1h', '2h', or '1 day'."
            )

        amount = int(match.group(1))
        if amount < 1:
            raise ValueError("Period must be at least 1.")

        unit = _PERIOD_UNITS[match.group(2).lower()]
        return timedelta(**{unit: amount})

    @staticmethod
    def _report_doc_to_dict(doc: firestore.DocumentSnapshot) -> Dict[str, Any]:
        """Convert a Firestore document snapshot to a plain dictionary with its ID."""
        data = doc.to_dict() or {}
        data["id"] = doc.id
        return data

    def fetch_report(
        self,
        period: str,
        severity: Any = _UNSET,
        service_name: Any = _UNSET,
    ) -> List[Dict[str, Any]]:
        """
        Fetch AI analysis reports from Firestore for the given lookback period.

        Args:
            period: Lookback window (e.g. "5min", "1h", "2h", "1d", "1 day").
            severity: Optional GCP log severity level filter (e.g. "ERROR").
            service_name: Optional service name filter. Pass ``None`` to match
                reports with no service name.

        Returns:
            List of report documents as dictionaries, newest first.
            Each document is expected to include a UTC ``created_at`` timestamp.
        """
        start_time = datetime.now(timezone.utc) - self._parse_period(period)
        query = self.firestore_client.collection(self.REPORT_COLLECTION)

        if service_name is not _UNSET:
            query = query.where(
                filter=firestore.FieldFilter("service_name", "==", service_name)
            )

        if severity is not _UNSET:
            query = query.where(
                filter=firestore.FieldFilter("severity", "==", severity)
            )

        query = query.where(
            filter=firestore.FieldFilter("created_at", ">=", start_time)
        ).order_by("created_at", direction=firestore.Query.DESCENDING)
        return [self._report_doc_to_dict(doc) for doc in query.stream()]

    def _create_report_record(
        self, record: Dict[str, Any], created_at: datetime
    ) -> None:
        record["incident_count"] = 1
        record["created_at"] = created_at
        self.firestore_client.collection(self.REPORT_COLLECTION).add(record)

    def _update_existing_report(
        self, doc_id: str, incident: LogAnalysisResponse, insert_id: str | None
    ) -> None:
        update_fields = {
            "incident_count": firestore.Increment(1),
            "last_seen_timestamp": incident.last_seen_timestamp,
        }
        if insert_id:
            update_fields["last_insert_id"] = insert_id
        self.firestore_client.collection(self.REPORT_COLLECTION).document(
            doc_id
        ).update(update_fields)

    def _candidate_ids(self, candidates: List[Dict[str, Any]]) -> set[str]:
        return {candidate["id"] for candidate in candidates if candidate.get("id")}

    def save_report(
        self, report: LogAnalysisResponse, source_log: dict | None = None
    ) -> None:
        """
        Persist each incident in an analysis report to Firestore.

        Checks recent reports for repetition before creating a new document.

        Args:
            report: Structured analysis output from the AI analyzer.
            source_log: Optional source GCP log entry used to inject severity.
        """

        created_at = datetime.now(timezone.utc)
        gcp_severity = ((source_log or {}).get("severity") or "").upper()
        insert_id = (source_log or {}).get("insertId")
        log_message = self.redactor.sanitize_single_log(source_log)["message"]

        record = report.model_dump()
        record["severity"] = gcp_severity

        string_to_hash = f"{record['service_name']}|{gcp_severity}|{log_message}"
        signature = hashlib.md5(string_to_hash.encode()).hexdigest()
        record["signature"] = signature
        record["log_message"] = log_message

        if insert_id:
            record["last_insert_id"] = insert_id

        if not gcp_severity:
            logger.warning(
                "Missing GCP severity on source log; skipping dedup for incident"
            )
            self._create_report_record(record, created_at)
        else:
            candidates = self.fetch_report(
                "2h", severity=gcp_severity, service_name=record["service_name"]
            )

            if candidates:
                result = self.analyzer.check_repetition(report, candidates)
                matching_id = result.matching_report_id
                if (
                    result.is_repetitive
                    and matching_id
                    and matching_id in self._candidate_ids(candidates)
                ):
                    self._update_existing_report(matching_id, report, insert_id)
            else:
                self._create_report_record(record, created_at)

    def fetch_logs(
        self,
        limit: int,
        log_name: Optional[str] = None,
        severity_level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        keywords: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches logs from Google Cloud Logging based on various filtering criteria.

        Args:
            limit (int): The maximum number of log entries to retrieve.
            log_name (Optional[str]): The specific log name to filter by.
                                       E.g., "syslog", "cloudtrail.googleapis.com%2Factivity".
                                       The full logName format internally becomes
                                       "projects/project/logs/LOG_ID".
            severity_level (Optional[str]): The minimum severity level to filter by.
                                            Valid values include "DEBUG", "INFO", "NOTICE",
                                            "WARNING", "ERROR", "CRITICAL", "ALERT", "EMERGENCY".
                                            Logs with severity equal to or higher than the specified
                                            level will be returned.
            start_time (Optional[datetime]): The earliest timestamp for log entries to retrieve.
                                             Logs older than this time will be excluded.
            end_time (Optional[datetime]): The latest timestamp for log entries to retrieve.
                                           Logs newer than this time will be excluded. By Default 24hour is applied
            keywords (Optional[List[str]]): A list of keywords to search for within log entry payloads
                                            (textPayload or jsonPayload.message). Multiple keywords
                                            will be combined with an 'AND' operator.

        Returns:
            List[StructEntry | TextEntry]: A list of fetched log entries,
                                          which can be either structured (JSON) or plain text.
        """
        filters = []

        # Construct filter string based on provided parameters
        if log_name:
            # Assuming log_name is the ID part (e.g., "syslog", "cloudtrail.googleapis.com%2Factivity")
            # The full logName format for filtering is projects/project/logs/LOG_ID
            filters.append(f'logName="projects/{self.project}/logs/{log_name}"')

        if (
            severity_level
            and severity_level in GoogleCloudLoggingAdapter.SEVERITY_LEVEL
        ):
            filters.append(f'severity>="{severity_level.upper()}"')

        if start_time and isinstance(start_time, datetime):
            # Convert datetime to ISO 8601 string with 'Z' for UTC, as expected by Cloud Logging filter
            filters.append(f'timestamp>="{start_time.isoformat()}Z"')

        if end_time and isinstance(end_time, datetime):
            filters.append(f'timestamp<="{end_time.isoformat()}Z"')

        # @TODO add option to pass in callback
        if keywords:
            keyword_filters = []
            for keyword in keywords:
                # Escape double quotes within keywords to prevent filter syntax errors
                escaped_keyword = keyword.replace('"', '\\"')
                keyword_filters.append(f" {escaped_keyword} ")
            filters.append(
                f'({" OR ".join(keyword_filters)})'
            )  # Combine multiple keywords with AND for more restrictive search

        gcp_filter_string = " AND ".join(filters) if filters else None

        fetched_logs: List[Dict[str, Any]] = []
        resource_names = [f"projects/{self.project}"]

        for entry in self.client.list_entries(
            resource_names=resource_names,
            filter_=gcp_filter_string,
            order_by="timestamp desc",  # Default to newest logs first
            max_results=limit,
            page_size=min(
                limit, 100
            ),  # Fetch up to 'limit' results, but use a reasonable page size
        ):
            fetched_logs.append(entry.to_api_repr())
            if len(fetched_logs) >= limit:
                break

        return fetched_logs

    def analyze(self, logs: List[Dict[str, Any]]) -> LogAnalysisReport:
        """Run AI analysis on a batch of Cloud Logging entries."""
        return self.analyzer.analyze_logs(logs)

    def has_processed(self, log: Dict[str, Any]) -> bool:
        """Check if the given log has been processed before."""
        insert_id = log.get("insertId")
        if not insert_id:
            raise ValueError("Insert ID is required to check if log has been processed")

        return self.firestore_client.collection(self.PROCESSED_EVENTS_COLLECTION).document(insert_id).get().exists

    def save_processed_event(self, log: Dict[str, Any], status: str) -> None:
        """Save the given log as a processed event."""
        insert_id = log.get("insertId")
        if not insert_id:
            raise ValueError("Insert ID is required to save a processed event")

        self.firestore_client.collection(self.PROCESSED_EVENTS_COLLECTION).document(insert_id).set({
            "status": status,
            "processed_timestamp": datetime.now(timezone.utc)
        })
