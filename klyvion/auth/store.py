"""User persistence.

``UserStore`` is the extension seam for where accounts live: the shipped
:class:`JsonUserStore` keeps them in a JSON file next to cloned voices, but a
future SQL or Redis backend is one subclass away — mirroring the engine and
voice-registry patterns used elsewhere in Klyvion.
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from klyvion.auth.models import User


class UserStore(ABC):
    """Abstract account store."""

    @abstractmethod
    def get(self, username: str) -> User | None:
        """Return the user with ``username`` (case-insensitive), or ``None``."""

    @abstractmethod
    def save(self, user: User) -> None:
        """Insert or replace ``user``."""

    @abstractmethod
    def atomic_update(self, username: str, mutator: Callable[[User], User]) -> User:
        """Read, transform and persist a user under a single lock.

        ``mutator`` receives the current :class:`User` and returns the replacement
        to persist. The read-modify-write happens atomically so concurrent
        requests (e.g. two synthesis calls debiting the same account) cannot
        interleave and lose an update. Use this for any balance change.

        Args:
            username: account to update (case-insensitive).
            mutator: pure function producing the new user from the current one.
                It may raise to abort the update (e.g. insufficient credits),
                in which case nothing is written.

        Returns:
            The persisted, post-mutation user.

        Raises:
            KeyError: if no such user exists.
        """


class JsonUserStore(UserStore):
    """Stores users in a single JSON file, keyed by lowercase username.

    Reads and writes are guarded by a lock so concurrent API requests cannot
    interleave a partial write. Suitable for the single-instance portfolio
    demo; swap in a database-backed :class:`UserStore` for multi-node use.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def get(self, username: str) -> User | None:
        key = username.lower()
        with self._lock:
            raw = self._read_all()
        record = raw.get(key)
        return User(**record) if record else None

    def save(self, user: User) -> None:
        key = user.username.lower()
        with self._lock:
            raw = self._read_all()
            raw[key] = asdict(user)
            self._write_all(raw)

    def atomic_update(self, username: str, mutator: Callable[[User], User]) -> User:
        key = username.lower()
        with self._lock:
            raw = self._read_all()
            record = raw.get(key)
            if record is None:
                raise KeyError(username)
            updated = mutator(User(**record))
            raw[key] = asdict(updated)
            self._write_all(raw)
        return updated

    def _write_all(self, raw: dict[str, dict]) -> None:
        self._path.write_text(
            json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8"
        )
