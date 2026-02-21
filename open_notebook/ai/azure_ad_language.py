"""Azure OpenAI language model with managed identity (Azure AD) authentication.

This module provides a language model that authenticates using
DefaultAzureCredential, supporting:
  - Managed Identity (Azure VMs, App Service, AKS)
  - Azure CLI credentials (local dev: `az login`)
  - VS Code credential
  - Interactive browser (fallback)

Usage::

    model = AzureAdLanguageModel(model_name="gpt-5.2-chat")
    response = await model.achat_complete(messages)
"""

import os
from typing import Any, Dict

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from loguru import logger

from esperanto.providers.llm.azure import AzureLanguageModel


class AzureAdLanguageModel(AzureLanguageModel):
    """Azure OpenAI language model authenticated via Azure AD (managed identity).

    Overrides the ``api-key`` header used by the parent class with an
    ``Authorization: Bearer <token>`` header obtained from
    ``DefaultAzureCredential``.  The token is refreshed on every request via
    ``get_bearer_token_provider``, so there is no manual token rotation needed.

    The LangChain integration also uses ``azure_ad_token_provider`` instead of
    ``api_key``, so LangGraph workflows work transparently.
    """

    def __post_init__(self):
        # Set up bearer token provider before parent's __post_init__ validates api_key.
        self._token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )

        # Inject placeholder api_key so AzureLanguageModel's required-field
        # validation passes.  _get_headers() is overridden below to use the
        # Bearer token instead, so this placeholder is never sent to Azure.
        if self.config is None:
            self.config = {"api_key": "managed-identity-placeholder"}
        else:
            self.config = dict(self.config)  # copy to avoid mutating caller's dict
            if "api_key" not in self.config:
                self.config["api_key"] = "managed-identity-placeholder"

        super().__post_init__()

        logger.debug(
            f"AzureAdLanguageModel initialised: deployment={self.deployment_name} "
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

    def to_langchain(self, **kwargs: Any):
        """Convert to a LangChain AzureChatOpenAI model using AD token provider.

        Uses ``azure_ad_token_provider`` instead of ``api_key`` so that
        LangGraph workflows authenticate via managed identity.
        """
        try:
            from langchain_openai import AzureChatOpenAI
        except ImportError as e:
            raise ImportError(
                "LangChain or langchain-openai not installed. "
                "Please install with `pip install langchain_openai`"
            ) from e

        model_kwargs = {}
        if self.structured is not None:
            if isinstance(self.structured, dict):
                if self.structured.get("type") in ("json_object", "json"):
                    model_kwargs["response_format"] = {"type": "json_object"}
            elif self.structured == "json":
                model_kwargs["response_format"] = {"type": "json_object"}

        is_reasoning_model = self._is_reasoning_model()

        langchain_kwargs = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "streaming": self.streaming,
            # Use AD token provider instead of api_key
            "azure_ad_token_provider": self._token_provider,
            "azure_deployment": self.deployment_name,
            "api_version": self.api_version,
            "azure_endpoint": self.azure_endpoint,
            "model_kwargs": model_kwargs,
        }

        try:
            sync_client, async_client = self._create_langchain_http_clients()
            langchain_kwargs["http_client"] = sync_client
            langchain_kwargs["http_async_client"] = async_client
        except (TypeError, AttributeError):
            pass

        if is_reasoning_model:
            if self.max_tokens != 850:
                model_kwargs["max_completion_tokens"] = self.max_tokens
            langchain_kwargs["temperature"] = 1
            langchain_kwargs["top_p"] = None
        else:
            langchain_kwargs["max_tokens"] = self.max_tokens

        langchain_kwargs.update(kwargs)

        final_lc_kwargs = {k: v for k, v in langchain_kwargs.items() if v is not None}

        if not final_lc_kwargs.get("model_kwargs") and "model_kwargs" not in kwargs:
            final_lc_kwargs.pop("model_kwargs", None)

        return AzureChatOpenAI(**self._clean_config(final_lc_kwargs))

    @property
    def provider(self) -> str:
        return "azure"


def build_azure_ad_language_model(
    deployment: str | None = None,
    endpoint: str | None = None,
    api_version: str | None = None,
) -> AzureAdLanguageModel:
    """Factory helper that reads config from env vars with optional overrides.

    Args:
        deployment: Azure deployment name (e.g. ``gpt-5.2-chat``).
            Defaults to ``AZURE_OPENAI_DEPLOYMENT`` env var.
        endpoint: Azure OpenAI endpoint URL.
            Defaults to ``AZURE_OPENAI_ENDPOINT_LLM`` or
            ``AZURE_OPENAI_ENDPOINT`` env var.
        api_version: API version string.
            Defaults to ``AZURE_OPENAI_API_VERSION_LLM`` or
            ``AZURE_OPENAI_API_VERSION`` env var.

    Returns:
        Configured :class:`AzureAdLanguageModel` instance.
    """
    resolved_deployment = (
        deployment
        or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        or ""
    )
    resolved_endpoint = (
        endpoint
        or os.getenv("AZURE_OPENAI_ENDPOINT_LLM")
        or os.getenv("AZURE_OPENAI_ENDPOINT", "")
    )
    resolved_api_version = (
        api_version
        or os.getenv("AZURE_OPENAI_API_VERSION_LLM")
        or os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    )
    return AzureAdLanguageModel(
        model_name=resolved_deployment,
        config={
            "azure_endpoint": resolved_endpoint,
            "api_version": resolved_api_version,
        },
    )
