from .base import BaseLLMClient
from .claude import ClaudeClient

# OpenAI, Gemini, Ollama는 선택 의존성 — import 시점에 패키지 없어도 에러 안 남
def __getattr__(name: str):
    if name == "OpenAIClient":
        from .openai import OpenAIClient
        return OpenAIClient
    if name == "GeminiClient":
        from .gemini import GeminiClient
        return GeminiClient
    if name == "OllamaClient":
        from .ollama import OllamaClient
        return OllamaClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "BaseLLMClient",
    "ClaudeClient",
    "OpenAIClient",
    "GeminiClient",
    "OllamaClient",
]
