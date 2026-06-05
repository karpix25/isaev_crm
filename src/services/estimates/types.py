from dataclasses import dataclass, field
from decimal import Decimal


Money = Decimal


@dataclass(frozen=True)
class EstimateLine:
    name: str
    price: Money
    quantity: Decimal
    unit: str
    section_no: int | str | None = None
    line_no: int | None = None

    @property
    def amount(self) -> Money:
        return self.price * self.quantity


@dataclass(frozen=True)
class EstimateSubsection:
    title: str
    section_no: int
    lines: tuple[EstimateLine, ...]

    @property
    def total(self) -> Money:
        return sum((line.amount for line in self.lines), Decimal("0"))


@dataclass(frozen=True)
class EstimateSection:
    title: str
    subsections: tuple[EstimateSubsection, ...]

    @property
    def total(self) -> Money:
        return sum((subsection.total for subsection in self.subsections), Decimal("0"))


@dataclass(frozen=True)
class Estimate:
    address: str
    valid_until: str
    sections: tuple[EstimateSection, ...]
    discount_rate: Decimal = Decimal("0.20")
    contract_term_text: str = "Срок выполнения работ по основной смете ____ дней"
    contract_text: str = "Договор подряда"
    notes: tuple[str, ...] = (
        "При просчёте стен проёмы не вычитаются",
        "Проёмы окон не вычитаются из общей сметы",
        "Сантехнические и электромонтажные работы корректируются по факту",
    )

    @property
    def rough_total(self) -> Money:
        return self.sections[0].total if self.sections else Decimal("0")

    @property
    def clean_total(self) -> Money:
        return self.sections[1].total if len(self.sections) > 1 else Decimal("0")

    @property
    def rough_discounted_total(self) -> Money:
        return self.rough_total * (Decimal("1") - self.discount_rate)

    @property
    def clean_discounted_total(self) -> Money:
        return self.clean_total * (Decimal("1") - self.discount_rate)

    @property
    def discounted_total(self) -> Money:
        return self.rough_discounted_total + self.clean_discounted_total


@dataclass(frozen=True)
class EstimateFacts:
    address: str
    valid_until: str = ""
    discount_rate: Decimal = Decimal("0.20")
    replanning: dict[str, Decimal] = field(default_factory=dict)
    walls: dict[str, Decimal] = field(default_factory=dict)
    installation: dict[str, Decimal] = field(default_factory=dict)
    electrical: dict[str, Decimal] = field(default_factory=dict)
    plumbing: dict[str, Decimal] = field(default_factory=dict)
    tile: dict[str, Decimal] = field(default_factory=dict)
    finishing: dict[str, Decimal] = field(default_factory=dict)
    slopes: dict[str, Decimal] = field(default_factory=dict)
    floors: dict[str, Decimal] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
