"""Small in-process TTL cache for expensive read responses.

The map re-requests the same viewport while the user pans back and forth, and the
dashboard polls. Caching identical GET responses for a few seconds removes most of
that work without any external service.

This is deliberately process-local: the API runs as one worker, and a restart
simply starts cold. Writes that change the data (ingestion) can call
``clear_caches``; the TTL also bounds staleness when they do not.
"""

from __future__ import annotations

import threading
import time
from typing import Any

MISS = object()

_registry: list[TTLCache] = []
_registry_lock = threading.Lock()


class TTLCache:
    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int = 128,
        name: str = "cache",
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max(1, max_entries)
        self.name = name
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        with _registry_lock:
            _registry.append(self)

    def get(self, key: str) -> Any:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.misses += 1
                return MISS
            expires, value = entry
            if expires <= now:
                del self._data[key]
                self.misses += 1
                return MISS
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self.max_entries and key not in self._data:
                # Drop the entry closest to expiry; insertion order is not age
                # order here, so this is cheap and good enough for a small cache.
                oldest = min(self._data, key=lambda item: self._data[item][0])
                del self._data[oldest]
                self.evictions += 1
            self._data[key] = (time.monotonic() + self.ttl_seconds, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "name": self.name,
                "entries": len(self._data),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate": round(self.hits / total, 4) if total else 0.0,
            }


def clear_caches() -> None:
    with _registry_lock:
        caches = list(_registry)
    for cache in caches:
        cache.clear()


def cache_stats() -> list[dict[str, Any]]:
    with _registry_lock:
        caches = list(_registry)
    return [cache.stats() for cache in caches]
