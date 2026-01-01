from __future__ import annotations
import json
import re
import urllib.parse
import zlib
from dataclasses import dataclass, asdict
from string import Template
from pathlib import Path
from typing import Dict, Iterable, List

PDF_PATH = Path("新市區-1130702.pdf")
DATA_PATH = Path("data/facilities.json")
DOCS_DIR = Path("docs")


@dataclass
class Facility:
    district: str
    li: str
    name: str
    address: str
    capacity: int
    branch: str
    slug: str


def extract_to_unicode_mapping(pdf_bytes: bytes) -> Dict[int, int]:
    ref_match = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", pdf_bytes)
    if not ref_match:
        raise ValueError("Could not find ToUnicode reference in PDF")
    obj_num = ref_match.group(1).decode()
    obj_pattern = re.compile(fr"{obj_num} 0 obj(.*?)endobj", re.S)
    obj_match = obj_pattern.search(pdf_bytes.decode("latin-1"))
    if not obj_match:
        raise ValueError("Could not locate ToUnicode object in PDF")
    obj_content = obj_match.group(1).encode("latin-1")
    stream = obj_content.split(b"stream", 1)[1].split(b"endstream", 1)[0]
    mapping = {}
    for src, dst in re.findall(r"<([0-9A-F]+)>\s+<([0-9A-F]+)>", stream.decode("latin-1")):
        mapping[int(src, 16)] = int(dst, 16)
    if not mapping:
        raise ValueError("Parsed ToUnicode mapping is empty")
    return mapping


def decode_text_streams(pdf_bytes: bytes, mapping: Dict[int, int]) -> str:
    decoded_chunks: List[str] = []
    for match in re.finditer(rb"stream\r?\n", pdf_bytes):
        start = match.end()
        end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            continue
        stream = pdf_bytes[start:end]
        try:
            decompressed = zlib.decompress(stream)
        except Exception:
            continue
        hex_codes = re.findall(rb"<([0-9A-F]+)>", decompressed)
        if not hex_codes:
            continue
        decoded_chunks.append(
            "".join(chr(mapping.get(int(code, 16), int(code, 16))) for code in hex_codes)
        )
    return "".join(decoded_chunks)


def parse_facilities(text: str) -> List[Facility]:
    start = text.find("新市區")
    if start == -1:
        raise ValueError("Could not find starting district text")
    trimmed = text[start:]
    pattern = re.compile(r"(新市區)(.{2,4}里)(.+?)(臺南市新市區.+?號)(\d+)(善化分局)")
    raw_entries = []
    for match in pattern.finditer(trimmed):
        district, li, name, address, capacity, branch = match.groups()
        raw_entries.append(
            {
                "district": district,
                "li": li,
                "name": name,
                "address": address,
                "capacity": int(capacity),
                "branch": branch,
            }
        )
    facilities: List[Facility] = []
    slug_counts: Dict[str, int] = {}
    for entry in raw_entries:
        base_slug = "".join(ch for ch in entry["name"] if ch.isalnum()) or "facility"
        slug_counts.setdefault(base_slug, 0)
        slug_counts[base_slug] += 1
        slug = base_slug if slug_counts[base_slug] == 1 else f"{base_slug}-{slug_counts[base_slug]}"
        facilities.append(Facility(slug=slug, **entry))
    if not facilities:
        raise ValueError("No facilities parsed from PDF text")
    return facilities


def write_json(facilities: Iterable[Facility]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump([asdict(facility) for facility in facilities], f, ensure_ascii=False, indent=2)


def build_index_html(facilities: List[Facility]) -> str:
    cards = []
    for facility in facilities:
        search_text = f"{facility.district} {facility.li} {facility.name} {facility.address} {facility.branch}"
        cards.append(
            f"""
            <article class=\"card\" data-search=\"{search_text}\">
              <div class=\"eyebrow\">{facility.district} · {facility.li}</div>
              <h2>{facility.name}</h2>
              <p class=\"address\">{facility.address}</p>
              <p class=\"meta\">容量：{facility.capacity:,} 人 ｜ 轄管分局：{facility.branch}</p>
              <div class=\"actions\">
                <a class=\"button\" href=\"facilities/{facility.slug}/index.html\">查看專頁</a>
                <a class=\"ghost\" href=\"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(facility.address)}\" target=\"_blank\" rel=\"noreferrer noopener\">在地圖開啟</a>
              </div>
            </article>
            """
        )
    cards_html = "\n".join(cards)
    template = Template(
        """
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>新市區防空避難設施</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header class="hero">
    <div>
      <p class="eyebrow">臺南市新市區</p>
      <h1>防空疏散避難設施一覽</h1>
      <p class="lede">從官方 PDF 自動轉換，方便快速找到最近的避難設施。點擊卡片即可查看專頁，或在地圖開啟路線。</p>
      <div class="search">
        <label for="search">搜尋設施名稱、里別或地址</label>
        <input id="search" type="search" placeholder="輸入關鍵字..." />
      </div>
    </div>
  </header>
  <main class="grid" id="facility-grid">
    $cards_html
  </main>
  <script>
    const searchInput = document.getElementById('search');
    const cards = Array.from(document.querySelectorAll('.card'));
    searchInput.addEventListener('input', () => {
      const term = searchInput.value.trim().toLowerCase();
      cards.forEach(card => {
        const haystack = card.dataset.search.toLowerCase();
        const match = haystack.includes(term);
        card.style.display = match ? '' : 'none';
      });
    });
  </script>
</body>
</html>
"""
    )
    return template.substitute(cards_html=cards_html)


def build_facility_page(facility: Facility) -> str:
    map_link = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(facility.address)}"
    return f"""
<!doctype html>
<html lang=\"zh-Hant\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{facility.name}｜新市區防空避難設施</title>
  <link rel=\"stylesheet\" href=\"../../styles.css\" />
</head>
<body class=\"detail\">
  <main class=\"panel\">
    <a class=\"back\" href=\"../../index.html\">← 返回列表</a>
    <p class=\"eyebrow\">{facility.district} · {facility.li}</p>
    <h1>{facility.name}</h1>
    <dl class=\"stats\">
      <div>
        <dt>容量（人數）</dt>
        <dd>{facility.capacity:,}</dd>
      </div>
      <div>
        <dt>轄管分局</dt>
        <dd>{facility.branch}</dd>
      </div>
    </dl>
    <section class=\"section\">
      <h2>地址</h2>
      <p class=\"address\">{facility.address}</p>
      <p><a class=\"button\" href=\"{map_link}\" target=\"_blank\" rel=\"noreferrer noopener\">在地圖開啟</a></p>
    </section>
    <section class=\"section\">
      <h2>資料來源</h2>
      <p>根據臺南市政府提供的「新市區防空疏散避難設施」PDF（113/07/02 更新）。</p>
    </section>
  </main>
</body>
</html>
"""


def write_facility_pages(facilities: List[Facility]) -> None:
    facilities_dir = DOCS_DIR / "facilities"
    for facility in facilities:
        page_dir = facilities_dir / facility.slug
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(build_facility_page(facility), encoding="utf-8")


def write_index_page(facilities: List[Facility]) -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "index.html").write_text(build_index_html(facilities), encoding="utf-8")


def write_styles() -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "styles.css").write_text(
        """
:root {
  color-scheme: light;
  --bg: #f6f7fb;
  --panel: #ffffff;
  --text: #1f2933;
  --muted: #55606d;
  --accent: #0b6cff;
  --border: #e5e7ef;
  --shadow: 0 10px 40px rgba(16, 24, 40, 0.08);
  font-family: "Noto Sans TC", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}
.hero {
  padding: 64px clamp(20px, 5vw, 80px);
  background: linear-gradient(135deg, #e8f0ff, #f6f9ff);
  border-bottom: 1px solid var(--border);
}
.hero h1 { margin: 8px 0 12px; font-size: clamp(28px, 3vw, 40px); }
.hero .lede { max-width: 720px; color: var(--muted); }
.eyebrow { letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); font-size: 13px; }
.search { margin-top: 20px; display: grid; gap: 8px; max-width: 480px; }
.search input {
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  font-size: 16px;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.04);
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
  padding: 32px clamp(20px, 5vw, 80px) 80px;
}
.card {
  background: var(--panel);
  border-radius: 16px;
  padding: 20px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  display: grid;
  gap: 10px;
}
.card h2 { margin: 0; font-size: 20px; }
.address { color: var(--muted); margin: 0; }
.meta { margin: 0; color: var(--muted); font-size: 14px; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.button {
  background: var(--accent);
  color: white;
  padding: 10px 14px;
  border-radius: 10px;
  text-decoration: none;
  font-weight: 600;
}
.ghost {
  color: var(--accent);
  padding: 10px 12px;
  text-decoration: none;
  font-weight: 600;
}
.detail {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 16px;
}
.panel {
  background: var(--panel);
  border-radius: 18px;
  padding: clamp(20px, 5vw, 48px);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  max-width: 760px;
  width: min(760px, 100%);
  display: grid;
  gap: 16px;
}
.panel h1 { margin: 0; }
.back { color: var(--accent); text-decoration: none; font-weight: 600; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 0; }
.stats div { padding: 12px; border: 1px dashed var(--border); border-radius: 12px; background: #fbfdff; }
.stats dt { margin: 0; color: var(--muted); font-weight: 600; }
.stats dd { margin: 4px 0 0; font-size: 24px; font-weight: 700; }
.section { padding: 12px 0; border-top: 1px solid var(--border); }
.section h2 { margin: 0 0 8px; }
@media (max-width: 540px) {
  .actions { flex-direction: column; }
  .hero { padding: 48px 16px; }
}
""",
        encoding="utf-8",
    )


def main() -> None:
    pdf_bytes = PDF_PATH.read_bytes()
    mapping = extract_to_unicode_mapping(pdf_bytes)
    text = decode_text_streams(pdf_bytes, mapping)
    facilities = parse_facilities(text)
    write_json(facilities)
    write_index_page(facilities)
    write_facility_pages(facilities)
    write_styles()
    print(f"Generated {len(facilities)} facility pages in {DOCS_DIR}/facilities")


if __name__ == "__main__":
    main()
