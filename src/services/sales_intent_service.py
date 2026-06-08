from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SalesIntent:
    name: str
    confidence: float
    client_budget_text: str | None = None
    client_budget_rub: int | None = None
    reason: str = ""


_NEGATED_PRICE_PATTERNS = (
    re.compile(r"\bне\s+дорог", re.I),
    re.compile(r"\bнормальн[оаяые]+\s+цена", re.I),
)

_INTENT_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "do_not_contact",
        (
            "не пишите",
            "не звоните",
            "удалите",
            "отпишите",
            "больше не беспокойте",
        ),
    ),
    (
        "competitor_comparison",
        (
            "у других дешевле",
            "другая бригада",
            "конкурент",
            "нашли дешевле",
            "предложили дешевле",
            "есть дешевле",
        ),
    ),
    (
        "scope_confusion",
        (
            "что входит",
            "что включено",
            "за что",
            "почему такая цена",
            "откуда сумма",
        ),
    ),
    (
        "hidden_cost_fear",
        (
            "доплат",
            "скрыт",
            "потом дороже",
            "вырастет",
            "накрут",
        ),
    ),
    (
        "measurement_objection",
        (
            "замер не нужен",
            "не хочу замер",
            "без замера",
            "можно без выезда",
            "зачем замер",
        ),
    ),
    (
        "decision_maker_needed",
        (
            "посоветоваться",
            "с мужем",
            "с женой",
            "с супруг",
            "с партнер",
            "обсудить",
        ),
    ),
    (
        "price_objection",
        (
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
        ),
    ),
    (
        "thinking",
        (
            "подумаю",
            "надо подумать",
            "пока думаю",
            "вернусь позже",
        ),
    ),
)

_BUDGET_PATTERNS = (
    re.compile(
        r"(?:до|около|примерно|ориентир(?:уемся)? на|рассчитывал[аи]? на|бюджет)\s+"
        r"(\d+(?:[.,]\d+)?)\s*(млн|миллион|миллиона|миллионов|к|тыс|тысяч)",
        re.I,
    ),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*(млн|миллион|миллиона|миллионов|к|тыс|тысяч)", re.I),
)


class SalesIntentService:
    def classify(self, text: str) -> SalesIntent | None:
        normalized = self._normalize(text)
        if not normalized:
            return None

        budget_text, budget_rub = self.extract_budget(text)
        if budget_rub:
            return SalesIntent(
                name="budget_given",
                confidence=0.88,
                client_budget_text=budget_text,
                client_budget_rub=budget_rub,
                reason="client_budget_detected",
            )

        if any(pattern.search(normalized) for pattern in _NEGATED_PRICE_PATTERNS):
            return None

        for intent_name, markers in _INTENT_MARKERS:
            marker = next((item for item in markers if item in normalized), None)
            if marker:
                return SalesIntent(
                    name=intent_name,
                    confidence=0.86,
                    client_budget_text=budget_text,
                    client_budget_rub=budget_rub,
                    reason=marker,
                )

        return None

    def extract_budget(self, text: str) -> tuple[str | None, int | None]:
        normalized = str(text or "").replace("ё", "е")
        for pattern in _BUDGET_PATTERNS:
            match = pattern.search(normalized)
            if not match:
                continue
            value = float(match.group(1).replace(",", "."))
            unit = match.group(2).lower()
            multiplier = 1_000_000 if unit.startswith(("млн", "миллион")) else 1_000
            return match.group(0).strip(), int(value * multiplier)

        if "миллион" in normalized.lower():
            return "до миллиона", 1_000_000
        return None, None

    def _normalize(self, text: str) -> str:
        return " ".join(str(text or "").lower().replace("ё", "е").split())


sales_intent_service = SalesIntentService()
