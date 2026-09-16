"""LiteLLM proxy client using direct HTTP requests.

This module provides a simple HTTP client that calls the LiteLLM proxy at
http://host.orb.internal:4000/v1/chat/completions. Per sprint requirements:
use requests to call the proxy instead of importing openai/google/mistralai directly.
"""
import requests
import os
from typing import Dict, List, Optional, Any


class LiteLLMClient:
    """Simple client for calling LiteLLM proxy via HTTP."""

    def __init__(self, api_key: Optional[str] = None, api_base: str = "http://host.orb.internal:4000/v1"):
        self.api_key = api_key or os.getenv("LITELLM_API_KEY", "")
        self.api_base = api_base.rstrip("/")
        self.chat = self.ChatCompletions(self)

    class ChatCompletions:
        """Mimics openai.ChatCompletions interface."""

        def __init__(self, client: 'LiteLLMClient'):
            self._client = client

        def create(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7,
                   max_completion_tokens: Optional[int] = None, max_tokens: Optional[int] = None,
                   timeout: int = 30, **kwargs) -> Any:
            """Make a chat completion request to the LiteLLM proxy."""
            # Build request payload
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }

            # Use max_completion_tokens if provided, otherwise max_tokens
            if max_completion_tokens is not None:
                payload["max_completion_tokens"] = max_completion_tokens
            elif max_tokens is not None:
                payload["max_tokens"] = max_tokens

            # Add any additional kwargs
            payload.update(kwargs)

            # Make the request
            url = f"{self._client.api_base}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self._client.api_key:
                headers["Authorization"] = f"Bearer {self._client.api_key}"

            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()

            # Parse and return a response object that mimics OpenAI's format
            data = response.json()
            return _OpenAIResponse(data)


    class _OpenAIResponse:
        """Mimics OpenAI response format."""

        def __init__(self, data: Dict[str, Any]):
            self.choices = [_OpenAIChoice(choice) for choice in data.get("choices", [])]
            self.model = data.get("model", "")
            self.usage = _OpenAIUsage(data.get("usage", {})) if "usage" in data else None


    class _OpenAIChoice:
        """Mimics OpenAI choice format."""

        def __init__(self, data: Dict[str, Any]):
            self.message = _OpenAIMessage(data.get("message", {}))
            self.finish_reason = data.get("finish_reason", "")
            self.index = data.get("index", 0)


    class _OpenAIMessage:
        """Mimics OpenAI message format."""

        def __init__(self, data: Dict[str, Any]):
            self.content = data.get("content", "")
            self.role = data.get("role", "assistant")


    class _OpenAIUsage:
        """Mimics OpenAI usage format."""

        def __init__(self, data: Dict[str, Any]):
            self.prompt_tokens = data.get("prompt_tokens", 0)
            self.completion_tokens = data.get("completion_tokens", 0)
            self.total_tokens = data.get("total_tokens", 0)


def create_client(api_key: Optional[str] = None, api_base: str = "http://host.orb.internal:4000/v1") -> LiteLLMClient:
    """Factory function to create a LiteLLM client."""
    return LiteLLMClient(api_key=api_key, api_base=api_base)
