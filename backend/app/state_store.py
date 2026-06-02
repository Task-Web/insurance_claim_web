import asyncio
import copy
from typing import Any, Dict, Optional

from .models import UserState


REPLACE_ON_PATCH_KEYS = {"current_claim", "submitted_claims", "uploads"}


def _deep_merge(dest: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in src.items():
        if key in REPLACE_ON_PATCH_KEYS:
            dest[key] = copy.deepcopy(value)
        elif (
            key in dest
            and isinstance(dest[key], dict)
            and isinstance(value, dict)
        ):
            dest[key] = _deep_merge(dest[key], value)
        else:
            dest[key] = copy.deepcopy(value)
    return dest


class StateStore:
    """In-memory state store keyed by user id."""

    def __init__(self) -> None:
        self._states: Dict[str, UserState] = {}
        self._lock = asyncio.Lock()

    async def get_state(self, user_id: str) -> UserState:
        async with self._lock:
            state = self._states.get(user_id)
            if state is None:
                state = UserState()
                self._states[user_id] = state
            return state

    async def replace_state(self, user_id: str, new_state: Dict[str, Any]) -> UserState:
        async with self._lock:
            state = UserState(**new_state)
            self._states[user_id] = state
            return state

    async def patch_state(self, user_id: str, patch: Dict[str, Any], note: Optional[str]) -> UserState:
        async with self._lock:
            state = self._states.get(user_id, UserState())
            updated_data = _deep_merge(copy.deepcopy(state.data), patch)
            state.data = updated_data
            if note is not None:
                state.note = note
            state.touch()
            self._states[user_id] = state
            return state

    async def reset_state(self, user_id: str) -> UserState:
        async with self._lock:
            state = UserState()
            self._states[user_id] = state
            return state

    async def delete_state(self, user_id: str) -> None:
        async with self._lock:
            self._states.pop(user_id, None)
