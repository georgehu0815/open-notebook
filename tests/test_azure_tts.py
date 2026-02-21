"""
Tests for Azure AD (managed identity) TTS model and podcast TTS integration.

Unit tests use mocks and run without Azure credentials.
Integration tests call the real Azure TTS endpoint and require:
  - AZURE_OPENAI_ENDPOINT_TTS (or AZURE_OPENAI_ENDPOINT)
  - AZURE_OPENAI_API_VERSION_TTS
  - AZURE_MANAGED_IDENTITY_CLIENT_ID (or az login / workload identity)

Run unit tests only:
    uv run pytest tests/test_azure_tts.py -v

Run integration tests:
    uv run pytest tests/test_azure_tts.py -m integration -v
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants matching the dev Azure TTS deployment
# ---------------------------------------------------------------------------
AZURE_TTS_ENDPOINT = "https://datacopilothub8882317788.openai.azure.com"
AZURE_TTS_DEPLOYMENT = "gpt-4o-mini-tts-3"
AZURE_TTS_API_VERSION = "2025-03-01-preview"
AZURE_MANAGED_IDENTITY_CLIENT_ID = "c9427d44-98e2-406a-9527-f7fa7059f984"
EXPECTED_VOICE = "nova"


# ===========================================================================
# TEST SUITE 1 — AzureAdTtsModel initialisation
# ===========================================================================


class TestAzureAdTtsModelInit:
    """Verify construction and auth header generation without hitting Azure."""

    def _make_model(self, extra_kwargs=None):
        """Build model with mocked Azure credential."""
        mock_token_provider = MagicMock(return_value="fake-bearer-token")

        with patch(
            "open_notebook.ai.azure_ad_tts.DefaultAzureCredential"
        ) as MockCred, patch(
            "open_notebook.ai.azure_ad_tts.get_bearer_token_provider",
            return_value=mock_token_provider,
        ):
            from open_notebook.ai.azure_ad_tts import AzureAdTtsModel

            kwargs = {
                "azure_endpoint": AZURE_TTS_ENDPOINT,
                "api_version": AZURE_TTS_API_VERSION,
                **(extra_kwargs or {}),
            }
            model = AzureAdTtsModel(model_name=AZURE_TTS_DEPLOYMENT, **kwargs)

        return model, mock_token_provider, MockCred

    def test_provider_name(self):
        model, _, _ = self._make_model()
        assert model.provider == "azureopenai"

    def test_deployment_name(self):
        model, _, _ = self._make_model()
        assert model.deployment_name == AZURE_TTS_DEPLOYMENT

    def test_endpoint_set(self):
        model, _, _ = self._make_model()
        assert AZURE_TTS_ENDPOINT.rstrip("/") in model.azure_endpoint

    def test_api_version_set(self):
        model, _, _ = self._make_model()
        assert model.api_version == AZURE_TTS_API_VERSION

    def test_bearer_header_not_api_key_header(self):
        """_get_headers() must return Authorization: Bearer, NOT api-key."""
        model, mock_token_provider, _ = self._make_model()
        headers = model._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer fake-bearer-token"
        assert "api-key" not in headers

    def test_token_provider_called_on_each_header_call(self):
        """Token provider is called every time headers are requested (auto-refresh)."""
        model, mock_token_provider, _ = self._make_model()
        model._get_headers()
        model._get_headers()
        assert mock_token_provider.call_count == 2

    def test_uses_default_azure_credential_when_no_client_id(self):
        """DefaultAzureCredential is used when no managed_identity_client_id is set."""
        mock_token_provider = MagicMock(return_value="fake-bearer-token")
        env_without_mi = {
            "AZURE_MANAGED_IDENTITY_CLIENT_ID_TTS": "",
            "AZURE_MANAGED_IDENTITY_CLIENT_ID": "",
        }
        with patch.dict(os.environ, env_without_mi), patch(
            "open_notebook.ai.azure_ad_tts.DefaultAzureCredential"
        ) as MockDC, patch(
            "open_notebook.ai.azure_ad_tts.ManagedIdentityCredential"
        ) as MockMI, patch(
            "open_notebook.ai.azure_ad_tts.get_bearer_token_provider",
            return_value=mock_token_provider,
        ):
            from open_notebook.ai.azure_ad_tts import AzureAdTtsModel

            AzureAdTtsModel(
                model_name=AZURE_TTS_DEPLOYMENT,
                azure_endpoint=AZURE_TTS_ENDPOINT,
                api_version=AZURE_TTS_API_VERSION,
            )

        MockDC.assert_called_once()
        MockMI.assert_not_called()

    def test_uses_managed_identity_with_client_id(self):
        """ManagedIdentityCredential is used when managed_identity_client_id is provided."""
        mock_token_provider = MagicMock(return_value="fake-bearer-token")

        with patch(
            "open_notebook.ai.azure_ad_tts.ManagedIdentityCredential"
        ) as MockMI, patch(
            "open_notebook.ai.azure_ad_tts.DefaultAzureCredential"
        ) as MockDC, patch(
            "open_notebook.ai.azure_ad_tts.get_bearer_token_provider",
            return_value=mock_token_provider,
        ):
            from open_notebook.ai.azure_ad_tts import AzureAdTtsModel

            AzureAdTtsModel(
                model_name=AZURE_TTS_DEPLOYMENT,
                azure_endpoint=AZURE_TTS_ENDPOINT,
                api_version=AZURE_TTS_API_VERSION,
                managed_identity_client_id=AZURE_MANAGED_IDENTITY_CLIENT_ID,
            )

        MockMI.assert_called_once_with(client_id=AZURE_MANAGED_IDENTITY_CLIENT_ID)
        MockDC.assert_not_called()

    def test_api_version_from_env(self):
        """api_version falls back to AZURE_OPENAI_API_VERSION_TTS env var."""
        mock_token_provider = MagicMock(return_value="tok")
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT_TTS": AZURE_TTS_ENDPOINT,
                "AZURE_OPENAI_API_VERSION_TTS": AZURE_TTS_API_VERSION,
            },
        ), patch(
            "open_notebook.ai.azure_ad_tts.DefaultAzureCredential"
        ), patch(
            "open_notebook.ai.azure_ad_tts.get_bearer_token_provider",
            return_value=mock_token_provider,
        ):
            from open_notebook.ai.azure_ad_tts import AzureAdTtsModel

            model = AzureAdTtsModel(model_name=AZURE_TTS_DEPLOYMENT)

        assert model.api_version == AZURE_TTS_API_VERSION

    def test_managed_identity_client_id_from_env(self):
        """managed_identity_client_id falls back to AZURE_MANAGED_IDENTITY_CLIENT_ID env var."""
        mock_token_provider = MagicMock(return_value="tok")
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT_TTS": AZURE_TTS_ENDPOINT,
                "AZURE_OPENAI_API_VERSION_TTS": AZURE_TTS_API_VERSION,
                "AZURE_MANAGED_IDENTITY_CLIENT_ID": AZURE_MANAGED_IDENTITY_CLIENT_ID,
            },
        ), patch(
            "open_notebook.ai.azure_ad_tts.ManagedIdentityCredential"
        ) as MockMI, patch(
            "open_notebook.ai.azure_ad_tts.get_bearer_token_provider",
            return_value=mock_token_provider,
        ):
            from open_notebook.ai.azure_ad_tts import AzureAdTtsModel

            AzureAdTtsModel(model_name=AZURE_TTS_DEPLOYMENT)

        MockMI.assert_called_once_with(client_id=AZURE_MANAGED_IDENTITY_CLIENT_ID)


# ===========================================================================
# TEST SUITE 2 — generate_speech / agenerate_speech with mocked HTTP
# ===========================================================================


class TestAzureAdTtsModelSpeech:
    """Verify sync/async speech generation with mocked HTTP."""

    FAKE_AUDIO = b"RIFF\x00\x00\x00\x00WAVEfmt "  # minimal fake WAV bytes

    def _build_model(self):
        """Return a model instance with mocked token provider."""
        token_provider = MagicMock(return_value="tok")
        mock_sync_resp = MagicMock()
        mock_sync_resp.status_code = 200
        mock_sync_resp.content = self.FAKE_AUDIO

        with patch(
            "open_notebook.ai.azure_ad_tts.DefaultAzureCredential"
        ), patch(
            "open_notebook.ai.azure_ad_tts.get_bearer_token_provider",
            return_value=token_provider,
        ):
            from open_notebook.ai.azure_ad_tts import AzureAdTtsModel

            model = AzureAdTtsModel(
                model_name=AZURE_TTS_DEPLOYMENT,
                azure_endpoint=AZURE_TTS_ENDPOINT,
                api_version=AZURE_TTS_API_VERSION,
            )

        return model, mock_sync_resp

    def test_sync_generate_speech_returns_audio(self):
        model, mock_resp = self._build_model()
        model.client = MagicMock()
        model.client.post.return_value = mock_resp

        result = model.generate_speech(text="Hello world", voice=EXPECTED_VOICE)

        assert result.audio_data == self.FAKE_AUDIO
        assert result.voice == EXPECTED_VOICE
        assert result.model == AZURE_TTS_DEPLOYMENT

    def test_sync_generate_speech_uses_bearer_header(self):
        model, mock_resp = self._build_model()
        model.client = MagicMock()
        model.client.post.return_value = mock_resp

        model.generate_speech(text="Test", voice=EXPECTED_VOICE)

        call_kwargs = model.client.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization", "").startswith("Bearer ")
        assert "api-key" not in headers

    def test_sync_generate_speech_payload(self):
        """Payload must include model, voice, and input fields."""
        model, mock_resp = self._build_model()
        model.client = MagicMock()
        model.client.post.return_value = mock_resp

        model.generate_speech(text="Say something", voice="alloy")

        call_kwargs = model.client.post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["model"] == AZURE_TTS_DEPLOYMENT
        assert payload["voice"] == "alloy"
        assert payload["input"] == "Say something"

    def test_sync_generate_speech_saves_file(self, tmp_path):
        model, mock_resp = self._build_model()
        model.client = MagicMock()
        model.client.post.return_value = mock_resp

        output = tmp_path / "speech.mp3"
        model.generate_speech(text="Save me", voice=EXPECTED_VOICE, output_file=output)

        assert output.exists()
        assert output.read_bytes() == self.FAKE_AUDIO

    @pytest.mark.asyncio
    async def test_async_generate_speech_returns_audio(self):
        model, _ = self._build_model()
        mock_async_resp = MagicMock()
        mock_async_resp.status_code = 200
        mock_async_resp.content = self.FAKE_AUDIO
        model.async_client = MagicMock()
        model.async_client.post = AsyncMock(return_value=mock_async_resp)

        result = await model.agenerate_speech(text="Hello async", voice=EXPECTED_VOICE)

        assert result.audio_data == self.FAKE_AUDIO
        assert result.voice == EXPECTED_VOICE

    @pytest.mark.asyncio
    async def test_async_generate_speech_uses_bearer_header(self):
        model, _ = self._build_model()
        mock_async_resp = MagicMock()
        mock_async_resp.status_code = 200
        mock_async_resp.content = self.FAKE_AUDIO
        model.async_client = MagicMock()
        model.async_client.post = AsyncMock(return_value=mock_async_resp)

        await model.agenerate_speech(text="Test", voice=EXPECTED_VOICE)

        call_kwargs = model.async_client.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization", "").startswith("Bearer ")
        assert "api-key" not in headers

    @pytest.mark.asyncio
    async def test_async_generate_speech_saves_file(self, tmp_path):
        model, _ = self._build_model()
        mock_async_resp = MagicMock()
        mock_async_resp.status_code = 200
        mock_async_resp.content = self.FAKE_AUDIO
        model.async_client = MagicMock()
        model.async_client.post = AsyncMock(return_value=mock_async_resp)

        output = tmp_path / "async_speech.mp3"
        await model.agenerate_speech(
            text="Save async", voice=EXPECTED_VOICE, output_file=output
        )

        assert output.exists()
        assert output.read_bytes() == self.FAKE_AUDIO


# ===========================================================================
# TEST SUITE 3 — AIFactory registration
# ===========================================================================


class TestAzureAdTtsProviderRegistration:
    """Verify register_azure_ad_tts_provider() works correctly."""

    def test_registers_azureopenai_provider(self):
        from esperanto import AIFactory
        from open_notebook.ai.azure_ad_tts import register_azure_ad_tts_provider

        register_azure_ad_tts_provider()

        assert "azureopenai" in AIFactory._provider_modules["text_to_speech"]

    def test_registration_is_idempotent(self):
        """Calling register twice does not break the registry."""
        from esperanto import AIFactory
        from open_notebook.ai.azure_ad_tts import register_azure_ad_tts_provider

        register_azure_ad_tts_provider()
        register_azure_ad_tts_provider()

        assert AIFactory._provider_modules["text_to_speech"]["azureopenai"] == (
            "open_notebook.ai.azure_ad_tts:AzureAdTtsModel"
        )

    def test_aifactory_creates_azure_ad_tts_model(self):
        """AIFactory.create_text_to_speech('azureopenai', …) returns AzureAdTtsModel."""
        from esperanto import AIFactory
        from open_notebook.ai.azure_ad_tts import (
            AzureAdTtsModel,
            register_azure_ad_tts_provider,
        )

        register_azure_ad_tts_provider()

        token_provider = MagicMock(return_value="tok")
        with patch(
            "open_notebook.ai.azure_ad_tts.DefaultAzureCredential"
        ), patch(
            "open_notebook.ai.azure_ad_tts.get_bearer_token_provider",
            return_value=token_provider,
        ):
            model = AIFactory.create_text_to_speech(
                "azureopenai",
                AZURE_TTS_DEPLOYMENT,
                azure_endpoint=AZURE_TTS_ENDPOINT,
                api_version=AZURE_TTS_API_VERSION,
            )

        assert isinstance(model, AzureAdTtsModel)
        assert model.deployment_name == AZURE_TTS_DEPLOYMENT


# ===========================================================================
# TEST SUITE 4 — SpeakerProfile.tts_config pass-through
# ===========================================================================


class TestSpeakerProfileTtsConfig:
    """Verify tts_config is stored and round-tripped on SpeakerProfile."""

    def test_speaker_profile_accepts_tts_config(self):
        from open_notebook.podcasts.models import SpeakerProfile

        config = {
            "azure_endpoint": AZURE_TTS_ENDPOINT,
            "api_version": AZURE_TTS_API_VERSION,
            "managed_identity_client_id": AZURE_MANAGED_IDENTITY_CLIENT_ID,
        }
        profile = SpeakerProfile(
            name="Azure TTS",
            tts_provider="azureopenai",
            tts_model=AZURE_TTS_DEPLOYMENT,
            tts_config=config,
            speakers=[
                {
                    "name": "Host",
                    "voice_id": EXPECTED_VOICE,
                    "backstory": "Tech journalist",
                    "personality": "Curious",
                }
            ],
        )
        assert profile.tts_config == config

    def test_speaker_profile_tts_config_optional(self):
        """tts_config defaults to None when not provided."""
        from open_notebook.podcasts.models import SpeakerProfile

        profile = SpeakerProfile(
            name="OpenAI TTS",
            tts_provider="openai",
            tts_model="tts-1",
            speakers=[
                {
                    "name": "Host",
                    "voice_id": "nova",
                    "backstory": "Journalist",
                    "personality": "Friendly",
                }
            ],
        )
        assert profile.tts_config is None

    def test_speaker_profile_dict_includes_tts_config(self):
        """model_dump() includes tts_config for podcast_creator serialisation."""
        from open_notebook.podcasts.models import SpeakerProfile

        config = {"azure_endpoint": AZURE_TTS_ENDPOINT, "api_version": AZURE_TTS_API_VERSION}
        profile = SpeakerProfile(
            name="Test",
            tts_provider="azureopenai",
            tts_model=AZURE_TTS_DEPLOYMENT,
            tts_config=config,
            speakers=[
                {
                    "name": "Host",
                    "voice_id": "nova",
                    "backstory": "x",
                    "personality": "y",
                }
            ],
        )
        dumped = profile.model_dump()
        assert dumped["tts_config"] == config


# ===========================================================================
# TEST SUITE 5 — podcast_commands provider registration at import
# ===========================================================================


class TestPodcastCommandsRegistration:
    """Verify that importing podcast_commands registers 'azureopenai'."""

    def test_azureopenai_registered_after_import(self):
        from esperanto import AIFactory

        # Import triggers register_azure_ad_tts_provider()
        import commands.podcast_commands  # noqa: F401

        assert "azureopenai" in AIFactory._provider_modules["text_to_speech"]


# ===========================================================================
# TEST SUITE 6 — Integration tests (real Azure TTS endpoint)
# ===========================================================================


@pytest.mark.integration
class TestAzureAdTtsIntegration:
    """
    Live integration tests against Azure TTS deployment.

    Requires:
      - AZURE_OPENAI_ENDPOINT_TTS or AZURE_OPENAI_ENDPOINT
      - AZURE_OPENAI_API_VERSION_TTS
      - AZURE_MANAGED_IDENTITY_CLIENT_ID (or az login / managed identity)
    """

    @pytest.fixture(autouse=True)
    def require_azure_env(self):
        """Skip if required Azure env vars are missing."""
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT_TTS") or os.getenv("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            pytest.skip(
                "AZURE_OPENAI_ENDPOINT_TTS must be set to run TTS integration tests."
            )

    @pytest.fixture(autouse=True)
    def clear_managed_identity_env(self, monkeypatch):
        """Remove managed-identity client ID env vars so DefaultAzureCredential falls through
        to AzureCliCredential (az login) on dev machines instead of trying ManagedIdentityCredential
        which requires the Azure IMDS endpoint (169.254.169.254) only available inside Azure."""
        monkeypatch.delenv("AZURE_MANAGED_IDENTITY_CLIENT_ID", raising=False)
        monkeypatch.delenv("AZURE_MANAGED_IDENTITY_CLIENT_ID_TTS", raising=False)

    @pytest.fixture
    def model(self, clear_managed_identity_env):
        from open_notebook.ai.azure_ad_tts import AzureAdTtsModel

        # clear_managed_identity_env ensures env vars are cleared before __init__ reads them
        return AzureAdTtsModel(
            model_name=AZURE_TTS_DEPLOYMENT,
            azure_endpoint=AZURE_TTS_ENDPOINT,
            api_version=AZURE_TTS_API_VERSION,
        )

    def test_sync_generate_speech_returns_bytes(self, model):
        result = model.generate_speech(text="Hello from Open Notebook!", voice=EXPECTED_VOICE)
        assert isinstance(result.audio_data, bytes)
        assert len(result.audio_data) > 1000  # real audio should be > 1 KB
        assert result.provider == "azureopenai"

    def test_sync_generate_speech_saves_file(self, model, tmp_path):
        output = tmp_path / "integration_speech.mp3"
        result = model.generate_speech(
            text="Saving to disk.", voice=EXPECTED_VOICE, output_file=output
        )
        assert output.exists()
        assert output.stat().st_size == len(result.audio_data)

    @pytest.mark.asyncio
    async def test_async_generate_speech_returns_bytes(self, model):
        result = await model.agenerate_speech(
            text="Async speech test.", voice=EXPECTED_VOICE
        )
        assert isinstance(result.audio_data, bytes)
        assert len(result.audio_data) > 1000

    @pytest.mark.asyncio
    async def test_async_generate_speech_different_voices_differ(self, model):
        """Two different voices should produce different audio bytes."""
        nova = await model.agenerate_speech(text="Same text.", voice="nova")
        alloy = await model.agenerate_speech(text="Same text.", voice="alloy")
        assert nova.audio_data != alloy.audio_data

    @pytest.mark.asyncio
    async def test_via_aifactory(self):
        """AIFactory.create_text_to_speech('azureopenai') → real speech."""
        from esperanto import AIFactory
        from open_notebook.ai.azure_ad_tts import register_azure_ad_tts_provider

        register_azure_ad_tts_provider()

        # No managed_identity_client_id → DefaultAzureCredential → az login on dev
        model = AIFactory.create_text_to_speech(
            "azureopenai",
            AZURE_TTS_DEPLOYMENT,
            azure_endpoint=AZURE_TTS_ENDPOINT,
            api_version=AZURE_TTS_API_VERSION,
        )
        result = await model.agenerate_speech(
            text="Testing via AIFactory.", voice=EXPECTED_VOICE
        )
        assert len(result.audio_data) > 1000

    @pytest.mark.asyncio
    async def test_tts_config_dict_flow(self):
        """
        Simulate the flow: SpeakerProfile.tts_config → AIFactory kwargs.
        This mirrors what podcast_creator does internally.
        """
        from esperanto import AIFactory
        from open_notebook.ai.azure_ad_tts import (
            AzureAdTtsModel,
            register_azure_ad_tts_provider,
        )
        from open_notebook.podcasts.models import SpeakerProfile

        register_azure_ad_tts_provider()

        # No managed_identity_client_id in tts_config → DefaultAzureCredential → az login on dev
        profile = SpeakerProfile(
            name="Azure TTS Integration",
            tts_provider="azureopenai",
            tts_model=AZURE_TTS_DEPLOYMENT,
            tts_config={
                "azure_endpoint": AZURE_TTS_ENDPOINT,
                "api_version": AZURE_TTS_API_VERSION,
            },
            speakers=[
                {
                    "name": "Host",
                    "voice_id": EXPECTED_VOICE,
                    "backstory": "Integration tester",
                    "personality": "Methodical",
                }
            ],
        )

        # Simulate podcast_creator extracting config
        tts_config = dict(profile.tts_config or {})
        api_key = tts_config.pop("api_key", None)
        base_url = tts_config.pop("base_url", None)

        model = AIFactory.create_text_to_speech(
            profile.tts_provider,
            profile.tts_model,
            api_key=api_key,
            base_url=base_url,
            **tts_config,
        )

        assert isinstance(model, AzureAdTtsModel)

        result = await model.agenerate_speech(text="End-to-end TTS config test.", voice=EXPECTED_VOICE)
        assert len(result.audio_data) > 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
