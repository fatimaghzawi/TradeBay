"""AI module has no trading-domain persistence; models are advisory DTOs only."""

from pydantic import BaseModel


class SourcingInsightRecord(BaseModel):
    """Ephemeral insight — not stored as source of truth for procurement."""

    summary: str
    suggested_actions: list[str]
