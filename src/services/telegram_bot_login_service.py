from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Optional

from src.services.redis_client import get_redis


@dataclass(frozen=True)
class TelegramBotLoginSession:
    state: str
    created_at: int
    expires_at: int
    telegram_id: Optional[int] = None
    full_name: Optional[str] = None
    username: Optional[str] = None


class TelegramBotLoginService:
    """
    One-time login handshake between web and Telegram bot:
      1) Web creates a session (state) and opens bot deep-link with that state.
      2) Bot approves the session by writing telegram_id into Redis.
      3) Web polls /status to exchange approved state for JWT tokens (then state is consumed).
    """

    KEY_PREFIX = "tg_login:"
    TTL_SECONDS = 5 * 60  # 5 minutes

    def _key(self, state: str) -> str:
        return f"{self.KEY_PREFIX}{state}"

    async def create_session(self) -> tuple[str, int]:
        state = secrets.token_urlsafe(16)
        now = int(time.time())
        expires_at = now + self.TTL_SECONDS

        r = get_redis()
        key = self._key(state)
        await r.hset(
            key,
            mapping={
                "state": state,
                "created_at": str(now),
                "expires_at": str(expires_at),
            },
        )
        await r.expire(key, self.TTL_SECONDS)
        return state, self.TTL_SECONDS

    async def get_session(self, state: str) -> Optional[TelegramBotLoginSession]:
        r = get_redis()
        key = self._key(state)
        data = await r.hgetall(key)
        if not data:
            return None
        try:
            telegram_id = int(data["telegram_id"]) if data.get("telegram_id") else None
        except Exception:
            telegram_id = None
        return TelegramBotLoginSession(
            state=state,
            created_at=int(data.get("created_at") or 0),
            expires_at=int(data.get("expires_at") or 0),
            telegram_id=telegram_id,
            full_name=data.get("full_name") or None,
            username=data.get("username") or None,
        )

    async def approve_session(
        self,
        state: str,
        telegram_id: int,
        full_name: str | None = None,
        username: str | None = None,
    ) -> bool:
        """
        Mark session as approved by a Telegram user.
        Returns False if the session does not exist / expired.
        """
        r = get_redis()
        key = self._key(state)

        exists = await r.exists(key)
        if not exists:
            return False

        await r.hset(
            key,
            mapping={
                "telegram_id": str(telegram_id),
                "full_name": full_name or "",
                "username": username or "",
                "approved_at": str(int(time.time())),
            },
        )
        return True

    async def consume_session(self, state: str) -> None:
        r = get_redis()
        await r.delete(self._key(state))


telegram_bot_login_service = TelegramBotLoginService()
