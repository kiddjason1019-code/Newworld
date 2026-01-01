from __future__ import annotations

import json
import re
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "新市區-1130702.pdf"


def _load_cmap_mapping(raw_pdf: bytes) -> Dict[int, str]:
    cmap_match = re.search(br"begincmap(.*?)endcmap", raw_pdf, re.S)
    if not cmap_match:
        raise ValueError("Unable to locate cmap definition in PDF.")

    cmap_text = cmap_match.group(0).decode("latin1")
    mapping: Dict[int, str] = {}
    for match in re.finditer(r"<([0-9A-F]{4})> <([0-9A-F]{4})>", cmap_text):
        code_point = int(match.group(1), 16)
        unicode_value = int(match.group(2), 16)
        mapping[code_point] = chr(unicode_value)

    if not mapping:
        raise ValueError("Parsed cmap is empty.")

    return mapping


def _decompress_streams(raw_pdf: bytes) -> Iterable[str]:
    for match in re.finditer(rb"stream\r?\n", raw_pdf):
        start = match.end()
        end = raw_pdf.find(b"endstream", start)
        if end == -1:
            continue

        stream = raw_pdf[start:end].strip(b"\r\n")
        try:
            decompressed = zlib.decompress(stream)
        except zlib.error:
            continue

        yield decompressed.decode("latin1")


def _decode_streams(streams: Sequence[str], cmap: Dict[int, str]) -> str:
    decoded_parts: List[str] = []
    for stream in streams:
        hex_codes = re.findall(r"<([0-9A-F]{4})>", stream)
        decoded_parts.append("".join(cmap.get(int(code, 16), "?") for code in hex_codes))
    return "".join(decoded_parts)


def _cleanup_text(raw_text: str) -> str:
    cleaned = raw_text.replace(
        "臺南市新市區防空疏散避難設施一覽表113/07/02更新第1頁 共2頁", ""
    )
    cleaned = cleaned.replace("第2頁 共2頁", "")
    cleaned = cleaned.replace("區別里別名稱地址容量(可容納人數)轄管分局", "")
    return cleaned.strip()


def _split_entries(clean_text: str) -> List[str]:
    chunks = clean_text.split("善化分局新市區")
    entries: List[str] = []
    for index, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk:
            continue

        if index < len(chunks) - 1:
            chunk = f"{chunk}善化分局"

        if not chunk.startswith("新市區"):
            chunk = f"新市區{chunk}"

        entries.append(chunk)

    return entries


def _parse_entry(entry: str) -> Dict[str, str | int]:
    capacity_match = re.search(r"(\d+)(善化分局)?$", entry)
    if not capacity_match:
        raise ValueError(f"Unable to parse capacity for entry: {entry}")

    capacity = int(capacity_match.group(1))
    prefix = entry[: capacity_match.start()]

    if not prefix.startswith("新市區"):
        raise ValueError(f"Entry missing district prefix: {entry}")

    remainder = prefix.removeprefix("新市區")
    village_match = re.match(r"([^里]+里)(.*)", remainder)
    if not village_match:
        raise ValueError(f"Unable to parse village/name/address from: {entry}")

    village = village_match.group(1)
    details = village_match.group(2)
    address_index = details.find("臺南市")

    if address_index == -1:
        name = details
        address = ""
    else:
        name = details[:address_index]
        address = details[address_index:]

    return {
        "district": "新市區",
        "village": village,
        "name": name,
        "address": address,
        "capacity": capacity,
        "branch": "善化分局",
    }


def extract_shelters(pdf_path: Path = PDF_PATH) -> List[Dict[str, str | int]]:
    raw_pdf = pdf_path.read_bytes()
    cmap = _load_cmap_mapping(raw_pdf)
    streams = list(_decompress_streams(raw_pdf))
    decoded_text = _decode_streams(streams, cmap)
    clean_text = _cleanup_text(decoded_text)
    entries = _split_entries(clean_text)
    return [_parse_entry(entry) for entry in entries]


def write_json(
    output_path: Path = ROOT / "data" / "shelters.json",
    shelters: List[Dict[str, str | int]] | None = None,
) -> None:
    shelters = shelters if shelters is not None else extract_shelters()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(shelters, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    write_json()
    print("Shelter data extracted to data/shelters.json")
