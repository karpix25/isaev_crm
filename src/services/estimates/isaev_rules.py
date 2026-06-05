from decimal import Decimal

from src.services.estimates.catalog import ISAEV_PRICES
from src.services.estimates.types import Estimate, EstimateFacts, EstimateLine, EstimateSection, EstimateSubsection


def q(source: dict[str, Decimal], key: str) -> Decimal:
    value = source.get(key, Decimal("0"))
    if isinstance(value, Decimal):
        return value if value >= 0 else Decimal("0")
    try:
        normalized = Decimal(str(value).strip().replace(" ", "").replace(",", "."))
    except Exception:
        return Decimal("0")
    return normalized if normalized >= 0 else Decimal("0")


def line(line_no: int, name: str, quantity: Decimal, unit: str) -> EstimateLine:
    return EstimateLine(
        line_no=line_no,
        name=name,
        price=ISAEV_PRICES[name],
        quantity=quantity,
        unit=unit,
    )


def build_isaev_estimate(facts: EstimateFacts) -> Estimate:
    rough = EstimateSection(
        title="Черновые работы",
        subsections=(
            _replanning(facts),
            _wall_plastering(facts),
            _installation(facts),
            _electrical_first_stage(facts),
            _plumbing_first_stage(facts),
        ),
    )
    clean = EstimateSection(
        title="Чистовые работы",
        subsections=(
            _bathroom_tile(facts),
            _wall_finishing(facts),
            _slopes(facts),
            _clean_floors(facts),
            _electrical_second_stage(facts),
            _plumbing_second_stage(facts),
        ),
    )
    return Estimate(
        address=facts.address,
        valid_until=facts.valid_until,
        discount_rate=facts.discount_rate,
        sections=(rough, clean),
    )


def _replanning(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.replanning
    return EstimateSubsection(
        title="Перепланировка",
        section_no=1,
        lines=(
            line(1, "Заложить дверной проём при входе (2.0×0.8м)", q(data, "door_closure_area"), "кв.м"),
            line(2, "Прорезать новый дверной проём кухня→спальня (2.0×0.8м)", q(data, "new_opening_count"), "шт"),
            line(3, "Усиление дверного проёма (металлическая перемычка)", q(data, "reinforcement_count"), "шт"),
            line(4, "Оштукатуривание откосов нового дверного проёма", q(data, "opening_slope_length"), "м.п"),
        ),
    )


def _wall_plastering(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.walls
    wall_area = q(data, "wall_area")
    return EstimateSubsection(
        title="Штукатурка стен",
        section_no=3,
        lines=(
            line(5, "Грунтовка стен", wall_area, "кв.м"),
            line(6, "Штукатурка стен по маякам (кухня, коридор, гостиная)", q(data, "plaster_area"), "кв.м"),
            line(7, "Штукатурка стен санузла под плитку", q(data, "bathroom_plaster_area"), "кв.м"),
            line(8, "Ошкуривание стен", wall_area, "кв.м"),
            line(9, "Шпаклёвка базовая стен", wall_area, "кв.м"),
            line(10, "Шпаклёвка финишная стен", wall_area, "кв.м"),
        ),
    )


def _installation(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.installation
    return EstimateSubsection(
        title="Монтажные работы",
        section_no=2,
        lines=(
            line(11, "Монтаж перегородок из блока", q(data, "block_partition_area"), "кв.м"),
            line(12, "Заложить дверной проём при входе (2.0×0.8м) - блоки", q(data, "block_closure_area"), "кв.м"),
        ),
    )


def _electrical_first_stage(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.electrical
    return EstimateSubsection(
        title="Электромонтажные работы 1 этап",
        section_no=3,
        lines=(
            line(13, "Штробление под электрику", q(data, "strobe_length"), "м.п"),
            line(14, "Прокладка электрокабеля", q(data, "cable_length"), "м.п"),
            line(15, "Заделка штроб", q(data, "strobe_seal_length"), "м.п"),
            line(16, "Монтаж подрозетников", q(data, "socket_boxes"), "шт"),
            line(17, "Сборка и подключение нового щита силового", q(data, "panel_count"), "компл"),
        ),
    )


def _plumbing_first_stage(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.plumbing
    return EstimateSubsection(
        title="Сантехнические работы 1 этап (коллекторная разводка)",
        section_no=4,
        lines=(
            line(18, "Сборка узла водоснабжения (коллектор/гребёнка, кран, фильтр, счётчик)", q(data, "water_node_count"), "компл"),
            line(19, "Разводка труб горячей воды (ГВС: кухня 1 точка + санузел 2 точка)", q(data, "hot_water_points"), "шт"),
            line(20, "Разводка труб холодной воды (ХВС: кухня 2 точки + санузел 3)", q(data, "cold_water_points"), "шт"),
            line(21, "Установка проточного водонагревателя (с обвязкой)", q(data, "water_heater_count"), "шт"),
            line(22, "Монтаж вентиляции", q(data, "ventilation_count"), "шт"),
            line(23, "Разводка канализации (5 точек: ванна, раковина санузел, унитаз, кухня)", q(data, "sewer_points"), "шт"),
        ),
    )


def _bathroom_tile(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.tile
    return EstimateSubsection(
        title="Плитка стены санузлы (гидроизоляция и облицовка)",
        section_no=5,
        lines=(
            line(24, "Гидроизоляция пола и стен санузла (обмазочная)", q(data, "waterproof_area"), "кв.м"),
            line(25, "Проклейка гидроизоляционной лентой (углы и примыкания)", q(data, "waterproof_tape_length"), "пм"),
            line(26, "Грунтовка санузла под плитку", q(data, "bathroom_primer_area"), "кв.м"),
            line(27, "Укладка керамогранита 60×60 в санузле (пол+стены)", q(data, "bathroom_tile_area"), "кв.м"),
            line(28, "Экран из плитки под ванну", q(data, "bath_screen_count"), "компл"),
            line(29, "Чистовой рез керамогранита санузел (уточняется по факту)", q(data, "bathroom_clean_cut_length"), "м.п"),
            line(30, "Черновой рез керамогранита санузел (уточняется по факту)", q(data, "bathroom_rough_cut_length"), "м.п"),
            line(31, "Запил под 45° санузел (уточняется по факту)", q(data, "bathroom_45_cut_length"), "м.п"),
        ),
    )


def _wall_finishing(facts: EstimateFacts) -> EstimateSubsection:
    return EstimateSubsection(
        title="Малярные работы стены",
        section_no=6,
        lines=(line(32, "Поклейка обоев (гостиная+спальня+коридор)", q(facts.finishing, "wallpaper_area"), "кв.м"),),
    )


def _slopes(facts: EstimateFacts) -> EstimateSubsection:
    return EstimateSubsection(
        title="Откосы",
        section_no=7,
        lines=(line(33, "Откосы из рустпанелей на окнах (3 окна × 3.5 пм)", q(facts.slopes, "rust_panel_length"), "пм"),),
    )


def _clean_floors(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.floors
    return EstimateSubsection(
        title="Полы (чистовые)",
        section_no=8,
        lines=(
            line(34, "Укладка керамогранита 60×60 при входе и кухне (пол)", q(data, "floor_tile_area"), "кв.м"),
            line(35, "Укладка кварцвинила (гостиная/спальня)", q(data, "vinyl_area"), "кв.м"),
            line(36, "Чистовой рез керамогранита кухня/коридор (уточняется по факту)", q(data, "floor_clean_cut_length"), "м.п"),
            line(37, "Монтаж плинтуса", q(data, "baseboard_length"), "м.п"),
            line(38, "Черновой рез керамогранита кухня/коридор (уточняется по факту)", q(data, "floor_rough_cut_length"), "м.п"),
        ),
    )


def _electrical_second_stage(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.electrical
    return EstimateSubsection(
        title="Электромонтажные работы 2 этап",
        section_no=9,
        lines=(
            line(39, "Установка розеток", q(data, "outlets"), "шт"),
            line(49, "Установка выключателей одноклавишных", q(data, "switches"), "шт"),
        ),
    )


def _plumbing_second_stage(facts: EstimateFacts) -> EstimateSubsection:
    data = facts.plumbing
    return EstimateSubsection(
        title="Сантехнические работы 2 этап",
        section_no=10,
        lines=(
            line(41, "Установка ванны", q(data, "bath_count"), "шт"),
            line(42, "Установка инсталяции", q(data, "installation_count"), "шт"),
            line(43, "Обвязка ванны", q(data, "bath_binding_count"), "компл"),
        ),
    )
