import json
import os
import time
from typing import Callable, Dict, Optional

from .models import UserState

DEFAULT_STATE_TTL_SECONDS = 12 * 60 * 60
DEFAULT_STATE_MAX_ENTRIES = 1000
DEFAULT_STATE_MAX_TOTAL_BYTES = 1024 * 1024 * 1024


def _positive_float(value: Optional[float], env_name: str, default: float) -> float:
    raw_value = value if value is not None else os.getenv(env_name, str(default))
    parsed = float(raw_value)
    if parsed <= 0:
        raise ValueError(f"{env_name} must be greater than zero")
    return parsed


def _positive_int(value: Optional[int], env_name: str, default: int) -> int:
    raw_value = value if value is not None else os.getenv(env_name, str(default))
    parsed = int(raw_value)
    if parsed <= 0:
        raise ValueError(f"{env_name} must be greater than zero")
    return parsed


class BoundedStateStoreMixin:
    """Lock-scoped TTL, LRU, and serialized-size accounting for state stores."""

    _states: Dict[str, UserState]

    def _init_state_limits(
        self,
        *,
        ttl_seconds: Optional[float] = None,
        max_entries: Optional[int] = None,
        max_total_bytes: Optional[int] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._ttl_seconds = _positive_float(
            ttl_seconds, "STATE_TTL_SECONDS", DEFAULT_STATE_TTL_SECONDS
        )
        self._max_entries = _positive_int(
            max_entries, "STATE_MAX_ENTRIES", DEFAULT_STATE_MAX_ENTRIES
        )
        self._max_total_bytes = _positive_int(
            max_total_bytes, "STATE_MAX_TOTAL_BYTES", DEFAULT_STATE_MAX_TOTAL_BYTES
        )
        self._clock = clock or time.monotonic
        self._last_access: Dict[str, float] = {}
        self._access_order: Dict[str, int] = {}
        self._state_sizes: Dict[str, int] = {}
        self._total_bytes = 0
        self._access_counter = 0

    @staticmethod
    def _serialized_size(state: UserState) -> int:
        payload = state.model_dump(mode="json")
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return len(serialized.encode("utf-8"))

    def _mark_access(self, user_id: str, now: float) -> None:
        self._access_counter += 1
        self._last_access[user_id] = now
        self._access_order[user_id] = self._access_counter

    def _remove_tracked_state(self, user_id: str) -> None:
        self._states.pop(user_id, None)
        self._last_access.pop(user_id, None)
        self._access_order.pop(user_id, None)
        self._total_bytes -= self._state_sizes.pop(user_id, 0)

    def _sync_existing_states(self, now: float) -> None:
        for user_id in list(self._state_sizes):
            if user_id not in self._states:
                self._last_access.pop(user_id, None)
                self._access_order.pop(user_id, None)
                self._total_bytes -= self._state_sizes.pop(user_id)

        # Preserve compatibility with a pre-existing or directly populated _states dict.
        for user_id, state in self._states.items():
            if user_id not in self._state_sizes:
                size = self._serialized_size(state)
                self._state_sizes[user_id] = size
                self._total_bytes += size
                self._mark_access(user_id, now)

    def _prepare_state_access(self) -> float:
        now = self._clock()
        self._sync_existing_states(now)
        expired = [
            user_id
            for user_id, last_access in self._last_access.items()
            if now - last_access >= self._ttl_seconds
        ]
        for user_id in expired:
            self._remove_tracked_state(user_id)
        return now

    def _store_state(self, user_id: str, state: UserState, now: float) -> UserState:
        previous_size = self._state_sizes.get(user_id, 0)
        current_size = self._serialized_size(state)
        self._states[user_id] = state
        self._state_sizes[user_id] = current_size
        self._total_bytes += current_size - previous_size
        self._mark_access(user_id, now)
        self._evict_lru()
        return state

    def _evict_lru(self) -> None:
        while (
            len(self._states) > self._max_entries
            or self._total_bytes > self._max_total_bytes
        ):
            user_id = min(
                self._states,
                key=lambda key: (
                    self._last_access.get(key, float("-inf")),
                    self._access_order.get(key, 0),
                ),
            )
            self._remove_tracked_state(user_id)
