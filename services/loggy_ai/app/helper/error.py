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