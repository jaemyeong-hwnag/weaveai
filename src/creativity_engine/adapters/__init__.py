from .base import DomainAdapter
from .general import GeneralAdapter
from .legal import LegalAdapter
from .marketing import MarketingAdapter
from .software import SoftwareAdapter

ADAPTER_REGISTRY: dict[str, type[DomainAdapter]] = {
    "general": GeneralAdapter,
    "legal": LegalAdapter,
    "marketing": MarketingAdapter,
    "software": SoftwareAdapter,
}


def get_adapter(domain: str) -> DomainAdapter:
    cls = ADAPTER_REGISTRY.get(domain)
    if not cls:
        raise ValueError(
            f"Unknown domain: '{domain}'. Available: {list(ADAPTER_REGISTRY)}"
        )
    return cls()


def get_adapter_or_default(domain: str) -> DomainAdapter:
    """알 수 없는 도메인이면 GeneralAdapter로 fallback."""
    cls = ADAPTER_REGISTRY.get(domain, GeneralAdapter)
    return cls()


__all__ = [
    "DomainAdapter",
    "GeneralAdapter",
    "LegalAdapter",
    "MarketingAdapter",
    "SoftwareAdapter",
    "ADAPTER_REGISTRY",
    "get_adapter",
    "get_adapter_or_default",
]
