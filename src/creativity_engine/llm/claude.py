from __future__ import annotations

import logging
import os

import anthropic
from dotenv import load_dotenv

from .base import BaseLLMClient

load_dotenv()
logger = logging.getLogger(__name__)


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude API 구현체."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        retries: int = 2,
    ) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self._model = model
        self._retries = retries

    def call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        for attempt in range(self._retries + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return response.content[0].text
            except Exception as e:
                if attempt == self._retries:
                    raise
                logger.warning("LLM attempt %d failed: %s", attempt + 1, e)
        return ""
