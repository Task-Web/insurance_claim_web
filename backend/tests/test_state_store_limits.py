import pytest

from app.models import UserState
from app.state_store import StateStore


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_state_limit_defaults_and_environment(monkeypatch):
    monkeypatch.delenv("STATE_TTL_SECONDS", raising=False)
    monkeypatch.delenv("STATE_MAX_ENTRIES", raising=False)
    monkeypatch.delenv("STATE_MAX_TOTAL_BYTES", raising=False)
    store = StateStore()
    assert store._ttl_seconds == 43200
    assert store._max_entries == 1000
    assert store._max_total_bytes == 1024 * 1024 * 1024

    monkeypatch.setenv("STATE_TTL_SECONDS", "60")
    monkeypatch.setenv("STATE_MAX_ENTRIES", "7")
    monkeypatch.setenv("STATE_MAX_TOTAL_BYTES", "4096")
    configured = StateStore()
    assert configured._ttl_seconds == 60
    assert configured._max_entries == 7
    assert configured._max_total_bytes == 4096


@pytest.mark.asyncio
async def test_idle_ttl_refreshes_on_read():
    clock = FakeClock()
    store = StateStore(ttl_seconds=10, clock=clock)
    stale = await store.get_state("stale")
    active = await store.get_state("active")

    clock.advance(9)
    assert await store.get_state("active") is active
    clock.advance(2)
    await store.get_state("trigger")

    assert "stale" not in store._states
    assert store._states["active"] is active
    assert stale is not active


@pytest.mark.asyncio
async def test_entry_and_total_byte_limits_evict_lru():
    clock = FakeClock()
    entry_store = StateStore(max_entries=2, clock=clock)
    await entry_store.get_state("a")
    await entry_store.get_state("b")
    await entry_store.get_state("a")
    await entry_store.get_state("c")
    assert set(entry_store._states) == {"a", "c"}

    first = UserState(data={"blob": "a"})
    second = UserState(data={"blob": "b"})
    total_limit = (
        entry_store._serialized_size(first)
        + entry_store._serialized_size(second)
        - 1
    )
    byte_store = StateStore(max_total_bytes=total_limit, clock=clock)
    await byte_store.replace_state("first", first.model_dump())
    await byte_store.replace_state("second", second.model_dump())

    assert set(byte_store._states) == {"second"}
    assert byte_store._total_bytes <= total_limit


@pytest.mark.asyncio
async def test_existing_states_are_adopted_without_changing_dict_shape():
    store = StateStore()
    legacy = UserState(data={"legacy": True})
    store._states["legacy"] = legacy

    assert await store.get_state("legacy") is legacy
    assert store._state_sizes["legacy"] == store._serialized_size(legacy)
    assert store._total_bytes == store._state_sizes["legacy"]
