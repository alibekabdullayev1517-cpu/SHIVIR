"""Redis fixed-window rate limiting.

A fixed-window counter (INCR + EXPIRE) is the smallest correct implementation of
the master plan's rate-limiting requirement. A true leaky/token-bucket via a Lua
script would be more precise at window boundaries but is unnecessary complexity
for V1 traffic levels.
"""

from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass
class RateLimitResult:
    allowed: bool
    scope: str | None = None  # which limit tripped: "fingerprint" | "link" | "global"


async def _check_window(redis: Redis, key: str, limit: int, window_seconds: int) -> bool:
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    return count <= limit


async def check_send_rate_limits(
    redis: Redis,
    *,
    fingerprint_hash: str,
    link_id: int,
    per_fingerprint_limit: int,
    per_fingerprint_window: int,
    per_link_limit: int,
    per_link_window: int,
    global_limit: int,
    global_window: int,
) -> RateLimitResult:
    if not await _check_window(
        redis, f"rl:fp:{fingerprint_hash}", per_fingerprint_limit, per_fingerprint_window
    ):
        return RateLimitResult(allowed=False, scope="fingerprint")

    if not await _check_window(redis, f"rl:link:{link_id}", per_link_limit, per_link_window):
        return RateLimitResult(allowed=False, scope="link")

    if not await _check_window(redis, "rl:global:send", global_limit, global_window):
        return RateLimitResult(allowed=False, scope="global")

    return RateLimitResult(allowed=True)
