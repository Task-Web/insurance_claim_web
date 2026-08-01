import asyncio
import copy
from typing import Any, Callable, Dict, Optional

from .models import UserState
from .state_limits import BoundedStateStoreMixin

REPLACE_ON_PATCH_KEYS = {"current_claim", "submitted_claims", "uploads"}


def _deep_merge(dest: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in src.items():
        if key in REPLACE_ON_PATCH_KEYS:
            dest[key] = copy.deepcopy(value)
        elif key in dest and isinstance(dest[key], dict) and isinstance(value, dict):
            dest[key] = _deep_merge(dest[key], value)
        else:
            dest[key] = copy.deepcopy(value)
    return dest


class StateStore(BoundedStateStoreMixin):
    """In-memory state store keyed by user id."""

    def __init__(
        self,
        *,
        ttl_seconds: Optional[float] = None,
        max_entries: Optional[int] = None,
        max_total_bytes: Optional[int] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._states: Dict[str, UserState] = {}
        self._lock = asyncio.Lock()
        self._init_state_limits(
            ttl_seconds=ttl_seconds,
            max_entries=max_entries,
            max_total_bytes=max_total_bytes,
            clock=clock,
        )

    async def get_state(self, user_id: str) -> UserState:
        async with self._lock:
            now = self._prepare_state_access()
            state = self._states.get(user_id)
            if state is None:
                state = UserState()
                return self._store_state(user_id, state, now)
            self._mark_access(user_id, now)
            self._evict_lru()
            return state

    async def replace_state(self, user_id: str, new_state: Dict[str, Any]) -> UserState:
        async with self._lock:
            now = self._prepare_state_access()
            state = UserState(**new_state)
            return self._store_state(user_id, state, now)

    async def patch_state(
        self, user_id: str, patch: Dict[str, Any], note: Optional[str]
    ) -> UserState:
        async with self._lock:
            now = self._prepare_state_access()
            state = self._states.get(user_id, UserState())
            updated_data = _deep_merge(copy.deepcopy(state.data), patch)
            state.data = updated_data
            if note is not None:
                state.note = note
            state.touch()
            return self._store_state(user_id, state, now)

    async def reset_state(self, user_id: str) -> UserState:
        async with self._lock:
            now = self._prepare_state_access()
            state = UserState()
            return self._store_state(user_id, state, now)

    async def delete_state(self, user_id: str) -> None:
        async with self._lock:
            self._remove_tracked_state(user_id)

    async def save_claim_draft(self, user_id: str, draft: Dict[str, Any]) -> UserState:
        async with self._lock:
            now = self._prepare_state_access()
            state = self._states.get(user_id, UserState())
            state.data["current_claim"] = copy.deepcopy(draft)
            state.note = "Insurance claim draft saved"
            state.touch()
            return self._store_state(user_id, state, now)

    async def submit_claim(self, user_id: str, claim: Dict[str, Any]) -> UserState:
        async with self._lock:
            now = self._prepare_state_access()
            state = self._states.get(user_id, UserState())
            submitted = state.data.get("submitted_claims")
            claims = copy.deepcopy(submitted) if isinstance(submitted, list) else []
            claims.append(copy.deepcopy(claim))
            state.data["submitted_claims"] = claims
            state.data["current_claim"] = None
            state.note = "Insurance claim submitted"
            state.touch()
            return self._store_state(user_id, state, now)

    async def clear_claims(self, user_id: str) -> UserState:
        async with self._lock:
            now = self._prepare_state_access()
            state = self._states.get(user_id, UserState())
            state.data["current_claim"] = None
            state.data["submitted_claims"] = []
            state.data["uploads"] = []
            state.note = "Insurance claim data cleared"
            state.touch()
            return self._store_state(user_id, state, now)
