import json
import time
from dataclasses import asdict, dataclass

import redis.asyncio as aioredis

from src.config import settings

TTL = 86400  # 24h — максимальное время жизни Gemini session handle


@dataclass
class StoredSession:
    session_id: str
    user_id: str
    system_prompt: str
    voice: str
    language: str
    created_at: float
    last_activity: float
    gemini_handle: str | None = None


class RedisSessionStore:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def save(self, session: StoredSession) -> None:
        r = await self._get_redis()
        session.last_activity = time.time()
        await r.setex(self._key(session.session_id), TTL, json.dumps(asdict(session)))

    async def get(self, session_id: str) -> StoredSession | None:
        r = await self._get_redis()
        raw = await r.get(self._key(session_id))
        if not raw:
            return None
        return StoredSession(**json.loads(raw))

    async def update_handle(self, session_id: str, handle: str) -> None:
        stored = await self.get(session_id)
        if stored:
            stored.gemini_handle = handle
            stored.last_activity = time.time()
            r = await self._get_redis()
            await r.setex(self._key(session_id), TTL, json.dumps(asdict(stored)))

    async def touch(self, session_id: str) -> None:
        stored = await self.get(session_id)
        if stored:
            await self.save(stored)

    async def delete(self, session_id: str) -> None:
        r = await self._get_redis()
        await r.delete(self._key(session_id))

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()


session_store = RedisSessionStore()
