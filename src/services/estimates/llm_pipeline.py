import argparse
import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import fitz
import httpx

from src.services.estimates.export_xlsx import export_isaev_estimate_xlsx
from src.services.estimates.fact_parser import estimate_facts_from_payload
from src.services.estimates.isaev_rules import build_isaev_estimate
from src.services.estimates.vision_contract import ESTIMATE_FACT_KEYS, VISION_EXTRACTION_PROMPT


DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
BATCH_SIZE = 6
RELEVANT_PAGE_MARKERS = (
    "исходный план",
    "помещения",
    "перегород",
    "сантех",
    "водоснаб",
    "розет",
    "освещ",
    "выключ",
    "напольн",
    "отделка стен",
    "гидроизоля",
    "развертк",
)


def run_pdf_estimate(
    pdf_path: Path,
    output_path: Path,
    model: str = DEFAULT_MODEL,
    max_pages: int = 24,
    input_mode: str = "pages",
) -> tuple[Path, Path]:
    api_key = _load_openrouter_key()
    if input_mode == "pdf":
        pages = []
        payload = call_openrouter_pdf_for_facts(pdf_path, api_key=api_key, model=model)
    else:
        pages = render_relevant_pages(pdf_path, output_path.parent / f"{output_path.stem}_pages", max_pages=max_pages)
        payload = call_openrouter_for_facts(pages, api_key=api_key, model=model)
    payload.setdefault("address", _infer_address(pdf_path, pages))
    payload_path = output_path.with_suffix(".facts.json")
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    facts = estimate_facts_from_payload(payload)
    estimate = build_isaev_estimate(facts)
    export_isaev_estimate_xlsx(estimate, output_path)
    return output_path, payload_path


def call_openrouter_pdf_for_facts(pdf_path: Path, api_key: str, model: str) -> dict[str, Any]:
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    keys = json.dumps(ESTIMATE_FACT_KEYS, ensure_ascii=False, indent=2)
    prompt = (
        "Извлеки факты для сметы Исаев Групп из полного PDF дизайн-проекта. "
        "Прочитай планы, развертки, легенды, экспликации и ведомости. "
        "Верни только JSON по контракту. Не составляй смету и не придумывай цены. "
        "Запрещено создавать новые названия ключей вроде plaster_m2 или outlets_pcs. "
        "Используй только эти ключи внутри разделов; если данные есть под другим названием, "
        f"переложи их в ближайший допустимый ключ:\n{keys}"
    )
    return _post_openrouter_json(
        messages=[
            {"role": "system", "content": VISION_EXTRACTION_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "file",
                        "file": {
                            "filename": pdf_path.name,
                            "file_data": f"data:application/pdf;base64,{pdf_b64}",
                        },
                    },
                ],
            },
        ],
        api_key=api_key,
        model=model,
    )


def render_relevant_pages(pdf_path: Path, out_dir: Path, max_pages: int = 16) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    selected: list[dict[str, Any]] = []
    for index, page in enumerate(doc):
        text = page.get_text("text") or ""
        lowered = text.lower()
        if any(marker in lowered for marker in RELEVANT_PAGE_MARKERS):
            pix = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
            image_path = out_dir / f"page_{index + 1:02d}.jpg"
            pix.save(str(image_path), jpg_quality=82)
            selected.append(
                {
                    "page": index + 1,
                    "image_path": image_path,
                    "text_excerpt": _compact_text(text),
                }
            )
        if len(selected) >= max_pages:
            break
    if not selected and len(doc):
        page = doc.load_page(0)
        image_path = out_dir / "page_01.jpg"
        page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False).save(str(image_path), jpg_quality=82)
        selected.append({"page": 1, "image_path": image_path, "text_excerpt": _compact_text(page.get_text("text") or "")})
    return selected


def call_openrouter_for_facts(pages: list[dict[str, Any]], api_key: str, model: str) -> dict[str, Any]:
    if len(pages) <= BATCH_SIZE:
        return _call_openrouter_page_batch(pages, api_key=api_key, model=model)

    partials = []
    for start in range(0, len(pages), BATCH_SIZE):
        batch = pages[start : start + BATCH_SIZE]
        partials.append(_call_openrouter_page_batch(batch, api_key=api_key, model=model))
    return _consolidate_facts(partials, api_key=api_key, model=model)


def _call_openrouter_page_batch(pages: list[dict[str, Any]], api_key: str, model: str) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": _build_user_prompt(pages)}]
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


def _consolidate_facts(partials: list[dict[str, Any]], api_key: str, model: str) -> dict[str, Any]:
    prompt = (
        "Объедини частичные JSON-факты по страницам дизайн-проекта в один финальный JSON. "
        "Не суммируй дублирующиеся площади с разных листов. Для одного и того же ключа выбирай "
        "самое надежное ненулевое значение, сверяй notes, сохраняй причины неопределенности. "
        "Верни только JSON в том же контракте.\n\n"
        f"Частичные факты:\n{json.dumps(partials, ensure_ascii=False, indent=2)}"
    )
    return _post_openrouter_json(
        messages=[
            {"role": "system", "content": VISION_EXTRACTION_PROMPT},
            {"role": "user", "content": prompt},
        ],
        api_key=api_key,
        model=model,
    )


def _post_openrouter_json(messages: list[dict[str, Any]], api_key: str, model: str) -> dict[str, Any]:
    response = None
    for attempt in range(1, 4):
        try:
            response = httpx.post(
                f"{os.getenv('OPENROUTER_BASE_URL', DEFAULT_BASE_URL).rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://renovation-crm.com",
                    "X-Title": "Isaev CRM Estimate",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 6000,
                    "response_format": {"type": "json_object"},
                },
                timeout=180,
            )
            response.raise_for_status()
            break
        except (httpx.RequestError, httpx.HTTPStatusError):
            if attempt == 3:
                raise
            time.sleep(2 * attempt)
    if response is None:
        raise RuntimeError("OpenRouter request did not return a response")
    data = response.json()
    if "choices" not in data:
        raise RuntimeError(f"OpenRouter returned no choices: {json.dumps(data, ensure_ascii=False)[:1600]}")
    return _extract_json(data["choices"][0]["message"]["content"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Isaev Group estimate from PDF through OpenRouter Vision.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/isaev_estimate_from_pdf.xlsx"))
    parser.add_argument("--model", default=os.getenv("ESTIMATE_OPENROUTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--max-pages", type=int, default=24)
    parser.add_argument("--input-mode", choices=("pages", "pdf"), default="pages")
    args = parser.parse_args()

    output, facts = run_pdf_estimate(
        args.pdf,
        args.output,
        model=args.model,
        max_pages=args.max_pages,
        input_mode=args.input_mode,
    )
    print(f"estimate={output}")
    print(f"facts={facts}")


def _build_user_prompt(pages: list[dict[str, Any]]) -> str:
    keys = json.dumps(ESTIMATE_FACT_KEYS, ensure_ascii=False, indent=2)
    listed = ", ".join(f"{page['page']}" for page in pages)
    return (
        "Извлеки факты для сметы Исаев Групп из приложенных страниц PDF. "
        f"Приложены страницы: {listed}. Верни только JSON. "
        f"Используй только эти ключи для разделов:\n{keys}"
    )


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _load_openrouter_key() -> str:
    _load_env_file(Path(".env"))
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("openrouter_api_key")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    return api_key


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _compact_text(text: str, limit: int = 1200) -> str:
    compacted = re.sub(r"\s+", " ", text).strip()
    return compacted[:limit]


def _infer_address(pdf_path: Path, pages: list[dict[str, Any]]) -> str:
    joined = " ".join(str(page.get("text_excerpt", "")) for page in pages)
    match = re.search(r"(Малая\s+Филевская\s+22|Муравская\s+38Б[^,\n]*)", joined, re.IGNORECASE)
    return match.group(1) if match else pdf_path.stem


if __name__ == "__main__":
    main()
