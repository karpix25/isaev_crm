from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PendingTelegramTurn:
    task: Any
    items: list[dict[str, Any]] = field(default_factory=list)
    message: Any = None
    has_voice: bool = False


class TelegramTurnBuffer:
    def __init__(self) -> None:
        self._pending: dict[str, PendingTelegramTurn] = {}

    def add(
        self,
        key: str,
        *,
        item: dict[str, Any],
        message: Any,
        task_factory: Callable[[], Any],
    ) -> PendingTelegramTurn:
        is_voice = bool(item.get("is_voice"))
        current = self._pending.get(key)
        if current:
            self._cancel_task(current.task)
            current.items.append(item)
            current.has_voice = current.has_voice or is_voice
            current.task = task_factory()
            return current

        turn = PendingTelegramTurn(
            task=task_factory(),
            items=[item],
            message=message,
            has_voice=is_voice,
        )
        self._pending[key] = turn
        return turn

    def pop(self, key: str) -> PendingTelegramTurn | None:
        return self._pending.pop(key, None)

    def get(self, key: str) -> PendingTelegramTurn | None:
        return self._pending.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self._pending

    def clear(self) -> None:
        self._pending.clear()

    def _cancel_task(self, task: Any) -> None:
        cancel = getattr(task, "cancel", None)
        if callable(cancel):
            cancel()
