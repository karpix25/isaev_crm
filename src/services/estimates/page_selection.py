from pathlib import Path
from typing import Any

import fitz


EXTRACTOR_MARKERS: dict[str, tuple[str, ...]] = {
    "partitions": ("перегород", "демонтаж"),
    "electrical": ("розет", "освещ", "выключ"),
    "plumbing": ("сантех", "водоснаб", "гидроизоля"),
    "floors": ("помещения", "напольн", "стяжка", "теплые полы", "тёплые полы"),
    "walls_tile": ("отделка стен", "развертк", "развёртк", "гидроизоля"),
}


def render_pages_for_extractors(pdf_path: Path, out_dir: Path) -> dict[str, list[dict[str, Any]]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    pages_by_extractor = {name: [] for name in EXTRACTOR_MARKERS}

    for index, page in enumerate(doc):
        text = page.get_text("text") or ""
        lowered = text.lower()
        matches = [
            name
            for name, markers in EXTRACTOR_MARKERS.items()
            if any(marker in lowered for marker in markers)
        ]
        if not matches:
            continue

        image_path = out_dir / f"page_{index + 1:02d}.jpg"
        if not image_path.exists():
            page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False).save(str(image_path), jpg_quality=84)
        page_data = {"page": index + 1, "image_path": image_path, "text_excerpt": _compact_text(text)}
        for name in matches:
            pages_by_extractor[name].append(page_data)

    return {name: pages[:8] for name, pages in pages_by_extractor.items() if pages}


def _compact_text(text: str, limit: int = 1400) -> str:
    return " ".join(text.split())[:limit]
