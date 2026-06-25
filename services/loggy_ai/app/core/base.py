from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


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
    def analyze(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass