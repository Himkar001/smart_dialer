"""Models package — import all models so Alembic can discover them."""

from app.models.agent import Agent, AgentState
from app.models.borrower import Borrower, BorrowerState
from app.models.call import Call, CallState
from app.models.call_event import CallEvent
from app.models.campaign import Campaign, CampaignMode, CampaignState, ProviderType

__all__ = [
    "Agent",
    "AgentState",
    "Borrower",
    "BorrowerState",
    "Call",
    "CallState",
    "CallEvent",
    "Campaign",
    "CampaignMode",
    "CampaignState",
    "ProviderType",
]
