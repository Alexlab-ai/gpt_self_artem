"""Persistent FSM storage backed by a local JSON file.

Drop-in replacement for aiogram MemoryStorage that survives bot restarts.
Data is flushed to disk on every write with a short debounce to avoid
excessive I/O under load.

Usage in main.py:
    from bot.storage import JsonFileStorage
    dp = Dispatcher(storage=JsonFileStorage("data/fsm_states.json"))

When Redis becomes available, simply swap to:
    from aiogram.fsm.storage.redis import RedisStorage
    dp = Dispatcher(storage=RedisStorage.from_url("redis://..."))
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType

logger = logging.getLogger(__name__)


class JsonFileStorage(BaseStorage):
    """File-backed FSM storage that persists state across restarts."""

    def __init__(self, path: str = "data/fsm_states.json", flush_delay: float = 1.0) -> None:
        self._path = Path(path)
        self._flush_delay = flush_delay
        self._data: Dict[str, Dict[str, Any]] = {}
        self._states: Dict[str, Optional[str]] = {}
        self._dirty = False
        self._flush_task: Optional[asyncio.Task] = None
        self._load()

    # ── Key helpers ──────────────────────────────────────────────

    @staticmethod
    def _key(key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}"

    # ── BaseStorage interface ────────────────────────────────────

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        k = self._key(key)
        if state is None:
            self._states.pop(k, None)
        elif isinstance(state, State):
            self._states[k] = state.state
        else:
            self._states[k] = str(state) if state else None
        self._schedule_flush()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        return self._states.get(self._key(key))

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        k = self._key(key)
        if data:
            self._data[k] = data
        else:
            self._data.pop(k, None)
        self._schedule_flush()

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        return self._data.get(self._key(key), {}).copy()

    async def close(self) -> None:
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        if self._dirty:
            self._flush_sync()

    # ── Persistence ──────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            logger.info("FSM storage file not found, starting fresh: %s", self._path)
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            snapshot = json.loads(raw) if raw.strip() else {}
            self._states = snapshot.get("states", {})
            self._data = snapshot.get("data", {})
            logger.info(
                "Loaded FSM storage: %d states, %d data entries from %s",
                len(self._states), len(self._data), self._path,
            )
        except Exception:
            logger.exception("Failed to load FSM storage from %s, starting fresh", self._path)
            self._states = {}
            self._data = {}

    def _flush_sync(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            snapshot = {"states": self._states, "data": self._data}
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(snapshot, ensure_ascii=False, default=str), encoding="utf-8")
            tmp.replace(self._path)
            self._dirty = False
        except Exception:
            logger.exception("Failed to flush FSM storage to %s", self._path)

    def _schedule_flush(self) -> None:
        self._dirty = True
        if self._flush_task and not self._flush_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._flush_task = loop.create_task(self._delayed_flush())
        except RuntimeError:
            self._flush_sync()

    async def _delayed_flush(self) -> None:
        await asyncio.sleep(self._flush_delay)
        self._flush_sync()
