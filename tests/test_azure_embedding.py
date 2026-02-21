"""
Tests for Azure AD (managed identity) embedding model.

Unit tests use mocks so they run without Azure credentials.
Integration tests call the real Azure endpoint and require:
  - AZURE_OPENAI_ENDPOINT_EMBEDDING (or AZURE_OPENAI_ENDPOINT)
  - AZURE_OPENAI_EMBEDDING_DEPLOYMENT (or AZURE_OPENAI_API_VERSION_EMBEDDING)
  - A valid credential reachable via DefaultAzureCredential (e.g. `az login`)

Run integration tests:
    uv run pytest tests/test_azure_embedding.py -m integration -v
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants matching the dev Azure deployment
# ---------------------------------------------------------------------------
AZURE_EMBEDDING_ENDPOINT = "https://datacopilothub8882317788.openai.azure.com/"
AZURE_EMBEDDING_DEPLOYMENT = "text-embedding-ada-002"
AZURE_EMBEDDING_API_VERSION = "2023-05-15"
EXPECTED_DIMENSIONS = 1536  # text-embedding-ada-002 output size


# ===========================================================================
# TEST SUITE 1 — AzureAdEmbeddingModel unit tests
# ===========================================================================


class TestAzureAdEmbeddingModelInit:
    """Verify construction and auth header generation without hitting Azure."""

    def _make_model(self, extra_config=None):
        """Build model with mocked Azure credential."""
        config = {
            "azure_endpoint": AZURE_EMBEDDING_ENDPOINT,
            "api_version": AZURE_EMBEDDING_API_VERSION,
            **(extra_config or {}),
        }
        mock_token_provider = MagicMock(return_value="fake-bearer-token")

        with patch(
            "open_notebook.ai.azure_ad_embedding.DefaultAzureCredential"
        ) as MockCred, patch(
            "open_notebook.ai.azure_ad_embedding.get_bearer_token_provider",
            return_value=mock_token_provider,
        ):
            from open_notebook.ai.azure_ad_embedding import AzureAdEmbeddingModel

            model = AzureAdEmbeddingModel(
                model_name=AZURE_EMBEDDING_DEPLOYMENT, config=config
            )
        return model, mock_token_provider

    def test_provider_name(self):
        model, _ = self._make_model()
        assert model.provider == "azure"

    def test_deployment_name(self):
        model, _ = self._make_model()
        assert model.deployment_name == AZURE_EMBEDDING_DEPLOYMENT

    def test_endpoint_set(self):
        model, _ = self._make_model()
        assert AZURE_EMBEDDING_ENDPOINT.rstrip("/") in model.azure_endpoint

    def test_api_version_set(self):
        model, _ = self._make_model()
        assert model.api_version == AZURE_EMBEDDING_API_VERSION

    def test_bearer_header_not_api_key_header(self):
        """_get_headers() must return Authorization: Bearer, NOT api-key."""
        model, mock_token_provider = self._make_model()
        headers = model._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer fake-bearer-token"
        assert "api-key" not in headers

    def test_token_provider_called_on_each_header_call(self):
        """Token provider is called every time headers are requested (auto-refresh)."""
        model, mock_token_provider = self._make_model()
        model._get_headers()
        model._get_headers()
        assert mock_token_provider.call_count == 2

    def test_api_version_from_env(self):
        """api_version falls back to AZURE_OPENAI_API_VERSION_EMBEDDING env var."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT_EMBEDDING": AZURE_EMBEDDING_ENDPOINT,
                "AZURE_OPENAI_API_VERSION_EMBEDDING": "2023-05-15",
            },
        ):
            mock_token_provider = MagicMock(return_value="tok")
            with patch(
                "open_notebook.ai.azure_ad_embedding.DefaultAzureCredential"
            ), patch(
                "open_notebook.ai.azure_ad_embedding.get_bearer_token_provider",
                return_value=mock_token_provider,
            ):
                from open_notebook.ai.azure_ad_embedding import AzureAdEmbeddingModel

                model = AzureAdEmbeddingModel(
                    model_name=AZURE_EMBEDDING_DEPLOYMENT, config={}
                )
        assert model.api_version == "2023-05-15"


# ===========================================================================
# TEST SUITE 2 — embed / aembed with mocked HTTP
# ===========================================================================


class TestAzureAdEmbeddingModelEmbedding:
    """Verify embed() and aembed() send correct requests and parse responses."""

    FAKE_RESPONSE = {
        "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
        "model": "text-embedding-ada-002",
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }

    def _build_model_with_mock_http(self):
        config = {
            "azure_endpoint": AZURE_EMBEDDING_ENDPOINT,
            "api_version": AZURE_EMBEDDING_API_VERSION,
        }
        token_provider = MagicMock(return_value="tok")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.FAKE_RESPONSE

        with patch(
            "open_notebook.ai.azure_ad_embedding.DefaultAzureCredential"
        ), patch(
            "open_notebook.ai.azure_ad_embedding.get_bearer_token_provider",
            return_value=token_provider,
        ):
            from open_notebook.ai.azure_ad_embedding import AzureAdEmbeddingModel

            model = AzureAdEmbeddingModel(
                model_name=AZURE_EMBEDDING_DEPLOYMENT, config=config
            )
        return model, mock_response

    def test_sync_embed_returns_list(self):
        model, mock_resp = self._build_model_with_mock_http()
        model.client = MagicMock()
        model.client.post.return_value = mock_resp

        result = model.embed(["Hello world"])
        assert result == [[0.1, 0.2, 0.3]]

    def test_sync_embed_uses_bearer_header(self):
        model, mock_resp = self._build_model_with_mock_http()
        model.client = MagicMock()
        model.client.post.return_value = mock_resp

        model.embed(["Test"])
        call_kwargs = model.client.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization", "").startswith("Bearer ")
        assert "api-key" not in headers

    @pytest.mark.asyncio
    async def test_async_embed_returns_list(self):
        model, mock_resp = self._build_model_with_mock_http()
        async_mock_response = MagicMock()
        async_mock_response.status_code = 200
        async_mock_response.json.return_value = self.FAKE_RESPONSE
        model.async_client = MagicMock()
        model.async_client.post = AsyncMock(return_value=async_mock_response)

        result = await model.aembed(["Hello world"])
        assert result == [[0.1, 0.2, 0.3]]

    @pytest.mark.asyncio
    async def test_async_embed_uses_bearer_header(self):
        model, mock_resp = self._build_model_with_mock_http()
        async_mock_response = MagicMock()
        async_mock_response.status_code = 200
        async_mock_response.json.return_value = self.FAKE_RESPONSE
        model.async_client = MagicMock()
        model.async_client.post = AsyncMock(return_value=async_mock_response)

        await model.aembed(["Test"])
        call_kwargs = model.async_client.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization", "").startswith("Bearer ")
        assert "api-key" not in headers


# ===========================================================================
# TEST SUITE 3 — ModelManager fallback
# ===========================================================================


class TestModelManagerEmbeddingFallback:
    """Verify ModelManager.get_embedding_model() falls back to Azure AD model."""

    @pytest.mark.asyncio
    async def test_fallback_when_no_db_model(self):
        """When no default embedding model in DB but env vars set → returns AzureAdEmbeddingModel."""
        from open_notebook.ai.azure_ad_embedding import AzureAdEmbeddingModel
        from open_notebook.ai.models import ModelManager

        env_overrides = {
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": AZURE_EMBEDDING_DEPLOYMENT,
            "AZURE_OPENAI_ENDPOINT_EMBEDDING": AZURE_EMBEDDING_ENDPOINT,
            "AZURE_OPENAI_API_VERSION_EMBEDDING": AZURE_EMBEDDING_API_VERSION,
        }

        mock_defaults = MagicMock()
        mock_defaults.default_embedding_model = None  # no DB model configured

        with patch.dict(os.environ, env_overrides), patch(
            "open_notebook.ai.azure_ad_embedding.DefaultAzureCredential"
        ), patch(
            "open_notebook.ai.azure_ad_embedding.get_bearer_token_provider",
            return_value=MagicMock(return_value="tok"),
        ):
            manager = ModelManager()
            with patch.object(
                manager, "get_defaults", new_callable=AsyncMock, return_value=mock_defaults
            ):
                result = await manager.get_embedding_model()

        assert isinstance(result, AzureAdEmbeddingModel)

    @pytest.mark.asyncio
    async def test_no_fallback_when_env_vars_missing(self):
        """When no DB model and no env vars → returns None."""
        from open_notebook.ai.models import ModelManager

        mock_defaults = MagicMock()
        mock_defaults.default_embedding_model = None

        env_without_azure = {k: "" for k in [
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
            "AZURE_OPENAI_ENDPOINT_EMBEDDING",
            "AZURE_OPENAI_ENDPOINT",
        ]}

        manager = ModelManager()
        with patch.dict(os.environ, env_without_azure), patch.object(
            manager, "get_defaults", new_callable=AsyncMock, return_value=mock_defaults
        ):
            result = await manager.get_embedding_model()

        assert result is None


# ===========================================================================
# TEST SUITE 4 — Integration tests (real Azure endpoint)
# ===========================================================================


@pytest.mark.integration
class TestAzureAdEmbeddingIntegration:
    """
    Live integration tests against Azure's text-embedding-ada-002 deployment.

    Requires:
      - `az login` completed in the current shell, OR
      - A managed identity attached to the host environment.
    """

    @pytest.fixture(autouse=True)
    def require_azure_env(self):
        """Skip integration tests if Azure env vars are not set."""
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT_EMBEDDING") or os.getenv(
            "AZURE_OPENAI_ENDPOINT"
        )
        deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if not (endpoint and deployment):
            pytest.skip(
                "AZURE_OPENAI_ENDPOINT_EMBEDDING and AZURE_OPENAI_EMBEDDING_DEPLOYMENT "
                "must be set to run integration tests."
            )

    @pytest.fixture
    def model(self):
        from open_notebook.ai.azure_ad_embedding import build_azure_ad_embedding_model

        return build_azure_ad_embedding_model(
            deployment=AZURE_EMBEDDING_DEPLOYMENT,
            endpoint=AZURE_EMBEDDING_ENDPOINT,
            api_version=AZURE_EMBEDDING_API_VERSION,
        )

    def test_sync_embed_single_text(self, model):
        result = model.embed(["Hello, Azure embedding!"])
        assert isinstance(result, list)
        assert len(result) == 1
        assert len(result[0]) == EXPECTED_DIMENSIONS
        assert all(isinstance(v, float) for v in result[0])

    def test_sync_embed_multiple_texts(self, model):
        texts = ["First sentence.", "Second sentence.", "Third sentence."]
        result = model.embed(texts)
        assert len(result) == len(texts)
        for emb in result:
            assert len(emb) == EXPECTED_DIMENSIONS

    @pytest.mark.asyncio
    async def test_async_embed_single_text(self, model):
        result = await model.aembed(["Async embedding test."])
        assert len(result) == 1
        assert len(result[0]) == EXPECTED_DIMENSIONS

    @pytest.mark.asyncio
    async def test_async_embed_multiple_texts(self, model):
        texts = ["Alpha.", "Beta.", "Gamma."]
        result = await model.aembed(texts)
        assert len(result) == len(texts)
        for emb in result:
            assert len(emb) == EXPECTED_DIMENSIONS

    @pytest.mark.asyncio
    async def test_embeddings_are_distinct(self, model):
        """Semantically different texts should produce different embeddings."""
        import math

        result = await model.aembed(["cat", "quantum physics"])
        emb_a, emb_b = result[0], result[1]
        dot = sum(a * b for a, b in zip(emb_a, emb_b))
        norm_a = math.sqrt(sum(v * v for v in emb_a))
        norm_b = math.sqrt(sum(v * v for v in emb_b))
        cosine_sim = dot / (norm_a * norm_b)
        # Different topics → cosine similarity < 0.95
        assert cosine_sim < 0.95, f"Expected dissimilar embeddings, got cosine={cosine_sim:.4f}"

    @pytest.mark.asyncio
    async def test_via_model_manager_fallback(self):
        """ModelManager.get_embedding_model() returns AzureAdEmbeddingModel via env fallback."""
        from open_notebook.ai.azure_ad_embedding import AzureAdEmbeddingModel
        from open_notebook.ai.models import ModelManager

        mock_defaults = MagicMock()
        mock_defaults.default_embedding_model = None

        manager = ModelManager()
        with patch.object(
            manager, "get_defaults", new_callable=AsyncMock, return_value=mock_defaults
        ):
            model = await manager.get_embedding_model()

        assert isinstance(model, AzureAdEmbeddingModel)
        # Now actually embed something
        result = await model.aembed(["Integration test via ModelManager."])
        assert len(result[0]) == EXPECTED_DIMENSIONS


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
