"""Azure OpenAI embedding with managed identity (Azure AD) authentication.

This module provides an embedding model that authenticates using
DefaultAzureCredential, supporting:
  - Managed Identity (Azure VMs, App Service, AKS)
  - Azure CLI credentials (local dev: `az login`)
  - VS Code credential
  - Interactive browser (fallback)

Usage::

    model = AzureAdEmbeddingModel(model_name="text-embedding-ada-002")
    embeddings = await model.aembed(["Hello world"])
"""

import os
from typing import Dict, List

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from loguru import logger

from esperanto.providers.embedding.azure import AzureEmbeddingModel


class AzureAdEmbeddingModel(AzureEmbeddingModel):
    """Azure OpenAI embedding model authenticated via Azure AD (managed identity).

    Overrides the ``api-key`` header used by the parent class with an
    ``Authorization: Bearer <token>`` header obtained from
    ``DefaultAzureCredential``.  The token is refreshed on every request via
    ``get_bearer_token_provider``, so there is no manual token rotation needed.
    """

    def __init__(self, **kwargs):
        # Resolve endpoint and api_version from env vars before calling super().
        config: dict = dict(kwargs.get("config") or {})

        if "azure_endpoint" not in config:
            config["azure_endpoint"] = (
                os.getenv("AZURE_OPENAI_ENDPOINT_EMBEDDING")
                or os.getenv("AZURE_OPENAI_ENDPOINT", "")
            )

        if "api_version" not in config:
            config["api_version"] = (
                os.getenv("AZURE_OPENAI_API_VERSION_EMBEDDING")
                or os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")
            )

        # Set up the token provider first (before super().__init__ runs
        # validation) so _get_headers() works immediately after construction.
        self._token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )

        # Inject a placeholder api_key so AzureEmbeddingModel's required-field
        # validation passes.  _get_headers() is overridden below to use the
        # Bearer token instead, so this placeholder is never sent to Azure.
        config["api_key"] = "managed-identity-placeholder"

        kwargs["config"] = config
        super().__init__(**kwargs)

        logger.debug(
            f"AzureAdEmbeddingModel initialised: deployment={self.deployment_name} "
            f"endpoint={self.azure_endpoint} api_version={self.api_version}"
        )

    # ------------------------------------------------------------------
    # Override auth header to use Bearer token instead of api-key header
    # ------------------------------------------------------------------

    def _get_headers(self) -> Dict[str, str]:
        """Return Azure AD Bearer token headers for every HTTP request."""
        token = self._token_provider()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @property
    def provider(self) -> str:
        return "azure"

    def _get_default_model(self) -> str:
        return "text-embedding-ada-002"


def build_azure_ad_embedding_model(
    deployment: str | None = None,
    endpoint: str | None = None,
    api_version: str | None = None,
) -> AzureAdEmbeddingModel:
    """Factory helper that reads config from env vars with optional overrides.

    Args:
        deployment: Azure deployment name (e.g. ``text-embedding-ada-002``).
            Defaults to ``AZURE_OPENAI_EMBEDDING_DEPLOYMENT`` env var.
        endpoint: Azure OpenAI endpoint URL.
            Defaults to ``AZURE_OPENAI_ENDPOINT_EMBEDDING`` or
            ``AZURE_OPENAI_ENDPOINT`` env var.
        api_version: API version string.
            Defaults to ``AZURE_OPENAI_API_VERSION_EMBEDDING`` or
            ``AZURE_OPENAI_API_VERSION`` env var.

    Returns:
        Configured :class:`AzureAdEmbeddingModel` instance.
    """
    resolved_deployment = (
        deployment
        or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        or "text-embedding-ada-002"
    )
    resolved_endpoint = (
        endpoint
        or os.getenv("AZURE_OPENAI_ENDPOINT_EMBEDDING")
        or os.getenv("AZURE_OPENAI_ENDPOINT", "")
    )
    resolved_api_version = (
        api_version
        or os.getenv("AZURE_OPENAI_API_VERSION_EMBEDDING")
        or os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")
    )
    return AzureAdEmbeddingModel(
        model_name=resolved_deployment,
        config={
            "azure_endpoint": resolved_endpoint,
            "api_version": resolved_api_version,
        },
    )
