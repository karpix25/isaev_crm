from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PriceObjectionReply:
    text: str
    client_budget_text: str | None
    client_budget_rub: int | None
    budget_fit: str


PRICE_OBJECTION_MARKERS = (
    "дорого",
    "дороговато",
    "стоимость не подходит",
    "цена не подходит",
    "не подходит стоимость",
    "не подходит цена",
    "не по бюджету",
    "выше бюджета",
    "не потян",
    "не укладываемся",
    "не укладываюсь",
    "бюджет меньше",
)

BUDGET_PATTERNS = (
    re.compile(r"(?:до|около|примерно|ориентир(?:уемся)? на|рассчитывал[аи]? на)\s+(\d+(?:[.,]\d+)?)\s*(млн|миллион|миллиона|миллионов|к|тыс|тысяч)", re.I),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*(млн|миллион|миллиона|миллионов|к|тыс|тысяч)", re.I),
)


class PriceObjectionService:
    def looks_like_price_objection(self, text: str) -> bool:
        normalized = self._normalize(text)
        if not normalized:
            return False
        return any(marker in normalized for marker in PRICE_OBJECTION_MARKERS)

    def build_reply(self, *, lead, text: str) -> PriceObjectionReply:
        price = self._price_data(lead)
        price_label = str(price.get("label") or "").strip()
        price_lo = self._positive_int(price.get("lo"))
        price_hi = self._positive_int(price.get("hi"))
        budget_text, budget_rub = self._extract_budget(text)

        if not budget_rub:
            return PriceObjectionReply(
                text=(
                    "Понимаю, бюджет правда важный момент. "
                    "Подскажите, на какой ориентир вы рассчитывали? "
                    "Если разница небольшая, подскажу, где можно оптимизировать или разбить ремонт на этапы."
                ),
                client_budget_text=budget_text,
                client_budget_rub=budget_rub,
                budget_fit="unknown",
            )

        fit = self._budget_fit(budget_rub=budget_rub, price_lo=price_lo, price_hi=price_hi)
        if fit in {"inside_range", "near_low"}:
            estimate = f"по квизу вышло {price_label} без стройматериалов" if price_label else "мы близко к вашему ориентиру"
            text_reply = (
                f"Понял, ориентир {budget_text}. Тогда мы примерно рядом: {estimate}. "
                "Чтобы держаться ближе к нижней границе, обычно смотрим, что можно оставить, где не усложнять решения и что разбить на этапы. "
                "Лучше всего это понять после замера — можем подобрать удобное окно?"
            )
        elif fit == "below_range":
            estimate = f"по квизу ориентир получился {price_label} без стройматериалов" if price_label else "по комплексному ремонту бюджет может быть выше"
            text_reply = (
                f"Понял, ориентир {budget_text}. Честно: {estimate}, поэтому в ваш бюджет можем не попасть без сильной оптимизации. "
                "Если хотите, могу подсказать, какие работы обычно переносят на второй этап, чтобы понять, есть ли смысл двигаться дальше."
            )
        else:
            text_reply = (
                f"Понял, ориентир {budget_text}. Это уже рабочий диапазон для обсуждения. "
                "Давайте после замера спокойно уточним объемы и посмотрим, как собрать смету без лишних решений."
            )

        return PriceObjectionReply(
            text=text_reply,
            client_budget_text=budget_text,
            client_budget_rub=budget_rub,
            budget_fit=fit,
        )

    def mark_lead(self, *, lead, reply: PriceObjectionReply, source_text: str) -> dict[str, Any]:
        data = self._lead_data(lead)
        data["conversation_mode"] = "price_objection"
        data["conversation_mode_reason"] = source_text[:300]
        data["conversation_mode_updated_at"] = datetime.now(timezone.utc).isoformat()
        data["price_objection"] = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "client_text": source_text[:500],
            "client_budget_text": reply.client_budget_text,
            "client_budget_rub": reply.client_budget_rub,
            "budget_fit": reply.budget_fit,
        }
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        return data

    def _budget_fit(self, *, budget_rub: int, price_lo: int | None, price_hi: int | None) -> str:
        if price_lo and price_hi and price_lo <= budget_rub <= price_hi:
            return "inside_range"
        if price_lo and budget_rub >= int(price_lo * 0.85):
            return "near_low"
        if price_lo and budget_rub < int(price_lo * 0.85):
            return "below_range"
        return "unknown"

    def _extract_budget(self, text: str) -> tuple[str | None, int | None]:
        normalized = text.replace("ё", "е")
        for pattern in BUDGET_PATTERNS:
            match = pattern.search(normalized)
            if not match:
                continue
            value = float(match.group(1).replace(",", "."))
            unit = match.group(2).lower()
            multiplier = 1_000_000 if unit.startswith(("млн", "миллион")) else 1_000
            rub = int(value * multiplier)
            return match.group(0).strip(), rub

        if "миллион" in normalized.lower():
            return "до миллиона", 1_000_000
        return None, None

    def _price_data(self, lead) -> dict[str, Any]:
        data = self._lead_data(lead)
        quiz = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
        price = quiz.get("price") if isinstance(quiz.get("price"), dict) else {}
        return price

    def _lead_data(self, lead) -> dict[str, Any]:
        raw = getattr(lead, "extracted_data", None)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _positive_int(self, value: Any) -> int | None:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else None
        except Exception:
            return None

    def _normalize(self, text: str) -> str:
        return " ".join((text or "").lower().replace("ё", "е").split())


price_objection_service = PriceObjectionService()
