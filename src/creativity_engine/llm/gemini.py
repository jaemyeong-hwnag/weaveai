from __future__ import annotations

import logging
import os

from .base import BaseLLMClient

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    """Google Gemini API 구현체 (gemini-2.0-flash, gemini-1.5-pro 등).

    설치:
        pip install google-genai

    사용:
        from creativity_engine.llm.gemini import GeminiClient
        config = EngineConfig(llm_client=GeminiClient(model="gemini-2.0-flash"))
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.0-flash",
        retries: int = 2,
    ) -> None:
        try:
            import google.genai as genai
        except ImportError:
            raise ImportError(
                "google-genai 패키지가 필요합니다.\n"
                "설치: pip install google-genai"
            )
        self._client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY", ""))
        self._model_name = model
        self._retries = retries

    def call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        # system instruction + user message 결합
        prompt = f"{system}\n\n{user}"
        for attempt in range(self._retries + 1):
            try:
                import google.genai.types as genai_types
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        max_output_tokens=max_tokens,
                    ),
                )
                return response.text or ""
            except Exception as e:
                if attempt == self._retries:
                    raise
                logger.warning("Gemini attempt %d failed: %s", attempt + 1, e)
        return ""
