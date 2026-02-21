"""
Tests for api/chat_service.py

Unit tests: all external calls (httpx, Azure identity, AsyncAzureOpenAI) are mocked.
Integration tests: connect to a real Azure OpenAI endpoint via managed identity.
  Run with:  pytest tests/test_chat_service.py -m integration -v
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

AZURE_ENDPOINT = "https://datacopilothub8882317788.cognitiveservices.azure.com/"
AZURE_DEPLOYMENT = "gpt-5.2-chat"
AZURE_API_VERSION = "2025-01-01-preview"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_mock(json_payload: dict, status_code: int = 200):
    """Return a mock that behaves like an httpx response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_payload
    response.raise_for_status = MagicMock()
    return response


def _make_async_client_mock(response: MagicMock) -> MagicMock:
    """Return an async context-manager mock that delegates HTTP verbs to `response`."""
    client = AsyncMock()
    # All verb methods return the same response object
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.put = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    # Support `async with httpx.AsyncClient() as client:`
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def azure_env(monkeypatch):
    """Inject Azure env vars for the duration of a test."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", AZURE_ENDPOINT)
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", AZURE_DEPLOYMENT)
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", AZURE_API_VERSION)


@pytest.fixture()
def no_azure_env(monkeypatch):
    """Ensure Azure env vars are absent."""
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)


# ---------------------------------------------------------------------------
# Unit: initialisation
# ---------------------------------------------------------------------------

class TestChatServiceInit:
    """Verify __init__ configures the Azure client correctly."""

    @patch("api.chat_service.AsyncAzureOpenAI")
    @patch("api.chat_service.get_bearer_token_provider")
    @patch("api.chat_service.DefaultAzureCredential")
    def test_azure_client_created_when_endpoint_set(
        self, mock_cred_cls, mock_token_provider_fn, mock_azure_cls, azure_env
    ):
        from api.chat_service import ChatService

        mock_token = MagicMock(name="token_provider")
        mock_token_provider_fn.return_value = mock_token
        mock_client = MagicMock(name="azure_client")
        mock_azure_cls.return_value = mock_client

        svc = ChatService()

        # DefaultAzureCredential instantiated once
        mock_cred_cls.assert_called_once()
        # Token provider created with cognitiveservices scope
        mock_token_provider_fn.assert_called_once_with(
            mock_cred_cls.return_value,
            "https://cognitiveservices.azure.com/.default",
        )
        # AsyncAzureOpenAI created with correct kwargs
        mock_azure_cls.assert_called_once_with(
            api_version=AZURE_API_VERSION,
            azure_endpoint=AZURE_ENDPOINT,
            azure_ad_token_provider=mock_token,
        )
        assert svc._azure_client is mock_client
        assert svc.azure_deployment == AZURE_DEPLOYMENT
        assert svc.azure_api_version == AZURE_API_VERSION

    @patch("api.chat_service.AsyncAzureOpenAI")
    @patch("api.chat_service.DefaultAzureCredential")
    def test_azure_client_none_when_endpoint_missing(
        self, mock_cred_cls, mock_azure_cls, no_azure_env
    ):
        from api.chat_service import ChatService

        svc = ChatService()

        mock_cred_cls.assert_not_called()
        mock_azure_cls.assert_not_called()
        assert svc._azure_client is None

    @patch("api.chat_service.DefaultAzureCredential")
    @patch("api.chat_service.AsyncAzureOpenAI")
    def test_auth_header_set_when_password_present(
        self, _azure, _cred, monkeypatch, no_azure_env
    ):
        monkeypatch.setenv("OPEN_NOTEBOOK_PASSWORD", "supersecret")
        from api.chat_service import ChatService

        svc = ChatService()

        assert svc.headers == {"Authorization": "Bearer supersecret"}

    @patch("api.chat_service.DefaultAzureCredential")
    @patch("api.chat_service.AsyncAzureOpenAI")
    def test_no_auth_header_when_password_absent(
        self, _azure, _cred, monkeypatch, no_azure_env
    ):
        monkeypatch.delenv("OPEN_NOTEBOOK_PASSWORD", raising=False)
        from api.chat_service import ChatService

        svc = ChatService()

        assert svc.headers == {}

    @patch("api.chat_service.DefaultAzureCredential")
    @patch("api.chat_service.AsyncAzureOpenAI")
    def test_deployment_defaults(self, _azure, _cred, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", AZURE_ENDPOINT)
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
        from api.chat_service import ChatService

        svc = ChatService()

        assert svc.azure_deployment == "gpt-5.2-chat"
        assert svc.azure_api_version == "2025-01-01-preview"


# ---------------------------------------------------------------------------
# Unit: session CRUD (mocked httpx)
# ---------------------------------------------------------------------------

class TestChatServiceSessions:
    """Test session management methods against a mocked httpx transport."""

    @pytest.fixture(autouse=True)
    def _service(self, no_azure_env):
        """Create a ChatService with no Azure client for session tests."""
        with patch("api.chat_service.DefaultAzureCredential"), \
             patch("api.chat_service.AsyncAzureOpenAI"):
            from api.chat_service import ChatService
            self.svc = ChatService()
            self.svc.base_url = "http://testserver"

    @pytest.mark.asyncio
    async def test_get_sessions(self):
        payload = [{"id": "session:1", "notebook_id": "notebook:abc"}]
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.get_sessions("notebook:abc")

        client_mock.get.assert_awaited_once_with(
            "http://testserver/api/chat/sessions",
            params={"notebook_id": "notebook:abc"},
            headers=self.svc.headers,
        )
        assert result == payload

    @pytest.mark.asyncio
    async def test_create_session_minimal(self):
        payload = {"id": "session:2", "notebook_id": "notebook:abc"}
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.create_session("notebook:abc")

        client_mock.post.assert_awaited_once_with(
            "http://testserver/api/chat/sessions",
            json={"notebook_id": "notebook:abc"},
            headers=self.svc.headers,
        )
        assert result == payload

    @pytest.mark.asyncio
    async def test_create_session_with_title_and_model(self):
        payload = {"id": "session:3"}
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.create_session(
                "notebook:abc", title="Research", model_override="model:xyz"
            )

        _, kwargs = client_mock.post.call_args
        assert kwargs["json"] == {
            "notebook_id": "notebook:abc",
            "title": "Research",
            "model_override": "model:xyz",
        }
        assert result == payload

    @pytest.mark.asyncio
    async def test_get_session(self):
        payload = {"id": "session:5", "messages": []}
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.get_session("session:5")

        client_mock.get.assert_awaited_once_with(
            "http://testserver/api/chat/sessions/session:5",
            headers=self.svc.headers,
        )
        assert result == payload

    @pytest.mark.asyncio
    async def test_update_session_title(self):
        payload = {"id": "session:5", "title": "New Title"}
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.update_session("session:5", title="New Title")

        client_mock.put.assert_awaited_once_with(
            "http://testserver/api/chat/sessions/session:5",
            json={"title": "New Title"},
            headers=self.svc.headers,
        )
        assert result == payload

    @pytest.mark.asyncio
    async def test_update_session_raises_when_no_fields(self):
        with pytest.raises(ValueError, match="At least one field"):
            await self.svc.update_session("session:5")

    @pytest.mark.asyncio
    async def test_delete_session(self):
        payload = {"deleted": True}
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.delete_session("session:5")

        client_mock.delete.assert_awaited_once_with(
            "http://testserver/api/chat/sessions/session:5",
            headers=self.svc.headers,
        )
        assert result == payload

    @pytest.mark.asyncio
    async def test_get_sessions_propagates_http_error(self):
        resp_mock = _make_http_mock({}, status_code=500)
        resp_mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            with pytest.raises(httpx.HTTPStatusError):
                await self.svc.get_sessions("notebook:abc")


# ---------------------------------------------------------------------------
# Unit: execute_chat and build_context
# ---------------------------------------------------------------------------

class TestChatServiceExecution:
    """Test execute_chat and build_context against a mocked httpx transport."""

    @pytest.fixture(autouse=True)
    def _service(self, no_azure_env):
        with patch("api.chat_service.DefaultAzureCredential"), \
             patch("api.chat_service.AsyncAzureOpenAI"):
            from api.chat_service import ChatService
            self.svc = ChatService()
            self.svc.base_url = "http://testserver"

    @pytest.mark.asyncio
    async def test_execute_chat_minimal(self):
        payload = {"message": {"role": "assistant", "content": "Hello!"}}
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.execute_chat(
                session_id="session:1",
                message="Hello",
                context={},
            )

        _, kwargs = client_mock.post.call_args
        assert kwargs["json"] == {
            "session_id": "session:1",
            "message": "Hello",
            "context": {},
        }
        assert "model_override" not in kwargs["json"]
        assert result == payload

    @pytest.mark.asyncio
    async def test_execute_chat_with_model_override(self):
        payload = {"message": {"role": "assistant", "content": "Hi"}}
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.execute_chat(
                session_id="session:1",
                message="Hi",
                context={"sources": []},
                model_override="model:azure-gpt",
            )

        _, kwargs = client_mock.post.call_args
        assert kwargs["json"]["model_override"] == "model:azure-gpt"
        assert result == payload

    @pytest.mark.asyncio
    async def test_execute_chat_uses_long_read_timeout(self):
        """execute_chat must use a 600s read timeout for slow local/remote LLMs."""
        resp_mock = _make_http_mock({})
        client_mock = _make_async_client_mock(resp_mock)

        captured_timeout = {}

        def capture_client(**kwargs):
            captured_timeout.update(kwargs)
            return client_mock

        with patch("api.chat_service.httpx.AsyncClient", side_effect=capture_client):
            await self.svc.execute_chat("s:1", "hi", {})

        timeout = captured_timeout.get("timeout")
        assert timeout is not None
        assert timeout.read == 600.0
        assert timeout.connect == 10.0

    @pytest.mark.asyncio
    async def test_build_context(self):
        payload = {"context": "assembled context text"}
        resp_mock = _make_http_mock(payload)
        client_mock = _make_async_client_mock(resp_mock)
        config = {"max_tokens": 4096, "sources": ["source:1"]}

        with patch("api.chat_service.httpx.AsyncClient", return_value=client_mock):
            result = await self.svc.build_context("notebook:abc", config)

        client_mock.post.assert_awaited_once_with(
            "http://testserver/api/chat/context",
            json={"notebook_id": "notebook:abc", "context_config": config},
            headers=self.svc.headers,
        )
        assert result == payload


# ---------------------------------------------------------------------------
# Integration: real Azure OpenAI via managed identity
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestChatServiceAzureIntegration:
    """
    Live tests against Azure OpenAI using DefaultAzureCredential.

    Prerequisites:
      - Run in an environment with a valid managed identity or az login session.
      - The deployment must be reachable and active.

    Run:
      pytest tests/test_chat_service.py -m integration -v
    """

    @pytest.fixture(autouse=True)
    def _set_azure_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", AZURE_ENDPOINT)
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", AZURE_DEPLOYMENT)
        monkeypatch.setenv("AZURE_OPENAI_API_VERSION", AZURE_API_VERSION)
        # Do NOT patch credentials — use real DefaultAzureCredential
        from api.chat_service import ChatService
        self.svc = ChatService()

    def test_azure_client_is_initialized(self):
        """Azure client must be non-None when endpoint is configured."""
        assert self.svc._azure_client is not None

    def test_deployment_and_version_match_env(self):
        assert self.svc.azure_deployment == AZURE_DEPLOYMENT
        assert self.svc.azure_api_version == AZURE_API_VERSION

    @pytest.mark.asyncio
    async def test_direct_azure_completion(self):
        """Send a real completion request and verify the response structure.

        gpt-5.2-chat is a reasoning model: it may consume all tokens on internal
        reasoning, leaving content as ''.  We assert the round-trip succeeded
        (choices present, content not None, finish_reason set) rather than
        requiring a non-empty content string.
        """
        client = self.svc._azure_client
        assert client is not None, "Azure client must be initialized"

        response = await client.chat.completions.create(
            model=self.svc.azure_deployment,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Reply with exactly the word: PONG"},
            ],
            max_completion_tokens=256,  # give reasoning model room to work
        )

        assert response.choices, "Response must have at least one choice"
        choice = response.choices[0]
        # content may be '' for reasoning models; None would indicate a parse error
        assert choice.message.content is not None
        assert choice.finish_reason in ("stop", "length")

    @pytest.mark.asyncio
    async def test_azure_completion_returns_usage(self):
        """Usage metadata (tokens) must be present in the response."""
        client = self.svc._azure_client
        assert client is not None

        response = await client.chat.completions.create(
            model=self.svc.azure_deployment,
            messages=[{"role": "user", "content": "Say hi"}],
            max_completion_tokens=256,
        )

        assert hasattr(response, "usage")
        assert response.usage.total_tokens > 0

    @pytest.mark.asyncio
    async def test_azure_completion_finish_reason(self):
        """Finish reason must be stop or length for a normal completion."""
        client = self.svc._azure_client
        assert client is not None

        response = await client.chat.completions.create(
            model=self.svc.azure_deployment,
            messages=[{"role": "user", "content": "Say the word OK"}],
            max_completion_tokens=256,
        )

        assert response.choices[0].finish_reason in ("stop", "length")
