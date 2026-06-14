from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AIReplyQualityResult:
    text: str
    score: int
    blocked: bool
    issues: tuple[str, ...]
    metadata: dict[str, Any]


class AIReplyQualityGateService:
    _ROOM_REPEAT_PATTERN = re.compile(
        r"(какие|какую|что)\s+(?:комнат|помещен|зон|ремонтир|делать)|"
        r"какие\s+конкретно\s+комнаты|что\s+именно\s+ремонт",
        flags=re.IGNORECASE,
    )
    _FAKE_IDENTITY_PATTERN = re.compile(
        r"\b(?:я\s+александр|меня\s+зовут\s+александр|я\s+(?:ии|ai)[-\s]?ассистент|я\s+бот)\b",
        flags=re.IGNORECASE,
    )
    _PASSIVE_WAIT_PATTERN = re.compile(
        r"(когда\s+будете\s+готов|дайте\s+сигнал|обращайтесь|буду\s+на\s+связи)",
        flags=re.IGNORECASE,
    )

    def validate(
        self,
        *,
        text: str,
        client_text: str,
        extracted_data: dict[str, Any] | None,
        stage_next_action: str | None = None,
    ) -> AIReplyQualityResult:
        normalized_text = str(text or "").strip()
        data = extracted_data if isinstance(extracted_data, dict) else {}
        issues: list[str] = []

        if self._FAKE_IDENTITY_PATTERN.search(normalized_text):
            issues.append("fake_identity")
        if self._repeats_known_room_question(normalized_text, data):
            issues.append("repeated_known_rooms")
        if self._question_count(normalized_text) > 1:
            issues.append("too_many_questions")
        if self._PASSIVE_WAIT_PATTERN.search(normalized_text):
            issues.append("passive_wait")

        blocked_issues = tuple(issue for issue in issues if issue in {"fake_identity", "repeated_known_rooms", "too_many_questions"})
        final_text = normalized_text
        if blocked_issues:
            final_text = self._fallback_text(data=data, stage_next_action=stage_next_action)

        score = max(0, 100 - len(blocked_issues) * 35 - (len(issues) - len(blocked_issues)) * 15)
        return AIReplyQualityResult(
            text=final_text,
            score=score,
            blocked=bool(blocked_issues),
            issues=tuple(issues),
            metadata={
                "score": score,
                "blocked": bool(blocked_issues),
                "issues": issues,
                "stage_next_action": stage_next_action,
                "client_text_sample": str(client_text or "")[:300],
            },
        )

    def _repeats_known_room_question(self, text: str, data: dict[str, Any]) -> bool:
        zones = self._known_zones(data)
        if not zones:
            return False
        return bool(self._ROOM_REPEAT_PATTERN.search(text))

    def _known_zones(self, data: dict[str, Any]) -> list[str]:
        zones = data.get("renovation_zones")
        if isinstance(zones, list):
            return [str(zone).strip() for zone in zones if str(zone).strip()]
        rooms = str(data.get("rooms_description") or "").strip()
        if rooms:
            return [part.strip() for part in rooms.split(",") if part.strip()]
        return []

    def _fallback_text(self, *, data: dict[str, Any], stage_next_action: str | None) -> str:
        zones = self._known_zones(data)
        if zones:
            zones_text = self._join_ru(zones)
            return f"По задаче понял: {zones_text}. Чтобы дать нормальную вилку по работам, подскажите примерную площадь?"

        if stage_next_action == "awaiting_measurement_slot":
            return "Чтобы не считать вслепую, лучше спокойно посмотреть объект на бесплатном замере. Подобрать удобное время?"

        return "Понял. Уточню один момент, чтобы ответить точнее: какая примерная площадь объекта?"

    def _join_ru(self, values: list[str]) -> str:
        clean = [value for value in values if value]
        if len(clean) <= 1:
            return clean[0] if clean else "объем работ"
        return f"{', '.join(clean[:-1])} и {clean[-1]}"

    def _question_count(self, text: str) -> int:
        return text.count("?")


ai_reply_quality_gate_service = AIReplyQualityGateService()
