from collections import defaultdict, deque
import os
import threading
import time

from fastapi import Depends, HTTPException, Request, status

from dependencies import get_optional_current_user


_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    with _lock:
        _buckets.clear()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first_ip = forwarded.split(",")[0].strip()
        if first_ip:
            return first_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        entries = _buckets[key]
        while entries and entries[0] <= cutoff:
            entries.popleft()
        if len(entries) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - entries[0])) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
                headers={"Retry-After": str(retry_after)},
            )
        entries.append(now)


def create_rate_limiter(
    scope: str,
    max_requests_env: str,
    default_max_requests: int,
    window_seconds_env: str = "RATE_LIMIT_WINDOW_SECONDS",
    default_window_seconds: int = 60,
):
    def _limit(
        request: Request,
        current_user=Depends(get_optional_current_user),
    ):
        max_requests = _int_env(max_requests_env, default_max_requests)
        window_seconds = _int_env(window_seconds_env, default_window_seconds)
        subject = f"user:{current_user.id}" if current_user else f"ip:{_client_ip(request)}"
        check_rate_limit(f"{scope}:{subject}", max_requests, window_seconds)

    return _limit
