from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.models import Lead, LeadStatus


@dataclass(frozen=True)
class FollowupPauseDecision:
    next_followup_at: datetime | None
    status: str | None
    reason: str | None
    extracted_patch: dict[str, Any]

    @property
    def should_pause(self) -> bool:
        return self.next_followup_at is not None


class LeadFollowupPauseService:
    MIN_DELAY_DAYS = 21
    DEFAULT_KEYS_DELAY_DAYS = 30
    MAX_DELAY_DAYS = 75

    _KEYS_PATTERNS = (
        r"\bключ[аи]?\b",
        r"\bполучим\s+ключ",
        r"\bсда[её]тся\b",
        r"\bсдадут\b",
        r"\bне\s+сдан[аоы]?\b",
        r"\bдом\s+не\s+сдан\b",
        r"\bквартира\s+не\s+сдан[а]?\b",
        r"\bжд[её]м\s+(?:сдач|ключ)",
        r"\bпока\s+рано\b",
        r"\bещ[её]\s+рано\b",
    )
    _MONTHS_PATTERN = re.compile(
        r"(?:через|в\s+течени[еи]|примерно|около|жд[её]м)?\s*"
        r"(?P<first>\d{1,2})\s*(?:[-–—]\s*(?P<second>\d{1,2}))?\s*"
        r"(?P<unit>мес(?:яц(?:а|ев)?)?|месяц(?:а|ев)?|нед(?:ел[яьиь])?)",
        flags=re.IGNORECASE,
    )
    _ACKNOWLEDGEMENT_PATTERN = re.compile(
        r"^\s*(?:хорошо|ок|окей|понял[аи]?|спасибо|благодарю|да|ага|угу|принял[аи]?)"
        r"(?:[\s,.!🙏✅-]*(?:спасибо|благодарю)?)?\s*$",
        flags=re.IGNORECASE,
    )

    def build_decision(self, lead: Lead, message_text: str, now: datetime | None = None) -> FollowupPauseDecision:
        now = self._aware(now or datetime.now(timezone.utc))
        text = (message_text or "").strip()
        normalized = text.lower().replace("ё", "е")

        delay_days = self._extract_delay_days(normalized)
        has_keys_context = any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in self._KEYS_PATTERNS)

        if not has_keys_context and delay_days is None:
            return FollowupPauseDecision(None, None, None, {})

        if delay_days is None:
            delay_days = self.DEFAULT_KEYS_DELAY_DAYS

        delay_days = max(self.MIN_DELAY_DAYS, min(delay_days, self.MAX_DELAY_DAYS))
        next_followup_at = now + timedelta(days=delay_days)
        reason = "keys_or_handover_wait"

        return FollowupPauseDecision(
            next_followup_at=next_followup_at,
            status=LeadStatus.KEYS_PENDING.value,
            reason=reason,
            extracted_patch={
                "followup_pause": {
                    "reason": reason,
                    "source_message": text[:500],
                    "detected_at": now.isoformat(),
                    "next_followup_at": next_followup_at.isoformat(),
                    "delay_days": delay_days,
                    "client_context": self._build_client_context(normalized),
                    "followup_goal": (
                        "Мягко узнать, появились ли новости по сдаче объекта или получению ключей. "
                        "Если ключи уже близко, предложить заранее подобрать удобное окно бесплатного замера."
                    ),
                }
            },
        )

    def merge_extracted_data(self, raw_data: str | None, patch: dict[str, Any]) -> str:
        data = self._parse_json(raw_data)
        data.update(patch)
        return json.dumps(data, ensure_ascii=False)

    def should_keep_existing_pause(self, lead: Lead, message_text: str) -> bool:
        if not getattr(lead, "next_followup_at", None):
            return False

        data = self._parse_json(getattr(lead, "extracted_data", None))
        pause = data.get("followup_pause")
        if not isinstance(pause, dict):
            return False

        return bool(self._ACKNOWLEDGEMENT_PATTERN.match(message_text or ""))

    def _extract_delay_days(self, text: str) -> int | None:
        match = self._MONTHS_PATTERN.search(text)
        if not match:
            return None

        first = int(match.group("first"))
        value = first
        unit = match.group("unit")

        if unit.startswith("нед"):
            return value * 7
        return value * 30

    def _build_client_context(self, text: str) -> str:
        if "не сдан" in text or "сда" in text:
            return "Клиент ждет сдачу квартиры/дома и пока не готов к замеру."
        if "ключ" in text:
            return "Клиент ждет получение ключей или доступ на объект."
        return "Клиент просит вернуться позже, потому что сейчас рано двигаться к замеру."

    @staticmethod
    def _parse_json(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


lead_followup_pause_service = LeadFollowupPauseService()
