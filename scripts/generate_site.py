from __future__ import annotations

import json
import re
import unicodedata
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = REPO_ROOT / "新市區-1130702.pdf"
DOCS_DIR = REPO_ROOT / "docs"
DATA_DIR = DOCS_DIR / "data"
FACILITY_DIR = DOCS_DIR / "facility"


@dataclass
class Facility:
    district: str
    village: str
    name: str
    address: str
    capacity: int | None
    division: str
    slug: str


def extract_streams(pdf_bytes: bytes) -> List[bytes]:
    """Return all streams (decompressed when possible) from the PDF."""
    streams: List[bytes] = []
    for match in re.finditer(rb"stream\r?\n", pdf_bytes):
        start = match.end()
        end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            continue
        raw = pdf_bytes[start:end].strip(b"\r\n")
        try:
            streams.append(zlib.decompress(raw))
        except Exception:
            streams.append(raw)
    return streams


def build_cmap(streams: Iterable[bytes]) -> dict[int, int]:
    """Parse the ToUnicode CMap from the font definition."""
    for stream in streams:
        if b"beginbfchar" not in stream:
            continue
        pairs = re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", stream)
        if pairs:
            return {int(src, 16): int(dst, 16) for src, dst in pairs}
    return {}


def decode_sections(stream: bytes, cmap: dict[int, int]) -> List[str]:
    """Decode text segments from a content stream using the cmap."""
    content = stream.decode("latin1", errors="ignore")
    sections: List[str] = []
    for raw_hexes in re.findall(r"\[<([^]]+)>[^\]]*\]", content):
        codes = re.findall(r"([0-9A-Fa-f]{4})", raw_hexes)
        decoded = "".join(chr(cmap[int(code, 16)]) for code in codes if int(code, 16) in cmap)
        if decoded:
            sections.append(decoded)
    return sections


def clean_sections(sections: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    for item in sections:
        compact = "".join(ch for ch in item if ch != "\uffff")
        compact = compact.strip()
        if compact:
            cleaned.append(compact)
    return cleaned


def remove_headers_and_footers(sections: List[str]) -> Tuple[List[str], str | None]:
    filtered: List[str] = []
    update_date: str | None = None
    for item in sections:
        if any(key in item for key in ("區別里別名稱地址", "容量(可容納人數)", "轄管分局", "防空疏散避難設施一覽表", "第1頁", "第2頁")):
            continue
        if "更新" in item:
            date_match = re.search(r"\d{3}/\d{2}/\d{2}", item)
            if date_match:
                update_date = date_match.group(0)
            continue
        filtered.append(item)
    return filtered, update_date


def assemble_rows(sections: List[str]) -> List[dict]:
    rows: List[dict] = []
    current: dict | None = None
    for item in sections:
        if item.startswith("新市區"):
            if current:
                rows.append(current)
            current = {"name_parts": [item], "address_parts": [], "capacity_division": None}
            continue
        if current is None:
            continue
        if item.startswith("臺南市新市區"):
            current["address_parts"].append(item)
        elif re.match(r"\d", item):
            current["capacity_division"] = item
        else:
            if current["address_parts"] and not current["capacity_division"]:
                current["address_parts"].append(item)
            else:
                current["name_parts"].append(item)
    if current:
        rows.append(current)
    return rows


def slugify(text: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or fallback


def finalize_facilities(rows: List[dict]) -> List[Facility]:
    facilities: List[Facility] = []
    for idx, row in enumerate(rows, start=1):
        name_blob = "".join(row["name_parts"])
        district = "新市區"
        remainder = name_blob[len(district) :]
        village = remainder[: remainder.find("里") + 1] if "里" in remainder else ""
        facility_name = remainder[len(village) :]
        address = "".join(row["address_parts"])
        cap_div = row.get("capacity_division") or ""
        match = re.match(r"(\d+)(.*)", cap_div)
        capacity = int(match.group(1)) if match else None
        division = match.group(2) if match else ""
        slug = slugify(f"{village}-{facility_name}", f"facility-{idx:02d}")
        facilities.append(
            Facility(
                district=district,
                village=village,
                name=facility_name,
                address=address,
                capacity=capacity,
                division=division,
                slug=slug,
            )
        )
    return facilities


def extract_facilities() -> Tuple[List[Facility], str | None]:
    pdf_bytes = PDF_PATH.read_bytes()
    streams = extract_streams(pdf_bytes)
    cmap = build_cmap(streams)
    if not cmap:
        raise RuntimeError("Unable to locate ToUnicode cmap in the PDF.")

    sections: List[str] = []
    for stream in streams:
        if b"TJ" in stream and b"Tf" in stream:
            sections.extend(decode_sections(stream, cmap))

    cleaned = clean_sections(sections)
    filtered, update_date = remove_headers_and_footers(cleaned)
    rows = assemble_rows(filtered)
    facilities = finalize_facilities(rows)
    return facilities, update_date


def write_json(facilities: List[Facility]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = [asdict(facility) for facility in facilities]
    DATA_DIR.joinpath("facilities.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_facility_pages(facilities: List[Facility], update_date: str | None) -> None:
    FACILITY_DIR.mkdir(parents=True, exist_ok=True)
    asset_prefix = "../assets"
    for facility in FACILITY_DIR.glob("*.html"):
        facility.unlink()

    for facility in facilities:
        map_url = f"https://www.google.com/maps/search/?api=1&query={facility.address}"
        html = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{facility.name}｜新市區防空避難設施</title>
  <link rel="stylesheet" href="{asset_prefix}/styles.css" />
</head>
<body class="page">
  <header class="hero">
    <div class="hero__content">
      <p class="eyebrow">新市區防空避難設施</p>
      <h1>{facility.name}</h1>
      <p class="subhead">{facility.village} · {facility.division or '轄區分局未註明'}</p>
    </div>
  </header>
  <main class="content">
    <section class="card detail-card">
      <dl>
        <div class="field">
          <dt>地址</dt>
          <dd>{facility.address}</dd>
        </div>
        <div class="field">
          <dt>可容納人數</dt>
          <dd>{facility.capacity or '未提供'}</dd>
        </div>
        <div class="field">
          <dt>轄管分局</dt>
          <dd>{facility.division or '未提供'}</dd>
        </div>
        <div class="field">
          <dt>所在里</dt>
          <dd>{facility.village}</dd>
        </div>
        <div class="field">
          <dt>行政區</dt>
          <dd>{facility.district}</dd>
        </div>
      </dl>
      <div class="actions">
        <a class="button" href="{map_url}" target="_blank" rel="noopener noreferrer">在地圖上查看</a>
        <a class="button button--ghost" href="../index.html">返回設施總覽</a>
      </div>
      {"<p class='meta'>資料更新日期：" + update_date + "</p>" if update_date else ""}
    </section>
  </main>
</body>
</html>
"""
        FACILITY_DIR.joinpath(f"{facility.slug}.html").write_text(html, encoding="utf-8")


def build_index(update_date: str | None) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    assets_prefix = "./assets"
    html = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>新市區防空避難設施</title>
  <link rel="stylesheet" href="{assets_prefix}/styles.css" />
</head>
<body>
  <header class="hero">
    <div class="hero__content">
      <p class="eyebrow">GitHub Pages</p>
      <h1>新市區防空避難設施</h1>
      <p class="subhead">逐一查看每個避難設施的詳細資料，並透過地圖快速定位。</p>
      {"<p class='meta'>資料更新日期：" + update_date + "</p>" if update_date else ""}
    </div>
  </header>
  <main class="content">
    <section class="controls card">
      <div class="control">
        <label for="search">搜尋名稱或地址</label>
        <input id="search" type="search" placeholder="輸入關鍵字…" />
      </div>
      <div class="control">
        <label for="village">按里別篩選</label>
        <select id="village">
          <option value="">所有里別</option>
        </select>
      </div>
      <div class="control">
        <label for="division">按轄管分局篩選</label>
        <select id="division">
          <option value="">所有分局</option>
        </select>
      </div>
    </section>
    <section id="facility-list" class="grid"></section>
  </main>
  <script type="module" src="{assets_prefix}/main.js"></script>
</body>
</html>
"""
    DOCS_DIR.joinpath("index.html").write_text(html, encoding="utf-8")


def main() -> None:
    facilities, update_date = extract_facilities()
    write_json(facilities)
    build_index(update_date)
    build_facility_pages(facilities, update_date)
    print(f"Generated {len(facilities)} facility pages.")


if __name__ == "__main__":
    main()
