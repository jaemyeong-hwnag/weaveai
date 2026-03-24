from __future__ import annotations

import logging

from .base import BaseLLMClient

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "http://localhost:11434"


class OllamaClient(BaseLLMClient):
    """Ollama 로컬 LLM 구현체 (llama3, mistral, qwen 등).

    Ollama 서버가 로컬에서 실행 중이어야 합니다.
    https://ollama.ai

    설치:
        pip install ollama

    사용:
        from creativity_engine.llm.ollama import OllamaClient
        config = EngineConfig(llm_client=OllamaClient(model="llama3.2"))
    """

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = _DEFAULT_HOST,
        retries: int = 2,
    ) -> None:
        try:
            import ollama as _ollama
        except ImportError:
            raise ImportError(
                "ollama 패키지가 필요합니다.\n"
                "설치: pip install ollama\n"
                "Ollama 서버: https://ollama.ai"
            )
        self._ollama = _ollama
        self._client = _ollama.Client(host=host)
        self._model = model
        self._retries = retries

    def call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        for attempt in range(self._retries + 1):
            try:
                response = self._client.chat(
                    model=self._model,
                    messages=messages,
                    options={"num_predict": max_tokens},
                )
                return response["message"]["content"] or ""
            except Exception as e:
                if attempt == self._retries:
                    raise
                logger.warning("Ollama attempt %d failed: %s", attempt + 1, e)
        return ""
