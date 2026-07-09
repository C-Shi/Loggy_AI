class LogPayloadLimitError(Exception):
    """Raised when a log batch exceeds configured entry or byte limits."""

    def __init__(
        self,
        message: str,
        entry_count: int | None = None,
        payload_bytes: int | None = None,
        max_log_entries: int | None = None,
        max_payload_bytes: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.entry_count = entry_count
        self.payload_bytes = payload_bytes
        self.max_log_entries = max_log_entries
        self.max_payload_bytes = max_payload_bytes

    def __str__(self):
        base_msg = f"[LogPayloadLimitError] {self.message}"
        if self.entry_count is not None and self.max_log_entries is not None:
            return (
                f"{base_msg} (entries: {self.entry_count}, "
                f"limit: {self.max_log_entries})"
            )
        if self.payload_bytes is not None and self.max_payload_bytes is not None:
            return (
                f"{base_msg} (payload: {self.payload_bytes} bytes, "
                f"limit: {self.max_payload_bytes} bytes)"
            )
        return base_msg


class PromptValidationError(Exception):
    """Base exception raised for failures within the AI Orchestration prompt lifecycle."""
    def __init__(self, message: str, payload_size: int = None, raw_payload: list = None):
        super().__init__(message)
        self.message = message
        self.payload_size = payload_size
        self.raw_payload = raw_payload

    def __str__(self):
        base_msg = f"[PromptValidationError] {self.message}"
        if self.payload_size is not None:
            return f"{base_msg} (Payload Size: {self.payload_size} items)"
        return base_msg