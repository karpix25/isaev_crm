from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from src.services.estimates.export_xlsx import export_isaev_estimate_xlsx
from src.services.estimates.fact_parser import estimate_facts_from_payload
from src.services.estimates.isaev_rules import build_isaev_estimate
from src.services.estimates.types import Estimate


def build_estimate_from_payload(payload: dict[str, Any]) -> Estimate:
    facts = estimate_facts_from_payload(payload)
    return build_isaev_estimate(facts)


def export_estimate_payload_xlsx(payload: dict[str, Any]) -> Path:
    estimate = build_estimate_from_payload(payload)
    with NamedTemporaryFile(prefix="isaev_estimate_", suffix=".xlsx", delete=False) as tmp:
        output_path = Path(tmp.name)
    return export_isaev_estimate_xlsx(estimate, output_path)
