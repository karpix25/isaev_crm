from decimal import Decimal
from typing import Any

from src.services.estimates.fact_parser import estimate_facts_from_payload
from src.services.estimates.types import EstimateFacts
from src.services.estimates.vision_contract import ESTIMATE_FACT_KEYS


MIN_POSITIVE_KEYS = {"panel_count", "water_node_count", "bath_count", "water_heater_count"}


def merge_fact_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "address": "",
        "valid_until": "",
        "discount_rate": Decimal("0.20"),
        "notes": [],
    }
    for section, keys in ESTIMATE_FACT_KEYS.items():
        merged[section] = {key: Decimal("0") for key in keys}

    for payload in payloads:
        if not merged["address"] and payload.get("address"):
            merged["address"] = payload["address"]
        if not merged["valid_until"] and payload.get("valid_until"):
            merged["valid_until"] = payload["valid_until"]
        merged["notes"].extend(payload.get("notes") or [])
        for section, keys in ESTIMATE_FACT_KEYS.items():
            source = payload.get(section) or {}
            for key in keys:
                current = _to_decimal(merged[section][key])
                candidate = _to_decimal(source.get(key))
                merged[section][key] = _choose_value(key, current, candidate)

    return _serialize_payload(apply_commercial_fallbacks(estimate_facts_from_payload(merged)))


def apply_commercial_fallbacks(facts: EstimateFacts) -> EstimateFacts:
    electrical = dict(facts.electrical)
    plumbing = dict(facts.plumbing)
    tile = dict(facts.tile)
    walls = dict(facts.walls)
    notes = list(facts.notes)

    outlets = _to_decimal(electrical.get("outlets"))
    switches = _to_decimal(electrical.get("switches"))
    if _to_decimal(electrical.get("socket_boxes")) == 0 and outlets + switches > 0:
        electrical["socket_boxes"] = outlets + switches
        notes.append("Расчетно: подрозетники приняты по количеству розеток и выключателей.")
    if _to_decimal(electrical.get("strobe_length")) == 0 and outlets > 0:
        electrical["strobe_length"] = (outlets * Decimal("2.5")).quantize(Decimal("0.01"))
        electrical["strobe_seal_length"] = electrical["strobe_length"]
        notes.append("Расчетно: штробы приняты 2.5 м.п. на розеточную точку.")
    if _to_decimal(electrical.get("cable_length")) == 0 and outlets > 0:
        electrical["cable_length"] = (outlets * Decimal("10")).quantize(Decimal("0.01"))
        notes.append("Расчетно: кабель принят 10 м.п. на розеточную точку.")

    bathroom_floor = _to_decimal(tile.get("waterproof_area"))
    if _to_decimal(tile.get("bathroom_tile_area")) == 0 and bathroom_floor > 0:
        tile["bathroom_tile_area"] = (bathroom_floor * Decimal("4.7")).quantize(Decimal("0.01"))
        tile["bathroom_primer_area"] = tile["bathroom_tile_area"]
        notes.append("Расчетно: плитка санузла оценена как площадь пола × 4.7.")

    if _to_decimal(tile.get("waterproof_tape_length")) == 0 and bathroom_floor > 0:
        tile["waterproof_tape_length"] = Decimal("12")
        notes.append("Расчетно: гидроизоляционная лента принята 12 п.м.")

    floor_area = _to_decimal(facts.floors.get("floor_tile_area")) + _to_decimal(facts.floors.get("vinyl_area"))
    if _to_decimal(walls.get("wall_area")) == 0 and floor_area > 0:
        walls["wall_area"] = (floor_area * Decimal("3.2")).quantize(Decimal("0.01"))
        walls["plaster_area"] = (walls["wall_area"] * Decimal("0.4")).quantize(Decimal("0.01"))
        notes.append("Расчетно: площадь стен оценена по площади чистовых полов × 3.2.")

    return EstimateFacts(
        address=facts.address,
        valid_until=facts.valid_until,
        discount_rate=facts.discount_rate,
        replanning=facts.replanning,
        walls=walls,
        installation=facts.installation,
        electrical=electrical,
        plumbing=plumbing,
        tile=tile,
        finishing=facts.finishing,
        slopes=facts.slopes,
        floors=facts.floors,
        notes=tuple(notes),
    )


def _choose_value(key: str, current: Decimal, candidate: Decimal) -> Decimal:
    if candidate <= 0:
        return current
    if current <= 0:
        return candidate
    if key in MIN_POSITIVE_KEYS:
        return min(current, candidate)
    return max(current, candidate)


def _to_decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "."))
    except Exception:
        return Decimal("0")
    return result if result > 0 else Decimal("0")


def _serialize_payload(facts: EstimateFacts) -> dict[str, Any]:
    payload = {"address": facts.address, "valid_until": facts.valid_until, "discount_rate": facts.discount_rate, "notes": list(facts.notes)}
    for section in ESTIMATE_FACT_KEYS:
        payload[section] = getattr(facts, section)
    return payload
