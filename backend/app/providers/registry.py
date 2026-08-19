"""Provider registry — factory function for provider instances."""

from app.models.campaign import ProviderType
from app.providers.base import TelecomProvider
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB

# Singletons — shared across the process so health score persists realistically
_provider_a = ProviderA()
_provider_b = ProviderB()


def get_provider(provider_type: ProviderType | str) -> TelecomProvider:
    """
    Return the singleton provider instance for the given type.
    The providers are singletons so their health state persists across calls.
    """
    if isinstance(provider_type, ProviderType):
        key = provider_type.name
    else:
        key = str(provider_type).upper()
        
    if key == "PROVIDER_A":
        return _provider_a
    if key == "PROVIDER_B":
        return _provider_b
    raise ValueError(f"Unknown provider: {provider_type!r}")


def get_all_providers() -> dict[str, TelecomProvider]:
    """Return all providers keyed by name (for health monitoring)."""
    return {
        "PROVIDER_A": _provider_a,
        "PROVIDER_B": _provider_b,
    }
