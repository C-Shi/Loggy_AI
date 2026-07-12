from service.helper.error import LogPayloadLimitError, PromptValidationError


class TestLogPayloadLimitError:
    def test_str_with_entry_metadata(self):
        err = LogPayloadLimitError(
            "too many entries",
            entry_count=600,
            max_log_entries=500,
        )
        assert "too many entries" in str(err)
        assert "entries: 600" in str(err)
        assert "limit: 500" in str(err)

    def test_str_with_payload_metadata(self):
        err = LogPayloadLimitError(
            "payload too large",
            payload_bytes=1024,
            max_payload_bytes=512,
        )
        assert "payload: 1024 bytes" in str(err)
        assert "limit: 512 bytes" in str(err)

    def test_str_without_metadata(self):
        err = LogPayloadLimitError("generic limit error")
        assert str(err) == "[LogPayloadLimitError] generic limit error"


class TestPromptValidationError:
    def test_str_with_payload_size(self):
        err = PromptValidationError("unsafe prompt", payload_size=10)
        assert "unsafe prompt" in str(err)
        assert "Payload Size: 10 items" in str(err)

    def test_str_without_payload_size(self):
        err = PromptValidationError("empty instruction")
        assert str(err) == "[PromptValidationError] empty instruction"
