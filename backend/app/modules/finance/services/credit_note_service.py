from __future__ import annotations

from typing import Any

from app.modules.finance.repository import CreditNoteRepository


class CreditNoteService:
    def __init__(self, credit_note_repository: CreditNoteRepository) -> None:
        self._credit_notes = credit_note_repository

    async def create_credit_note(self, *, invoice_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
