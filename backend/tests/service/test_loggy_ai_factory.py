import pytest

from service import LoggyAI
from service.core.gcp_adapter import GoogleCloudLoggingAdapter


class TestLoggyAIFactory:
    def test_create_google_provider(self, mock_gcp_adapter_clients, mock_genai_client):
        adapter = LoggyAI.create("google")
        assert isinstance(adapter, GoogleCloudLoggingAdapter)

    def test_create_google_provider_case_insensitive(self, mock_gcp_adapter_clients, mock_genai_client):
        adapter = LoggyAI.create("Google")
        assert isinstance(adapter, GoogleCloudLoggingAdapter)

    def test_unsupported_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported provider"):
            LoggyAI.create("aws")
