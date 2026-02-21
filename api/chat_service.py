"""
Chat service for API operations.
Provides async interface for chat functionality.
"""

import os
from typing import Any, Dict, List, Optional

import httpx
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from loguru import logger
from openai import AsyncAzureOpenAI


class ChatService:
    """Service for chat-related API operations"""

    def __init__(self):
        self.base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:5055")
        # Add authentication header if password is set
        self.headers = {}
        password = os.getenv("OPEN_NOTEBOOK_PASSWORD")
        if password:
            self.headers["Authorization"] = f"Bearer {password}"

        # Azure OpenAI client using managed identity (no API key required).
        # Follows the same pattern as azure_provider.py.
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2-chat")
        self.azure_api_version = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2025-01-01-preview"
        )

        if azure_endpoint:
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            self._azure_client = AsyncAzureOpenAI(
                api_version=self.azure_api_version,
                azure_endpoint=azure_endpoint,
                azure_ad_token_provider=token_provider,
            )
            logger.info(
                f"Azure OpenAI default LLM initialized: endpoint={azure_endpoint} "
                f"deployment={self.azure_deployment}"
            )
        else:
            self._azure_client = None
            logger.warning(
                "AZURE_OPENAI_ENDPOINT not set — Azure OpenAI default LLM disabled"
            )

    async def get_sessions(self, notebook_id: str) -> List[Dict[str, Any]]:
        """Get all chat sessions for a notebook"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/chat/sessions",
                    params={"notebook_id": notebook_id},
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching chat sessions: {str(e)}")
            raise

    async def create_session(
        self,
        notebook_id: str,
        title: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new chat session"""
        try:
            data: Dict[str, Any] = {"notebook_id": notebook_id}
            if title is not None:
                data["title"] = title
            if model_override is not None:
                data["model_override"] = model_override

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/chat/sessions",
                    json=data,
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error creating chat session: {str(e)}")
            raise

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get a specific session with messages"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/chat/sessions/{session_id}",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching session: {str(e)}")
            raise

    async def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update session properties"""
        try:
            data: Dict[str, Any] = {}
            if title is not None:
                data["title"] = title
            if model_override is not None:
                data["model_override"] = model_override

            if not data:
                raise ValueError(
                    "At least one field must be provided to update a session"
                )

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/api/chat/sessions/{session_id}",
                    json=data,
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error updating session: {str(e)}")
            raise

    async def delete_session(self, session_id: str) -> Dict[str, Any]:
        """Delete a chat session"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/api/chat/sessions/{session_id}",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error deleting session: {str(e)}")
            raise

    async def execute_chat(
        self,
        session_id: str,
        message: str,
        context: Dict[str, Any],
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a chat request"""
        try:
            data = {"session_id": session_id, "message": message, "context": context}
            if model_override is not None:
                data["model_override"] = model_override

            # Short connect timeout (10s), long read timeout (10 min) for Ollama/local LLMs
            timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat/execute", json=data, headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error executing chat: {str(e)}")
            raise

    async def build_context(
        self, notebook_id: str, context_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build context for a notebook"""
        try:
            data = {"notebook_id": notebook_id, "context_config": context_config}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/chat/context", json=data, headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error building context: {str(e)}")
            raise


# Global instance
chat_service = ChatService()
