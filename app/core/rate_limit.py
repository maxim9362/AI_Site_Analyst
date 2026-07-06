import time
from collections import defaultdict

from app.core.config import settings

# In-memory rate limiter for MVP. Not suitable for multi-worker production.
_buckets: dict[str, list[float]] = defaultdict(list)
_CLEANUP_INTERVAL = 60
_last_cleanup = time.time()


def _cleanup():
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    cutoff = now - 120
    empty_keys = []
    for key, timestamps in _buckets.items():
        _buckets[key] = [t for t in timestamps if t > cutoff]
        if not _buckets[key]:
            empty_keys.append(key)
    for key in empty_keys:
        del _buckets[key]


def check_rate_limit(key: str, limit: int | None = None) -> bool:
    """Returns True if request is allowed, False if rate limit exceeded."""
    _cleanup()
    max_per_minute = limit or settings.TRACKER_RATE_LIMIT_PER_MINUTE
    now = time.time()
    cutoff = now - 60
    timestamps = _buckets[key]
    _buckets[key] = [t for t in timestamps if t > cutoff]
    if len(_buckets[key]) >= max_per_minute:
        return False
    _buckets[key].append(now)
    return True
