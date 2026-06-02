from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class StateMeta(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    type: str = "unrestricted"


def _default_state_data() -> Dict[str, Any]:
    return {
        "current_claim": None,
        "submitted_claims": [],
        "uploads": [],
    }


class UserState(BaseModel):
    meta: StateMeta = Field(default_factory=StateMeta)
    data: Dict[str, Any] = Field(default_factory=_default_state_data)
    note: Optional[str] = None

    def touch(self) -> None:
        self.meta.updated_at = datetime.now(timezone.utc)
        self.meta.version += 1
