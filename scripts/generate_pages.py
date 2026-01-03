from __future__ import annotations

import json
import re
import unicodedata
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Tuple


@dataclass
class Facility:
    name: str
    address: str
    locality: str
    capacity: int
    precinct: str
    page: int
    slug: str


def load_pdf_bytes(pdf_path: Path) -> bytes:
    return pdf_path.read_bytes()


def extract_to_unicode_map(data: bytes) -> dict[int, str]:
    mapping_ref = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", data)
    if not mapping_ref:
        raise ValueError("Unable to find ToUnicode mapping in PDF")
    obj_num = int(mapping_ref.group(1))
    obj_pattern = rf"{obj_num} 0 obj".encode()
    obj_start = data.find(obj_pattern)
    if obj_start == -1:
        raise ValueError("Unable to find ToUnicode object body")
    stream_start = data.find(b"stream", obj_start)
    stream_end = data.find(b"endstream", stream_start)
    raw_stream = data[stream_start + len(b"stream") : stream_end]
    text = raw_stream.decode("latin1")
    mapping: dict[int, str] = {}
    for src, dst in re.findall(r"<([0-9A-F]{4})> <([0-9A-F]{4})>", text):
        mapping[int(src, 16)] = chr(int(dst, 16))
    return mapping


def decode_hex_string(hex_string: str, cmap: dict[int, str]) -> str:
    characters: list[str] = []
    for idx in range(0, len(hex_string), 4):
        code = int(hex_string[idx : idx + 4], 16)
        characters.append(cmap.get(code, "?"))
    return "".join(characters)


def decode_text_operand(raw: bytes, cmap: dict[int, str]) -> str:
    raw = raw.strip()
    if raw.startswith(b"["):
        parts = re.findall(rb"<([0-9A-F]+)>|\(([^)]*)\)", raw)
        decoded = []
        for hex_part, str_part in parts:
            if hex_part:
                decoded.append(decode_hex_string(hex_part.decode(), cmap))
            elif str_part:
                decoded.append(str_part.decode("latin1"))
        return "".join(decoded)
    if raw.startswith(b"<"):
        return decode_hex_string(raw.strip(b"<>").decode(), cmap)
    if raw.startswith(b"("):
        return raw.strip(b"()").decode("latin1")
    return ""


def iter_text_entries(stream: bytes, cmap: dict[int, str]) -> Iterable[Tuple[float, str]]:
    token_pattern = re.compile(
        rb"(?P<tm>(?:-?\d+\.?\d*\s+){5}-?\d+\.?\d*\s+Tm)|(?P<text>(\[.*?\]|<[^>]+>|\([^)]*\))\s*(?:TJ|Tj))",
        re.S,
    )
    current_y: float | None = None
    for match in token_pattern.finditer(stream):
        if match.group("tm"):
            numbers = [float(n) for n in re.findall(rb"-?\d+\.?\d*", match.group("tm"))]
            current_y = numbers[-1]
        else:
            if current_y is None:
                continue
            yield current_y, decode_text_operand(match.group("text"), cmap)


def extract_facilities(data: bytes) -> List[Facility]:
    cmap = extract_to_unicode_map(data)
    flate_streams: List[bytes] = []
    for stream_match in re.finditer(rb"stream\r?\n", data):
        start = stream_match.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        header_start = data.rfind(b"<<", 0, stream_match.start())
        header = data[header_start : stream_match.start()]
        if b"/FlateDecode" not in header:
            continue
        try:
            flate_streams.append(zlib.decompress(data[start:end]))
        except Exception:
            continue

    facilities: List[Facility] = []
    for page_index, stream in enumerate(flate_streams[1:], start=1):
        entries = sorted(iter_text_entries(stream, cmap), key=lambda item: -item[0])
        for idx, (_, text) in enumerate(entries):
            if "善化分局" not in text or idx < 2 or idx + 1 >= len(entries):
                continue
            name = entries[idx - 1][1]
            address = entries[idx - 2][1]
            locality = entries[idx + 1][1]
            capacity_value = text.replace("善化分局", "")
            slug = f"facility-{len(facilities) + 1:02d}"
            facilities.append(
                Facility(
                    name=name,
                    address=address,
                    locality=locality,
                    capacity=int(capacity_value),
                    precinct="善化分局",
                    page=page_index,
                    slug=slug,
                )
            )
    return facilities


def write_json(data: List[Facility], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([asdict(item) for item in data], ensure_ascii=False, indent=2), encoding="utf-8")


def slug_title(text: str) -> str:
    cleaned = "".join(ch for ch in unicodedata.normalize("NFKD", text) if ord(ch) < 128 and ch.isalnum())
    return cleaned or "facility"


def build_pages(facilities: List[Facility], docs_root: Path) -> None:
    assets = docs_root / "assets"
    facilities_root = docs_root / "facilities"
    assets.mkdir(parents=True, exist_ok=True)
    facilities_root.mkdir(parents=True, exist_ok=True)
    (assets / "style.css").write_text(
        """
:root {
  font-family: "Noto Sans TC", "Noto Sans", Arial, sans-serif;
  color: #0f172a;
  background-color: #f8fafc;
}
body {
  margin: 0;
  padding: 0;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 40%);
}
.page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem 1.25rem 3rem;
}
.card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
  padding: 1.5rem;
  margin-bottom: 1rem;
}
.grid {
  display: grid;
  gap: 1rem;
}
.grid-2 {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}
.muted { color: #475569; }
.title {
  margin: 0 0 0.25rem 0;
  font-size: 1.5rem;
}
.subtitle { margin: 0; color: #2563eb; font-weight: 700; }
.pill {
  display: inline-block;
  background: #e0f2fe;
  color: #0369a1;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.9rem;
}
.meta-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.meta-list li {
  margin-bottom: 0.35rem;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 0.75rem;
  text-align: left;
}
th {
  background: #eff6ff;
  color: #1e3a8a;
}
tr:nth-child(even) td {
  background: #f8fafc;
}
a { color: #1d4ed8; text-decoration: none; }
a:hover { text-decoration: underline; }
.breadcrumbs {
  font-size: 0.95rem;
  margin-bottom: 1rem;
}
footer {
  margin-top: 2rem;
  color: #475569;
  font-size: 0.9rem;
}
""",
        encoding="utf-8",
    )

    index_rows = []
    for facility in facilities:
        index_rows.append(
            f"<tr>"
            f"<td><a href=\"./facilities/{facility.slug}/\">{facility.name}</a></td>"
            f"<td>{facility.address}</td>"
            f"<td>{facility.locality}</td>"
            f"<td class=\"muted\">{facility.capacity}</td>"
            f"<td>{facility.precinct}</td>"
            f"</tr>"
        )

    index_html = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>新市區防空避難設施一覽</title>
  <link rel="stylesheet" href="./assets/style.css">
</head>
<body>
  <div class="page">
    <header>
      <p class="subtitle">臺南市新市區</p>
      <h1 class="title">防空避難設施獨立網站索引</h1>
      <p class="muted">資料來源：<code>新市區-1130702.pdf</code>，自動化解析並產生。</p>
      <div class="pill">設施總數：{len(facilities)}</div>
    </header>
    <div class="card">
      <table>
        <thead>
          <tr><th>名稱</th><th>地址</th><th>里別/鄰</th><th>可容納人數</th><th>轄管分局</th></tr>
        </thead>
        <tbody>
          {"".join(index_rows)}
        </tbody>
      </table>
    </div>
    <footer>點擊名稱即可進入各設施的專屬頁面。</footer>
  </div>
</body>
</html>
"""
    docs_root.joinpath("index.html").write_text(index_html, encoding="utf-8")

    for facility in facilities:
        page_html = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{facility.name}｜防空避難設施</title>
  <link rel="stylesheet" href="../../assets/style.css">
</head>
<body>
  <div class="page">
    <nav class="breadcrumbs"><a href="../../">← 返回索引</a></nav>
    <section class="card">
      <p class="subtitle">轄管分局：{facility.precinct}</p>
      <h1 class="title">{facility.name}</h1>
      <div class="pill">可容納人數：{facility.capacity:,}</div>
    </section>
    <section class="card grid grid-2">
      <div>
        <h2>位置資訊</h2>
        <ul class="meta-list">
          <li><strong>地址：</strong>{facility.address}</li>
          <li><strong>里別／鄰：</strong>{facility.locality}</li>
          <li><strong>PDF 頁碼：</strong>第 {facility.page} 頁</li>
        </ul>
      </div>
      <div>
        <h2>快速查看</h2>
        <p class="muted">點擊下方連結，可快速在 Google Maps 搜尋該地址。</p>
        <p><a href="https://www.google.com/maps/search/{facility.address}" target="_blank" rel="noopener noreferrer">在地圖上開啟</a></p>
      </div>
    </section>
    <footer>資料由 PDF 自動解析產出。如需更新，請重新執行產生腳本。</footer>
  </div>
</body>
</html>
"""
        facility_dir = facilities_root / facility.slug
        facility_dir.mkdir(parents=True, exist_ok=True)
        facility_dir.joinpath("index.html").write_text(page_html, encoding="utf-8")


def generate(pdf_path: Path, docs_root: Path) -> List[Facility]:
    data = load_pdf_bytes(pdf_path)
    facilities = extract_facilities(data)
    write_json(facilities, docs_root / "data" / "facilities.json")
    build_pages(facilities, docs_root)
    return facilities


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[1]
    pdf_path = base_dir / "新市區-1130702.pdf"
    docs_root = base_dir / "docs"
    facilities = generate(pdf_path, docs_root)
    print(f"Generated {len(facilities)} facility pages in {docs_root}")
