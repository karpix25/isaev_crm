from decimal import Decimal

import pytest

from src.services.estimates.isaev_rules import build_isaev_estimate
from src.services.estimates.fact_parser import estimate_facts_from_payload
from src.services.estimates.types import EstimateFacts
from src.services.estimates.vision_contract import VISION_EXTRACTION_PROMPT


def _muravskaya_facts() -> EstimateFacts:
    return EstimateFacts(
        address="ул. Муравская 38Б к2, кв. 1149",
        valid_until="20.05",
        replanning={
            "door_closure_area": Decimal("1.6"),
            "new_opening_count": Decimal("1"),
            "reinforcement_count": Decimal("1"),
            "opening_slope_length": Decimal("2.5"),
        },
        walls={
            "wall_area": Decimal("99.3"),
            "plaster_area": Decimal("36.8"),
            "bathroom_plaster_area": Decimal("19.6"),
        },
        installation={
            "block_partition_area": Decimal("16.9"),
            "block_closure_area": Decimal("1.6"),
        },
        electrical={
            "strobe_length": Decimal("50"),
            "cable_length": Decimal("200"),
            "strobe_seal_length": Decimal("50"),
            "socket_boxes": Decimal("20"),
            "panel_count": Decimal("1"),
            "outlets": Decimal("20"),
            "switches": Decimal("5"),
        },
        plumbing={
            "water_node_count": Decimal("1"),
            "hot_water_points": Decimal("3"),
            "cold_water_points": Decimal("7"),
            "water_heater_count": Decimal("1"),
            "ventilation_count": Decimal("2"),
            "sewer_points": Decimal("6"),
            "bath_count": Decimal("1"),
            "installation_count": Decimal("1"),
            "bath_binding_count": Decimal("1"),
        },
        tile={
            "waterproof_area": Decimal("24.7"),
            "waterproof_tape_length": Decimal("12"),
            "bathroom_primer_area": Decimal("24.7"),
            "bathroom_tile_area": Decimal("24.7"),
            "bath_screen_count": Decimal("1"),
        },
        finishing={"wallpaper_area": Decimal("99.3")},
        slopes={"rust_panel_length": Decimal("10.5")},
        floors={
            "floor_tile_area": Decimal("6.8"),
            "vinyl_area": Decimal("22.6"),
            "baseboard_length": Decimal("35.57"),
        },
    )


def test_build_isaev_estimate_matches_reference_totals():
    estimate = build_isaev_estimate(_muravskaya_facts())

    assert estimate.rough_total == Decimal("700826.0")
    assert estimate.clean_total == Decimal("442859.57")
    assert estimate.rough_discounted_total == Decimal("560660.800")
    assert estimate.clean_discounted_total == Decimal("354287.6560")
    assert estimate.discounted_total == Decimal("914948.4560")


def test_export_isaev_estimate_xlsx_uses_reference_format(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from src.services.estimates.export_xlsx import export_isaev_estimate_xlsx

    estimate = build_isaev_estimate(_muravskaya_facts())
    output_path = export_isaev_estimate_xlsx(estimate, tmp_path / "estimate.xlsx")

    wb = openpyxl.load_workbook(output_path, data_only=False)
    ws = wb.active

    assert ws["A1"].value == "СМЕТА"
    assert ws["A9"].value == "Черновые работы"
    assert ws["A43"].value == "Чистовые работы"
    assert ws["A75"].value == "ВСЕГО с учётом скидки* по черновым и чистовым работам"
    assert ws["F75"].value == 914948.456


def test_estimate_facts_from_payload_normalizes_llm_values():
    facts = estimate_facts_from_payload(
        {
            "address": "  объект  ",
            "discount_rate": "0,15",
            "walls": {"wall_area": "99,3", "plaster_area": None, "bathroom_plaster_area": "-4"},
            "electrical": {"strobe_length": "not visible"},
            "notes": ["нет площади перегородок", ""],
        }
    )

    assert facts.address == "объект"
    assert facts.discount_rate == Decimal("0.15")
    assert facts.walls["wall_area"] == Decimal("99.3")
    assert facts.walls["plaster_area"] == Decimal("0")
    assert facts.walls["bathroom_plaster_area"] == Decimal("0")
    assert facts.electrical["strobe_length"] == Decimal("0")
    assert facts.notes == ("нет площади перегородок",)


def test_vision_prompt_contains_isaev_methodology_guardrails():
    assert "Площадь комнаты никогда не равна площади перегородок" in VISION_EXTRACTION_PROMPT
    assert "panel_count — только силовой электрощит" in VISION_EXTRACTION_PROMPT
    assert "bathroom_tile_area — плитка санузла: стены + пол" in VISION_EXTRACTION_PROMPT
    assert "Натяжные потолки" in VISION_EXTRACTION_PROMPT
