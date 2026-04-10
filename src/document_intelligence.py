"""
Document intelligence layer.

Reads messy source documents that Andres's property managers would actually
send each quarter — operating statement PDFs, rent roll Excel files,
ARGUS-style CSV exports — and extracts structured asset-level performance
data using the Claude API.

Falls back to pre-extracted fixtures if the API is unreachable, so the
demo always runs end-to-end even without an API key.
"""
import json
import os
from pathlib import Path
from typing import List
import pandas as pd
import fitz  # pymupdf
from anthropic import Anthropic

from .schemas import AssetPerformance


# Fallback extractions keyed by filename stem. Used when the API is not
# reachable (no key, offline demo, etc.). Every mock source document has
# a matching fallback so the demo is deterministic.
FALLBACK_EXTRACTIONS: dict[str, List[dict]] = {
    "q1_operating_statement": [
        {
            "asset_name": "Eastern Park",
            "state": "CT",
            "sf": 180_000,
            "occupancy_pct": 95.0,
            "in_place_noi": 1_620_000,
            "yoy_noi_change_pct": 8.5,
            "valuation_mark": 21_000_000,
        },
        {
            "asset_name": "Mountainside",
            "state": "NJ",
            "sf": 95_000,
            "occupancy_pct": 98.0,
            "in_place_noi": 935_000,
            "yoy_noi_change_pct": 6.2,
            "valuation_mark": 14_500_000,
        },
        {
            "asset_name": "South Windsor",
            "state": "CT",
            "sf": 145_000,
            "occupancy_pct": 97.0,
            "in_place_noi": 1_180_000,
            "yoy_noi_change_pct": 11.3,
            "valuation_mark": 16_200_000,
        },
        {
            "asset_name": "Danbury",
            "state": "CT",
            "sf": 125_000,
            "occupancy_pct": 92.0,
            "in_place_noi": 870_000,
            "yoy_noi_change_pct": 5.8,
            "valuation_mark": 11_800_000,
        },
        {
            "asset_name": "Little Ferry",
            "state": "NJ",
            "sf": 68_000,
            "occupancy_pct": 100.0,
            "in_place_noi": 720_000,
            "yoy_noi_change_pct": 9.4,
            "valuation_mark": 10_500_000,
        },
    ],
    "q1_rent_roll": [
        {
            "asset_name": "Bridgeport",
            "state": "CT",
            "sf": 210_000,
            "occupancy_pct": 88.0,
            "in_place_noi": 1_380_000,
            "yoy_noi_change_pct": 4.2,
            "valuation_mark": 17_500_000,
        },
        {
            "asset_name": "Stratford",
            "state": "CT",
            "sf": 155_000,
            "occupancy_pct": 94.0,
            "in_place_noi": 1_050_000,
            "yoy_noi_change_pct": 7.1,
            "valuation_mark": 13_200_000,
        },
        {
            "asset_name": "Waterbury",
            "state": "CT",
            "sf": 135_000,
            "occupancy_pct": 100.0,
            "in_place_noi": 985_000,
            "yoy_noi_change_pct": 12.6,
            "valuation_mark": 12_100_000,
        },
        {
            "asset_name": "Windsor Locks",
            "state": "CT",
            "sf": 175_000,
            "occupancy_pct": 90.0,
            "in_place_noi": 1_220_000,
            "yoy_noi_change_pct": 6.8,
            "valuation_mark": 14_700_000,
        },
        {
            "asset_name": "East Hartford",
            "state": "CT",
            "sf": 115_000,
            "occupancy_pct": 95.0,
            "in_place_noi": 810_000,
            "yoy_noi_change_pct": 9.2,
            "valuation_mark": 10_300_000,
        },
    ],
    "q1_argus_export": [
        {
            "asset_name": "Elizabeth",
            "state": "NJ",
            "sf": 85_000,
            "occupancy_pct": 100.0,
            "in_place_noi": 925_000,
            "yoy_noi_change_pct": 8.1,
            "valuation_mark": 12_800_000,
        },
        {
            "asset_name": "Kearny",
            "state": "NJ",
            "sf": 72_000,
            "occupancy_pct": 96.0,
            "in_place_noi": 780_000,
            "yoy_noi_change_pct": 7.5,
            "valuation_mark": 10_900_000,
        },
        {
            "asset_name": "Meriden",
            "state": "CT",
            "sf": 160_000,
            "occupancy_pct": 82.0,
            "in_place_noi": 1_020_000,
            "yoy_noi_change_pct": 3.4,
            "valuation_mark": 13_500_000,
        },
        {
            "asset_name": "New Britain",
            "state": "CT",
            "sf": 80_000,
            "occupancy_pct": 100.0,
            "in_place_noi": 615_000,
            "yoy_noi_change_pct": 10.8,
            "valuation_mark": 8_400_000,
        },
    ],
}


def _read_file_as_text(path: Path) -> str:
    """Pull raw text out of whatever format Andres's PMs send us."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        doc = fitz.open(str(path))
        return "\n".join(page.get_text() for page in doc)

    if suffix in (".xlsx", ".xls"):
        xl = pd.ExcelFile(path)
        chunks = []
        for sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet)
            chunks.append(f"=== Sheet: {sheet} ===\n{df.to_string(index=False)}")
        return "\n\n".join(chunks)

    if suffix == ".csv":
        df = pd.read_csv(path)
        return df.to_string(index=False)

    if suffix in (".txt", ".md"):
        return path.read_text()

    raise ValueError(f"Unsupported source document type: {suffix}")


_EXTRACTION_PROMPT = """You are extracting asset-level performance data from a property management document for a value-add industrial real estate operator.

Return ONLY a JSON array. Each element must have exactly these fields:
- asset_name (string)
- state (two-letter US state code)
- sf (integer, square feet)
- occupancy_pct (float, 0-100)
- in_place_noi (float, annualized USD)
- yoy_noi_change_pct (float, e.g. 8.5 for +8.5%)
- valuation_mark (float, USD)

If a field is not present in the document, make your best estimate based on context but do NOT invent assets that are not mentioned.

Document content:
---
{content}
---

Return only the JSON array, no prose, no markdown fences."""


def extract_assets_from_document(path: Path) -> List[AssetPerformance]:
    """
    Main entry point. Reads a source document, calls Claude to extract
    structured asset data, and returns validated AssetPerformance objects.

    Falls back to a pre-extracted fixture matching the filename if the
    API call fails — ensures the demo always completes.
    """
    raw_text = _read_file_as_text(path)

    # Try the API first
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            client = Anthropic()
            msg = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                temperature=0.0,
                messages=[{
                    "role": "user",
                    "content": _EXTRACTION_PROMPT.format(content=raw_text[:8000]),
                }],
            )
            text = "".join(
                b.text for b in msg.content if hasattr(b, "text")
            ).strip()
            # Strip any markdown fences
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())
            return [AssetPerformance(**row) for row in data]
    except Exception as e:
        print(f"[document_intelligence] API extraction failed, using fallback: {e}")

    # Fallback — use pre-built fixtures keyed by filename stem
    stem = path.stem.lower().replace("-", "_")
    for key, rows in FALLBACK_EXTRACTIONS.items():
        if key in stem or stem in key:
            return [AssetPerformance(**row) for row in rows]

    # Final fallback: empty
    return []


def extract_from_multiple(paths: List[Path]) -> List[AssetPerformance]:
    """Process a batch of source documents and merge results, deduped by asset name."""
    seen = {}
    for p in paths:
        for asset in extract_assets_from_document(p):
            seen[asset.asset_name] = asset
    return list(seen.values())
