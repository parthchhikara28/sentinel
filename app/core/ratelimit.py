from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_current_user
from app.config import settings
from app.core.redis import redis
from app.db.models import User

# Atomic: INCR and EXPIRE run together inside Redis, so two concurrent
# requests cannot both see a count of 1 and both set a fresh window.
_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
if current > tonumber(ARGV[1]) then
    return 0
end
return 1
"""

_limiter = redis.register_script(_SCRIPT)


async def rate_limit(request: Request, user: User = Depends(get_current_user)) -> User:
    key = f"ratelimit:{user.id}"
    allowed = await _limiter(
        keys=[key],
        args=[settings.rate_limit_requests, settings.rate_limit_window_seconds],
    )
    if not allowed:
        ttl = await redis.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(ttl, 1))},
        )
    return user
