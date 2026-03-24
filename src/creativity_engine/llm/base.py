from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """LLM 공급자 추상 인터페이스. Claude, OpenAI 등 교체 가능."""

    @abstractmethod
    def call(self, system: str, user: str, max_tokens: int = 4096) -> str:
        """시스템 프롬프트 + 사용자 메시지 → 응답 텍스트."""
        ...
