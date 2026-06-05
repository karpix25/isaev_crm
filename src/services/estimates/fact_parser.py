from decimal import Decimal, InvalidOperation
from typing import Any

from src.services.estimates.types import EstimateFacts
from src.services.estimates.vision_contract import ESTIMATE_FACT_KEYS


def estimate_facts_from_payload(payload: dict[str, Any]) -> EstimateFacts:
    """Normalize LLM/Vision JSON into stable estimate facts."""
    normalized = {
        section: _normalize_section(payload.get(section, {}), keys)
        for section, keys in ESTIMATE_FACT_KEYS.items()
    }
    return EstimateFacts(
        address=str(payload.get("address") or "").strip(),
        valid_until=str(payload.get("valid_until") or "").strip(),
        discount_rate=_to_decimal(payload.get("discount_rate"), default=Decimal("0.20")),
        notes=tuple(str(note).strip() for note in payload.get("notes", []) if str(note).strip()),
        **normalized,
    )


def _normalize_section(value: Any, keys: tuple[str, ...]) -> dict[str, Decimal]:
    source = value if isinstance(value, dict) else {}
    return {key: _to_decimal(source.get(key)) for key in keys}


def _to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        result = value
    else:
        text = str(value).strip().replace(" ", "").replace(",", ".")
        try:
            result = Decimal(text)
        except InvalidOperation:
            return default
    return result if result >= 0 else default
