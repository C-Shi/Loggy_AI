from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LogIngestor(ABC):
    @abstractmethod
    def fetch_logs(self, limit: int) -> List[Dict[str, Any]]:
        pass
