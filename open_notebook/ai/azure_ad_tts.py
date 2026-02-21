"""
Azure AD (managed identity) Text-to-Speech model for Open Notebook.

Subclasses Esperanto's AzureTextToSpeechModel to replace api-key header auth
with Azure AD Bearer token (DefaultAzureCredential / ManagedIdentityCredential).

Registration:
    call register_azure_ad_tts_provider() once at startup to add "azureopenai"
    to AIFactory's TTS provider registry.

SpeakerProfile.tts_config keys consumed here:
    azure_endpoint            - Azure OpenAI endpoint URL
    api_version               - API version (default: 2025-03-01-preview)
    managed_identity_client_id - Optional user-assigned managed identity client ID
"""

import os
from typing import Dict, Optional

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.identity import get_bearer_token_provider
from esperanto import AIFactory
from esperanto.providers.tts.azure import AzureTextToSpeechModel
from loguru import logger


class AzureAdTtsModel(AzureTextToSpeechModel):
    """
    Azure OpenAI TTS using managed identity (no API key required).

    Overrides _get_headers() to send Authorization: Bearer <token> instead of
    the api-key header used by the base class.
    """

    PROVIDER = "azureopenai"

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,   # ignored – kept for compat
        base_url: Optional[str] = None,
        **kwargs,
    ):
        # Pull managed identity client ID before passing kwargs to parent
        managed_identity_client_id = kwargs.pop("managed_identity_client_id", None) or (
            os.getenv("AZURE_MANAGED_IDENTITY_CLIENT_ID_TTS")
            or os.getenv("AZURE_MANAGED_IDENTITY_CLIENT_ID")
        )

        # Resolve endpoint (priority: kwarg > env TTS-specific > generic)
        azure_endpoint = base_url or kwargs.get("azure_endpoint") or (
            os.getenv("AZURE_OPENAI_ENDPOINT_TTS")
            or os.getenv("AZURE_OPENAI_ENDPOINT", "")
        )

        # Ensure api_version is in kwargs (parent reads it from self._config)
        if "api_version" not in kwargs:
            kwargs["api_version"] = (
                os.getenv("AZURE_OPENAI_API_VERSION_TTS")
                or os.getenv("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")
            )

        # Set up Azure AD token provider
        if managed_identity_client_id:
            logger.debug(
                f"AzureAdTtsModel: using user-assigned managed identity {managed_identity_client_id}"
            )
            credential = ManagedIdentityCredential(client_id=managed_identity_client_id)
        else:
            logger.debug("AzureAdTtsModel: using DefaultAzureCredential")
            credential = DefaultAzureCredential()

        self._token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )

        # Inject placeholder api_key so parent validation passes
        super().__init__(
            model_name=model_name,
            api_key="managed-identity-placeholder",
            base_url=azure_endpoint,
            **kwargs,
        )

        logger.info(
            f"AzureAdTtsModel initialised: deployment={self.deployment_name} "
            f"endpoint={self.azure_endpoint} api_version={self.api_version}"
        )

    # ------------------------------------------------------------------
    # Override header generation to use Bearer token instead of api-key
    # ------------------------------------------------------------------

    def _get_headers(self) -> Dict[str, str]:
        token = self._token_provider()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def register_azure_ad_tts_provider() -> None:
    """
    Register 'azureopenai' as a TTS provider in Esperanto's AIFactory.

    Call once at process startup (e.g. in podcast_commands.py at module level).
    Idempotent – safe to call multiple times.
    """
    AIFactory._provider_modules["text_to_speech"][
        "azureopenai"
    ] = "open_notebook.ai.azure_ad_tts:AzureAdTtsModel"
    logger.debug("Registered 'azureopenai' TTS provider in AIFactory")
