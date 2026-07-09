import pytest

from service.helper.log_redactor import LogRedactor


@pytest.fixture
def redactor():
    return LogRedactor()


class TestRedactValue:
    def test_redacts_jwt(self, redactor):
        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redactor._redact_value(f"Bearer {token}")
        assert "[REDACTED_JWT]" in result
        assert token not in result

    def test_redacts_email(self, redactor):
        result = redactor._redact_value("Contact user@example.com for help")
        assert result == "Contact [REDACTED_EMAIL] for help"

    def test_redacts_credit_card(self, redactor):
        result = redactor._redact_value("Card 4111 1111 1111 1111 declined")
        assert "[REDACTED_CREDIT_CARD]" in result

    def test_redacts_api_key_colon_format(self, redactor):
        result = redactor._redact_value('api_key: "abcdefghijklmnop"')
        assert '[REDACTED_SECRET]"' in result

    def test_returns_non_string_unchanged(self, redactor):
        assert redactor._redact_value(123) == 123


class TestSanitizeLogBatch:
    def test_extracts_json_payload_message(self, redactor):
        logs = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "severity": "ERROR",
                "resource": {"type": "cloud_run_revision"},
                "jsonPayload": {"message": "user@example.com failed"},
            }
        ]
        result = redactor.sanitize_log_batch(logs)
        assert len(result) == 1
        assert "[REDACTED_EMAIL]" in result[0]["message"]
        assert result[0]["severity"] == "ERROR"

    def test_extracts_text_payload(self, redactor):
        logs = [{"textPayload": "plain text error", "severity": "WARNING"}]
        result = redactor.sanitize_log_batch(logs)
        assert result[0]["message"] == "plain text error"

    def test_skips_non_dict_entries(self, redactor):
        assert redactor.sanitize_log_batch(["not a dict", None]) == []

    def test_normalizes_whitespace(self, redactor):
        logs = [{"textPayload": "line one\n\n  line two"}]
        result = redactor.sanitize_log_batch(logs)
        assert result[0]["message"] == "line one line two"
