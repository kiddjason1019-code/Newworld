from __future__ import annotations

import json
import re
import zlib
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "新市區-1130702.pdf"
OUTPUT_PATH = ROOT / "data" / "shelters.json"

SKIP_TOKENS = {
    "區別里別名稱地址",
    "容量(可容",
    "納人數)",
    "轄管分局",
    "臺南市新市區防空疏散避難設施一覽表",
    "113/07/02更新",
    "第1頁 共2頁",
    "第2頁 共2頁",
}


def build_cmap(pdf_bytes: bytes) -> Mapping[str, str]:
    """Extract the CMap that maps glyph hex codes to Unicode codepoints."""

    cmap_start = pdf_bytes.find(b"begincmap")
    if cmap_start == -1:
        raise ValueError("No CMap found in the PDF")

    cmap_end = pdf_bytes.find(b"endcmap", cmap_start)
    cmap_bytes = pdf_bytes[cmap_start : cmap_end + len("endcmap")]
    cmap_text = cmap_bytes.decode("latin1")
    pairs = re.findall(r"<([0-9A-F]{4})>\s+<([0-9A-F]{4})>", cmap_text)
    return {code: target for code, target in pairs}


def iter_text_tokens(pdf_bytes: bytes) -> Iterable[str]:
    """Yield decoded text tokens from the PDF content streams."""

    cmap = build_cmap(pdf_bytes)

    def decode_hex_string(hex_string: str) -> str:
        chars: List[str] = []
        for i in range(0, len(hex_string), 4):
            glyph = hex_string[i : i + 4]
            target = cmap.get(glyph, "003F")
            chars.append(chr(int(target, 16)))
        return "".join(chars)

    streams = re.findall(b"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, flags=re.S)
    for raw_stream in streams:
        try:
            stream_text = zlib.decompress(raw_stream).decode("latin1")
        except Exception:
            continue

        for match in re.finditer(r"(\[[^\]]*\] TJ|<[^>]+> Tj)", stream_text):
            hex_strings = re.findall(r"<([0-9A-F]+)>", match.group(1))
            yield "".join(decode_hex_string(hx) for hx in hex_strings)


def clean_tokens(tokens: Sequence[str]) -> List[str]:
    cleaned: List[str] = []
    for token in tokens:
        if token in SKIP_TOKENS:
            continue
        cleaned.append(token.replace("\n", ""))
    return cleaned


def tokens_to_rows(tokens: Sequence[str]) -> List[dict]:
    rows: List[dict] = []
    name_parts: List[str] = []
    address_parts: List[str] = []
    reading_address = False

    for token in tokens:
        if re.match(r"^\d+", token):
            match = re.match(r"^(\d+)(.+)$", token)
            capacity = int(match.group(1)) if match else None
            precinct = match.group(2) if match else token
            name = "".join(name_parts).strip()
            address = "".join(address_parts).strip()
            rows.append(
                {
                    "name": name,
                    "address": address,
                    "capacity": capacity,
                    "precinct": precinct,
                }
            )
            name_parts.clear()
            address_parts.clear()
            reading_address = False
        elif token.startswith("臺南市"):
            reading_address = True
            address_parts.append(token)
        else:
            if reading_address:
                address_parts.append(token)
            else:
                name_parts.append(token)

    return rows


def extract_shelters() -> List[dict]:
    pdf_bytes = PDF_PATH.read_bytes()
    raw_tokens = list(iter_text_tokens(pdf_bytes))
    tokens = clean_tokens(raw_tokens)
    return tokens_to_rows(tokens)


def main() -> None:
    shelters = extract_shelters()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(shelters, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Extracted {len(shelters)} shelters to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
