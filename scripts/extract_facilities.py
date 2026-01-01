"""Extract shelter facility data from the provided PDF.

This script intentionally avoids third-party dependencies so it can run in
restricted environments. It reads the bundled PDF, decodes the embedded font
maps, and writes a normalized JSON file to ``data/facilities.json``.
"""

from __future__ import annotations

import json
import re
import unicodedata
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "新市區-1130702.pdf"
OUTPUT_PATH = ROOT / "data" / "facilities.json"


@dataclass
class Facility:
    """Structured representation of a single shelter facility."""

    id: int
    slug: str
    name: str
    village: str
    site_name: str
    address: str
    capacity: int
    precinct: str


def _parse_cmap(pdf_bytes: bytes) -> Dict[int, str]:
    """Extract the character map (CID -> Unicode) from the PDF bytes."""

    cmap: Dict[int, str] = {}
    for match in re.finditer(rb"beginbfchar(.*?)endbfchar", pdf_bytes, re.S):
        block = match.group(1)
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s+<([0-9A-Fa-f]+)>", block):
            code_point = int(src, 16)
            text = bytes.fromhex(dst.decode()).decode("utf-16-be")
            cmap[code_point] = text
    return cmap


def _decode_text_streams(pdf_bytes: bytes, cmap: Dict[int, str]) -> List[str]:
    """Decode all text drawing arrays inside Flate encoded streams."""

    lines: List[str] = []
    for match in re.finditer(rb"stream\r?\n", pdf_bytes):
        start = match.end()
        end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            break

        data = pdf_bytes[start:end]
        if data.startswith(b"\r\n"):
            data = data[2:]
        elif data.startswith(b"\n"):
            data = data[1:]

        try:
            decompressed = zlib.decompress(data)
        except Exception:
            continue

        for array in re.findall(rb"\[(.*?)\]\s*TJ", decompressed, re.S):
            glyphs = re.findall(rb"<([0-9A-Fa-f]+)>", array)
            if not glyphs:
                continue
            lines.append("".join(cmap.get(int(code, 16), "?") for code in glyphs))
    return lines


def _slugify(value: str) -> str:
    """Create a filesystem-friendly slug while retaining intent."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(ch for ch in normalized if ch.isalnum())
    return ascii_only.lower() or "facility"


def _parse_entries(lines: Iterable[str]) -> List[Facility]:
    """Turn PDF text lines into structured facility records."""

    ignore = {
        "區別里別名稱地址",
        "容量(可容",
        "納人數)",
        "轄管分局",
        "臺南市新市區防空疏散避難設施一覽表",
        "113/07/02更新",
        "第1頁 共2頁",
        "第2頁 共2頁",
    }

    facilities: List[Facility] = []
    pending: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line in ignore:
            continue

        capacity_match = re.match(r"^(\d+)(.*分局)$", line)
        if capacity_match and pending:
            name_parts: List[str] = []
            address_parts: List[str] = []
            collecting_address = False

            for part in pending:
                if part.startswith("臺南市"):
                    collecting_address = True
                (address_parts if collecting_address else name_parts).append(part)

            full_name = "".join(name_parts)
            address = "".join(address_parts)

            # Derive village and site name from the combined name.
            village = ""
            site_name = full_name
            if full_name.startswith("新市區") and "里" in full_name:
                remainder = full_name[len("新市區") :]
                before, after = remainder.split("里", 1)
                village = f"{before}里"
                site_name = after

            facility_id = len(facilities) + 1
            slug = f"{facility_id:03d}-{_slugify(site_name)}"

            facilities.append(
                Facility(
                    id=facility_id,
                    slug=slug,
                    name=full_name,
                    village=village or "",
                    site_name=site_name,
                    address=address,
                    capacity=int(capacity_match.group(1)),
                    precinct=capacity_match.group(2),
                )
            )
            pending = []
        else:
            pending.append(line)

    return facilities


def extract() -> List[Facility]:
    """Parse the PDF and return all facilities."""

    pdf_bytes = PDF_PATH.read_bytes()
    cmap = _parse_cmap(pdf_bytes)
    raw_lines = _decode_text_streams(pdf_bytes, cmap)
    return _parse_entries(raw_lines)


def main() -> None:
    facilities = extract()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps([asdict(facility) for facility in facilities], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(facilities)} facilities to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
