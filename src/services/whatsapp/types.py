from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WhatsAppAttachment:
    url: str | None = None
    data_base64: str | None = None
    filename: str | None = None
    mimetype: str | None = None
    size: int | None = None


@dataclass(frozen=True)
class WhatsAppIncomingMessage:
    provider: str
    chat_id: str
    message_id: str | None
    text: str
    sender_name: str | None = None
    instance: str | None = None
    raw: dict[str, Any] | None = None
    attachment: WhatsAppAttachment | None = None


@dataclass(frozen=True)
class WhatsAppSendResult:
    provider: str
    message_id: str | None = None
    chat_id: str | None = None
    raw: dict[str, Any] | None = None
