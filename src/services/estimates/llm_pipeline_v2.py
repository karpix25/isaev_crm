import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any

from src.services.estimates.export_xlsx import export_isaev_estimate_xlsx
from src.services.estimates.extractor_prompts import EXTRACTOR_PROMPTS
from src.services.estimates.fact_merge import merge_fact_payloads
from src.services.estimates.fact_parser import estimate_facts_from_payload
from src.services.estimates.isaev_rules import build_isaev_estimate
from src.services.estimates.llm_pipeline import DEFAULT_MODEL, _load_openrouter_key, _post_openrouter_json
from src.services.estimates.page_selection import render_pages_for_extractors
from src.services.estimates.vision_contract import ESTIMATE_FACT_KEYS, VISION_EXTRACTION_PROMPT


def run_pdf_estimate_v2(pdf_path: Path, output_path: Path, model: str = DEFAULT_MODEL) -> tuple[Path, Path]:
    api_key = _load_openrouter_key()
    page_groups = render_pages_for_extractors(pdf_path, output_path.parent / f"{output_path.stem}_v2_pages")
    partials = []
    for extractor, pages in page_groups.items():
        if extractor not in EXTRACTOR_PROMPTS:
            continue
        partials.append(_extract_with_claude(extractor, pages, api_key=api_key, model=model))

    merged = merge_fact_payloads(partials)
    if not merged.get("address"):
        merged["address"] = pdf_path.stem
    facts_path = output_path.with_suffix(".facts.json")
    facts_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    estimate = build_isaev_estimate(estimate_facts_from_payload(merged))
    export_isaev_estimate_xlsx(estimate, output_path)
    return output_path, facts_path


def _extract_with_claude(extractor: str, pages: list[dict[str, Any]], api_key: str, model: str) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": _build_extractor_prompt(extractor, pages)}]
    for page in pages:
        image_b64 = base64.b64encode(Path(page["image_path"]).read_bytes()).decode("ascii")
        content.extend(
            [
                {"type": "text", "text": f"Страница {page['page']}. Текстовый слой: {page['text_excerpt']}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]
        )
    return _post_openrouter_json(
        messages=[
            {"role": "system", "content": VISION_EXTRACTION_PROMPT},
            {"role": "user", "content": content},
        ],
        api_key=api_key,
        model=model,
    )


def _build_extractor_prompt(extractor: str, pages: list[dict[str, Any]]) -> str:
    keys = json.dumps(ESTIMATE_FACT_KEYS, ensure_ascii=False, indent=2)
    page_list = ", ".join(str(page["page"]) for page in pages)
    return (
        f"Extractor: {extractor}. Страницы: {page_list}.\n"
        f"{EXTRACTOR_PROMPTS[extractor]}\n\n"
        "Верни полный JSON-контракт, но заполняй только свои разделы. "
        "Остальные разделы оставь нулями. Используй строго эти ключи:\n"
        f"{keys}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Isaev Group estimate with specialized LLM extractors.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/isaev_estimate_v2.xlsx"))
    parser.add_argument("--model", default=os.getenv("ESTIMATE_OPENROUTER_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    output, facts = run_pdf_estimate_v2(args.pdf, args.output, model=args.model)
    print(f"estimate={output}")
    print(f"facts={facts}")


if __name__ == "__main__":
    main()
