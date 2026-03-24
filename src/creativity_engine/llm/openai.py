from __future__ import annotations

import logging
import os

from .base import BaseLLMClient

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI API 구현체 (GPT-4o, GPT-4o-mini 등).

    설치:
        pip install openai

    사용:
        from creativity_engine.llm.openai import OpenAIClient
        config = EngineConfig(llm_client=OpenAIClient(model="gpt-4o"))
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        retries: int = 2,
    ) -> None:
        try:
            import openai as _openai
        except ImportError:
            raise ImportError(
                "openai 패키지가 필요합니다.\n"
                "설치: pip install openai"
            )
        self._client = _openai.OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY", "")
        )
        self._model = model
        self._retries = retries

    def call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        for attempt in range(self._retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                if attempt == self._retries:
                    raise
                logger.warning("OpenAI attempt %d failed: %s", attempt + 1, e)
        return ""
