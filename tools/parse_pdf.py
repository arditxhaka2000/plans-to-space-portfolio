"""Create a page-faithful, searchable evidence index for a flattened drawing PDF."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "Flamingo-Tower-Takeoff.pdf"
OUT = ROOT / "document"
PAGES = OUT / "pages"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def classify(text: str, number: int) -> str:
    upper = text.upper()
    if number == 1 or "COVER SHEET" in upper:
        return "cover"
    if "DOOR SCHEDULE" in upper or "WINDOW SCHEDULE" in upper:
        return "schedule"
    if "BUILDING SECTION" in upper:
        return "section"
    if "BUILDING ELEVATION" in upper:
        return "elevation"
    if "REFLECTED CEILING" in upper or "RCP" in upper:
        return "reflected-ceiling-plan"
    if "FLOOR PLAN" in upper or "ROOF PLAN" in upper:
        return "plan"
    return "architectural-sheet"


def drawing_codes(text: str) -> list[str]:
    codes = re.findall(r"\bA\d{1,2}[.]\d{1,2}\b", text.upper())
    return sorted(set(codes))


def measurements(text: str) -> list[dict]:
    found: list[dict] = []
    patterns = [
        ("area", r"(?<!\d)(\d[\d,.]*)\s*(?:SQ\s*FT|SF)\b"),
        ("length", r"(?<!\d)(\d[\d,.]*)\s*(?:FT|LF)\b"),
        ("imperial-dimension", r"\b\d{1,3}\s*['’]-?\s*\d{1,2}(?:\s+\d/\d)?\s*[\"”]?"),
    ]
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            found.append({"kind": kind, "raw": match.group(0), "offset": match.start()})
    return found


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source PDF: {SOURCE}")
    OUT.mkdir(exist_ok=True)
    PAGES.mkdir(exist_ok=True)
    reader = PdfReader(SOURCE)
    prefix = PAGES / "sheet"
    if len(list(PAGES.glob("sheet-*.jpg"))) != len(reader.pages):
        subprocess.run(["pdftoppm", "-jpeg", "-jpegopt", "quality=88", "-r", "130", str(SOURCE), str(prefix)], check=True)

    ocr = RapidOCR() if RapidOCR else None
    page_entries = []
    for index, page in enumerate(reader.pages, start=1):
        image_path = PAGES / f"sheet-{index:02d}.jpg"
        embedded_text = page.extract_text() or ""
        ocr_lines = []
        if ocr:
            result, _ = ocr(str(image_path))
            for row in result or []:
                box, text, confidence = row
                clean = " ".join(str(text).split())
                if clean:
                    ocr_lines.append({"text": clean, "confidence": round(float(confidence), 4), "box": [[round(float(x), 1), round(float(y), 1)] for x, y in box]})
        searchable = "\n".join(x["text"] for x in ocr_lines) if ocr_lines else embedded_text
        image = Image.open(image_path)
        page_entries.append({
            "page": index,
            "label": f"Sheet {index:02d}",
            "classification": classify(searchable, index),
            "drawingCodes": drawing_codes(searchable),
            "widthPoints": float(page.mediabox.width),
            "heightPoints": float(page.mediabox.height),
            "rotation": int(page.rotation or 0),
            "pixelWidth": image.width,
            "pixelHeight": image.height,
            "preview": f"/document/pages/{image_path.name}",
            "imageSha256": sha256(image_path),
            "embeddedText": embedded_text,
            "ocrText": searchable,
            "ocrLines": ocr_lines,
            "ocrAverageConfidence": round(sum(x["confidence"] for x in ocr_lines) / len(ocr_lines), 4) if ocr_lines else None,
            "measurements": measurements(searchable),
            "annotationCount": len(page.get("/Annots", []).get_object()) if page.get("/Annots") else 0,
            "imageObjectCount": len(list(page.images)),
        })
        print(f"Indexed page {index:02d}/{len(reader.pages)}: {len(ocr_lines)} OCR lines", flush=True)

    fields = reader.get_fields() or {}
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "fileName": SOURCE.name,
            "sha256": sha256(SOURCE),
            "sizeBytes": SOURCE.stat().st_size,
            "pageCount": len(reader.pages),
            "metadata": {str(k).lstrip("/"): str(v) for k, v in (reader.metadata or {}).items()},
            "formFieldNames": sorted(fields.keys()),
            "hasEmbeddedText": any(x["embeddedText"] for x in page_entries),
            "preservation": "Original PDF retained unchanged; every page rendered and hashed; OCR is an aid, not a replacement for the page image.",
        },
        "pages": page_entries,
    }
    (OUT / "document-index.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT / 'document-index.json'}", flush=True)


if __name__ == "__main__":
    main()
