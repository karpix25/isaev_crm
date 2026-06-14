from __future__ import annotations

import re


ROOM_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("санузел", ("сануз", "ванн", "туалет", "душев")),
    ("детская", ("детск",)),
    ("кухня", ("кухн",)),
    ("спальня", ("спальн",)),
    ("гостиная", ("гостин", "зал")),
    ("коридор", ("коридор", "прихож")),
    ("балкон/лоджия", ("балкон", "лодж")),
)


class LeadRequestFactExtractor:
    def extract(self, text: str) -> dict:
        normalized = (text or "").lower()
        zones = self._zones(normalized)
        facts: dict[str, object] = {}
        if zones:
            facts["renovation_zones"] = zones
            facts["rooms_description"] = ", ".join(zones)
        if self._has_design_reference(normalized):
            facts["design_reference_provided"] = True
        if self._asks_about_renovation(normalized) and zones:
            facts["client_request_summary"] = f"Клиент интересуется ремонтом: {', '.join(zones)}."
        return facts

    def merge(self, existing: dict, facts: dict) -> dict:
        if not facts:
            return existing
        merged = dict(existing or {})
        if facts.get("renovation_zones"):
            current = merged.get("renovation_zones")
            zones = [str(item) for item in current] if isinstance(current, list) else []
            for zone in facts["renovation_zones"]:
                if zone not in zones:
                    zones.append(zone)
            merged["renovation_zones"] = zones
            merged["rooms_description"] = ", ".join(zones)
        for key in ("design_reference_provided", "client_request_summary"):
            if facts.get(key):
                merged[key] = facts[key]
        return merged

    def _zones(self, normalized: str) -> list[str]:
        zones: list[str] = []
        for label, markers in ROOM_PATTERNS:
            if any(marker in normalized for marker in markers):
                zones.append(label)
        if re.search(r"\b(вся|всю|целиком)\s+квартир", normalized):
            zones.append("вся квартира")
        return zones

    def _has_design_reference(self, normalized: str) -> bool:
        return any(marker in normalized for marker in ("дизайн", "стил", "референс", "как нравится", "в таком стиле"))

    def _asks_about_renovation(self, normalized: str) -> bool:
        return any(marker in normalized for marker in ("ремонт", "отделк", "сануз", "детск", "комнат"))


lead_request_fact_extractor = LeadRequestFactExtractor()
