"""
Abstract TelecomProvider interface.

Design principle: the Pacing Engine and Dialer Worker NEVER import
concrete providers directly. They receive a provider instance injected
by the registry. This makes the Safety Controller the only authorised
path from pacing decision → actual call placement.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ProviderStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


@dataclass
class ProviderCallResult:
    """Result of initiating a call with the telecom provider."""
    status: ProviderStatus
    provider_call_id: str | None
    error_message: str | None = None


class TelecomProvider(ABC):
    """
    Abstract base for all telecom provider implementations.

    Both ProviderA and ProviderB implement this interface.
    The rest of the system only ever uses TelecomProvider — never a concrete class.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'PROVIDER_A')."""

    @abstractmethod
    async def initiate_call(
        self,
        call_id: uuid.UUID,
        to_number: str,
    ) -> ProviderCallResult:
        """
        Instruct the provider to place a call.
        Returns immediately with a provider_call_id; events arrive asynchronously.
        """

    @abstractmethod
    async def get_health_score(self) -> float:
        """
        Current provider health (0.0 = dead, 1.0 = perfect).
        Used by SafetyController to gate predictive pacing.
        """

    @abstractmethod
    async def simulate_call_events(
        self, call_id: uuid.UUID, answer_rate_override: float | None = None
    ):
        """
        Async generator that yields (event_type, idempotency_key) tuples
        in the order they arrive from the provider.

        Provider B may yield duplicate or out-of-order events intentionally.
        """
        # Protocol: yield (event_type: str, idempotency_key: str)
        return
        yield  # Make this a generator
