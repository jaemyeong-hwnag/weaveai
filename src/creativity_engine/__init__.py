from .engine import CreativityEngine
from .config import EngineConfig, DEFAULT_SERENDIPITY_DOMAINS, DEFAULT_GENERATORS
from .llm import BaseLLMClient, ClaudeClient
from .llm import __getattr__ as _llm_getattr  # noqa: F401 — re-export lazy attrs


def __getattr__(name: str):
    _lazy = {"OpenAIClient", "GeminiClient", "OllamaClient"}
    if name in _lazy:
        import importlib
        llm_mod = importlib.import_module("creativity_engine.llm")
        return getattr(llm_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
from .adapters import (
    DomainAdapter,
    GeneralAdapter,
    LegalAdapter,
    MarketingAdapter,
    SoftwareAdapter,
    get_adapter,
    get_adapter_or_default,
)
from .core.models import (
    Action,
    ActionType,
    CreativityProblem,
    Document,
    Idea,
    IdeaSet,
    InputBundle,
    Signal,
    Solution,
)

__all__ = [
    # Engine
    "CreativityEngine",
    # Config
    "EngineConfig",
    "DEFAULT_SERENDIPITY_DOMAINS",
    "DEFAULT_GENERATORS",
    # LLM
    "BaseLLMClient",
    "ClaudeClient",
    "OpenAIClient",
    "GeminiClient",
    "OllamaClient",
    # Adapters
    "DomainAdapter",
    "GeneralAdapter",
    "LegalAdapter",
    "MarketingAdapter",
    "SoftwareAdapter",
    "get_adapter",
    "get_adapter_or_default",
    # Models
    "Action",
    "ActionType",
    "CreativityProblem",
    "Document",
    "Idea",
    "IdeaSet",
    "InputBundle",
    "Signal",
    "Solution",
]
