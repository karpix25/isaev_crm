"""Structured contract for LLM/Vision extraction.

The LLM should extract facts only. Price selection and arithmetic stay in
`isaev_rules.py`, so the same facts always produce the same estimate.
"""

from src.services.estimates.isaev_methodology import ISAEV_ESTIMATE_METHODOLOGY


ESTIMATE_FACT_KEYS = {
    "replanning": (
        "door_closure_area",
        "new_opening_count",
        "reinforcement_count",
        "opening_slope_length",
    ),
    "walls": ("wall_area", "plaster_area", "bathroom_plaster_area"),
    "installation": ("block_partition_area", "block_closure_area"),
    "electrical": (
        "strobe_length",
        "cable_length",
        "strobe_seal_length",
        "socket_boxes",
        "panel_count",
        "outlets",
        "switches",
    ),
    "plumbing": (
        "water_node_count",
        "hot_water_points",
        "cold_water_points",
        "water_heater_count",
        "ventilation_count",
        "sewer_points",
        "bath_count",
        "installation_count",
        "bath_binding_count",
    ),
    "tile": (
        "waterproof_area",
        "waterproof_tape_length",
        "bathroom_primer_area",
        "bathroom_tile_area",
        "bath_screen_count",
        "bathroom_clean_cut_length",
        "bathroom_rough_cut_length",
        "bathroom_45_cut_length",
    ),
    "finishing": ("wallpaper_area",),
    "slopes": ("rust_panel_length",),
    "floors": (
        "floor_tile_area",
        "vinyl_area",
        "baseboard_length",
        "floor_clean_cut_length",
        "floor_rough_cut_length",
    ),
}


VISION_EXTRACTION_PROMPT = """
Ты инженер-сметчик Isaev Group. Твоя задача — не составлять смету, а извлечь
из дизайн-проекта факты для расчетного ядра.

__METHODOLOGY__

Ответь строго JSON без markdown. Все числа — в метрах, квадратных метрах или штуках.
Если значение не видно или нельзя надежно вывести, ставь 0 и добавляй причину в notes.

Правила:
- Натяжные потолки не включай как работу.
- Демонтаж включай только если это явно коммерчески считается в проекте.
- Стены считай без вычета дверных и оконных проемов, если нет иной ведомости.
- Электрика: длина штроб, длина кабеля и количество точек — разные значения.
- Сантехника: отдельно ГВС, ХВС, канализация, узел водоснабжения и 2 этап.
- Плитка санузла включает стены и пол санузла, а чистовые полы считаются отдельно.
- Строки "уточняется по факту" должны возвращаться количеством 0.

JSON:
{
  "address": "",
  "valid_until": "",
  "replanning": {},
  "walls": {},
  "installation": {},
  "electrical": {},
  "plumbing": {},
  "tile": {},
  "finishing": {},
  "slopes": {},
  "floors": {},
  "discount_rate": 0.20,
  "notes": []
}
""".strip().replace("__METHODOLOGY__", ISAEV_ESTIMATE_METHODOLOGY)
