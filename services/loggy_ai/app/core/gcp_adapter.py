from typing import Any, Dict, List, Optional
from datetime import datetime
from google.cloud import logging
from google.auth import default
from app.core.base import LogIngestor
from app.core.google_ai import GeminiLogAnalyzer


class GoogleCloudLoggingAdapter(LogIngestor):
    """Concrete adapter handling the plumbing with GCP Cloud Logging."""

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

    def __init__(self, project: str = None) -> None:
        # initalize Logging Client without Credential. Rely on ADC behavior
        _, project_id = default()
        self.project = project_id

        if project:
            self.project = project

        self.client = logging.Client(project=self.project)
        self.analyzer = GeminiLogAnalyzer()

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

    def analyze(self, logs) -> dict:
        response = self.analyzer.analyze_logs(logs, "Return in pure string, do not return json")
        return response.parsed
