from .engine import CreativityEngine
from .config import EngineConfig, DEFAULT_SERENDIPITY_DOMAINS, DEFAULT_GENERATORS
from .llm import BaseLLMClient, ClaudeClient
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
