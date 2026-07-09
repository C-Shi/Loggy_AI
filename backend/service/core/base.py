from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

from service.core.models import LogAnalysisReport, LogAnalysisResponse, RepetitionCheckResult, ValidationResult


class LogIngestor(ABC):
    @abstractmethod
    def fetch_logs(
        self,
        limit: int,
        log_name: Optional[str] = None,
        severity_level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        keywords: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_report(self, report: LogAnalysisReport, source_log: dict | None = None) -> None:
        pass

    @abstractmethod
    def fetch_report(self, period: str, severity: Optional[str] = None, service_name: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def analyze(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def has_processed(self, log: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def save_processed_event(self, log: Dict[str, Any], status: str) -> None:
        pass

class GenAIAnalyzer(ABC):
    @abstractmethod
    def analyze_logs(self, logs: List[Any], instruction: Optional[str] = None) -> LogAnalysisReport:
        pass

    @abstractmethod
    def check_repetition(self, incident: LogAnalysisResponse, candidates: List[Dict[str, Any]]) -> RepetitionCheckResult:
        pass

    @abstractmethod
    def validate_prompt(self, prompt: str) -> ValidationResult:
        pass