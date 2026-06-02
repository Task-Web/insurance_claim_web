from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .models import StateMeta, UserState


class StateRequest(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None
    meta: Optional[StateMeta] = None


class StatePatchRequest(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None


class StateResponse(BaseModel):
    user_id: str
    state: UserState


class InfoResponse(BaseModel):
    app_name: str
    python_version: str
    env: Dict[str, str]
    request: Dict[str, Any]


class FileMetadata(BaseModel):
    id: str
    name: str
    size: int
    type: str
    url: str
    filename: str
