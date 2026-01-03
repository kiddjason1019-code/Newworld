"""Generate static GitHub Pages for 新市區防空避難設施資料.

This script parses the bundled PDF (新市區-1130702.pdf) using only
standard library modules, converts it into structured data, and writes a
GitHub Pages-ready site into the ``docs`` directory:

* docs/data/facilities.json – machine-readable data
* docs/index.html – landing page with search and links
* docs/facilities/<slug>.html – dedicated page per facility

Run it from the repository root:

    python scripts/build_sites.py
"""

from __future__ import annotations

import html
import json
import re
import textwrap
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "新市區-1130702.pdf"
DOCS_DIR = ROOT / "docs"
DATA_DIR = DOCS_DIR / "data"
FACILITIES_DIR = DOCS_DIR / "facilities"


@dataclass
class Facility:
    area: str
    village: str
    name: str
    address: str
    capacity: int
    division: str
    slug: str


def _build_unicode_map(pdf_text: str) -> Dict[int, str]:
    """Extract the ToUnicode CMap mapping for glyph decoding."""

    mapping: Dict[int, str] = {}
    for block in re.findall(r"beginbfchar(.*?)endbfchar", pdf_text, re.S):
        for code, uni in re.findall(r"<([0-9A-F]+)>\s*<([0-9A-F]+)>", block):
            mapping[int(code, 16)] = chr(int(uni, 16))
    return mapping


def _extract_text_runs(pdf_bytes: bytes, mapping: Dict[int, str]) -> str:
    """Return concatenated text from BT/ET blocks using the provided map."""

    text_content: List[str] = []
    hex_re = re.compile(br"<([0-9A-F]+)>")

    for match in re.finditer(br"stream\r?\n", pdf_bytes):
        start = match.end()
        end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            continue

        raw = pdf_bytes[start:end].strip(b"\r\n")
        try:
            decoded = zlib.decompress(raw)
        except Exception:
            # Non-compressed streams (e.g., metadata, images) – skip.
            continue

        if b"BT" not in decoded:
            continue

        for glyph in hex_re.findall(decoded):
            text_content.append(mapping.get(int(glyph, 16), "?"))

    return "".join(text_content)


def _parse_facilities(raw_text: str) -> List[Facility]:
    """Convert raw text into structured facility objects."""

    header = "區別里別名稱地址容量(可容納人數)轄管分局"
    cleaned = raw_text.replace(header, "")
    entries = cleaned.split("善化分局")

    facilities: List[Facility] = []
    for index, entry in enumerate(entries):
        trimmed = entry.strip()
        if not trimmed:
            continue

        trimmed += "善化分局"  # add the delimiter back for consistent parsing
        match = re.match(r"(?P<area>.{2,3}區)(?P<village>[^里]+里)(?P<rest>.+)", trimmed)
        if not match:
            continue

        area = match.group("area")
        village = match.group("village")
        rest = match.group("rest")

        address_start = rest.find("臺南市")
        if address_start == -1:
            continue

        name = rest[:address_start]
        address_and_capacity = rest[address_start:]

        capacity_match = re.search(r"(\d+)(善化分局)$", address_and_capacity)
        if not capacity_match:
            continue

        capacity = int(capacity_match.group(1))
        address = address_and_capacity[: capacity_match.start(1)]
        slug = f"facility-{index + 1:03d}"

        facilities.append(
            Facility(
                area=area,
                village=village,
                name=name,
                address=address,
                capacity=capacity,
                division="善化分局",
                slug=slug,
            )
        )

    return facilities


def extract_facilities(pdf_path: Path = PDF_PATH) -> List[Facility]:
    pdf_text = pdf_path.read_text("latin-1")
    unicode_map = _build_unicode_map(pdf_text)
    raw_text = _extract_text_runs(pdf_path.read_bytes(), unicode_map)
    return _parse_facilities(raw_text)


def _write_json(facilities: Iterable[Facility]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = [asdict(facility) for facility in facilities]
    DATA_DIR.joinpath("facilities.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_facility_page(facility: Facility) -> None:
    FACILITIES_DIR.mkdir(parents=True, exist_ok=True)
    body = f"""
    <!doctype html>
    <html lang=\"zh-Hant\">
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>{html.escape(facility.name)}｜新市區防空避難設施</title>
        <link rel=\"stylesheet\" href=\"../assets/style.css\" />
      </head>
      <body>
        <header class=\"site-header\">
          <div class=\"container\">
            <a class=\"breadcrumb\" href=\"../index.html\">← 回首頁</a>
            <h1>{html.escape(facility.name)}</h1>
            <p class=\"subtitle\">{html.escape(facility.area)} · {html.escape(facility.village)}</p>
          </div>
        </header>
        <main class=\"container card\">
          <dl class=\"facility-details\">
            <div>
              <dt>地址</dt>
              <dd>{html.escape(facility.address)}</dd>
            </div>
            <div>
              <dt>容量（人）</dt>
              <dd>{facility.capacity:,}</dd>
            </div>
            <div>
              <dt>轄管分局</dt>
              <dd>{html.escape(facility.division)}</dd>
            </div>
          </dl>
        </main>
        <footer class=\"site-footer\">
          <div class=\"container\">
            <p>資料來源：{html.escape(PDF_PATH.name)}。此頁面由 scripts/build_sites.py 自動生成。</p>
          </div>
        </footer>
      </body>
    </html>
    """
    FACILITIES_DIR.joinpath(f"{facility.slug}.html").write_text(
        textwrap.dedent(body), encoding="utf-8"
    )


def _write_index(facilities: List[Facility]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    cards_markup = "\n".join(
        f"""
        <article class=\"facility-card\" data-village=\"{html.escape(f.village)}\" data-name=\"{html.escape(f.name)}\" data-address=\"{html.escape(f.address)}\">
          <h2><a href=\"facilities/{f.slug}.html\">{html.escape(f.name)}</a></h2>
          <p class=\"meta\">{html.escape(f.area)} · {html.escape(f.village)}</p>
          <p>{html.escape(f.address)}</p>
          <p class=\"capacity\">容量：{f.capacity:,} 人</p>
        </article>
        """
        for f in facilities
    )

    html_doc = f"""
    <!doctype html>
    <html lang=\"zh-Hant\">
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>新市區防空避難設施</title>
        <link rel=\"stylesheet\" href=\"assets/style.css\" />
      </head>
      <body>
        <header class=\"site-header\">
          <div class=\"container\">
            <h1>新市區防空避難設施</h1>
            <p class=\"subtitle\">資料來源：{html.escape(PDF_PATH.name)}（自動解析生成）</p>
            <div class=\"search-row\">
              <label for=\"search\">快速搜尋（名稱 / 里別 / 地址）：</label>
              <input id=\"search\" type=\"search\" placeholder=\"輸入關鍵字...\" />
            </div>
          </div>
        </header>
        <main class=\"container\">
          <section class=\"grid\" id=\"facility-list\">
            {cards_markup}
          </section>
        </main>
        <footer class=\"site-footer\">
          <div class=\"container\">
            <p>此站點由 <code>scripts/build_sites.py</code> 解析 PDF 並生成，適用於 GitHub Pages 的 <code>docs</code> 目錄。</p>
          </div>
        </footer>
        <script>
          const searchInput = document.getElementById('search');
          const cards = Array.from(document.querySelectorAll('.facility-card'));
          searchInput.addEventListener('input', () => {{
            const term = searchInput.value.trim();
            const tokens = term.split(/\s+/).filter(Boolean);
            cards.forEach(card => {{
              const haystack = (card.dataset.village + card.dataset.name + card.dataset.address).toLowerCase();
              const show = tokens.every(token => haystack.includes(token.toLowerCase()));
              card.style.display = show ? '' : 'none';
            }});
          }});
        </script>
      </body>
    </html>
    """
    DOCS_DIR.joinpath("index.html").write_text(textwrap.dedent(html_doc), encoding="utf-8")


def _write_styles() -> None:
    assets_dir = DOCS_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    css = """
    :root {
      --bg: #0f172a;
      --card: #111827;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #60a5fa;
      --border: #1f2937;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: "Inter", "Noto Sans TC", system-ui, -apple-system, sans-serif;
      background: radial-gradient(circle at top left, rgba(96,165,250,0.12), rgba(96,165,250,0)),
                  radial-gradient(circle at top right, rgba(52,211,153,0.12), rgba(52,211,153,0)),
                  var(--bg);
      color: var(--text);
      min-height: 100vh;
    }

    .container {
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 1.25rem 2rem;
    }

    .site-header {
      padding: 2rem 0 1rem;
    }

    .site-header h1 {
      margin: 0;
      font-size: 2.4rem;
      letter-spacing: 0.02em;
    }

    .subtitle {
      margin: 0.35rem 0 1.2rem;
      color: var(--muted);
    }

    .search-row {
      display: grid;
      gap: 0.5rem;
      margin-top: 0.75rem;
    }

    input[type="search"] {
      padding: 0.85rem 1rem;
      border-radius: 0.75rem;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      font-size: 1rem;
      outline: none;
    }

    input[type="search"]:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(96,165,250,0.25);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 1rem;
      margin-top: 1.5rem;
    }

    .facility-card, .card {
      background: rgba(17, 24, 39, 0.8);
      border: 1px solid var(--border);
      border-radius: 1rem;
      padding: 1.25rem;
      box-shadow: 0 10px 35px rgba(0,0,0,0.3);
      transition: transform 0.15s ease, border-color 0.15s ease;
    }

    .facility-card:hover {
      transform: translateY(-4px);
      border-color: var(--accent);
    }

    .facility-card h2 {
      margin: 0 0 0.3rem;
      font-size: 1.3rem;
    }

    .facility-card a {
      color: #bfdbfe;
      text-decoration: none;
    }

    .facility-card a:hover {
      color: #fff;
    }

    .facility-card .meta {
      margin: 0 0 0.4rem;
      color: var(--muted);
    }

    .facility-card p {
      margin: 0.2rem 0;
      line-height: 1.5;
    }

    .capacity {
      color: #a5b4fc;
      font-weight: 600;
    }

    .site-footer {
      padding: 2rem 0;
      color: var(--muted);
      border-top: 1px solid var(--border);
      margin-top: 2rem;
    }

    .breadcrumb {
      color: #bfdbfe;
      text-decoration: none;
      display: inline-block;
      margin-bottom: 0.8rem;
    }

    .breadcrumb:hover {
      color: #fff;
    }

    .card h1 {
      margin-top: 0;
    }

    .facility-details {
      display: grid;
      gap: 0.75rem;
      margin: 0;
    }

    .facility-details div {
      background: rgba(255,255,255,0.02);
      padding: 0.75rem 1rem;
      border-radius: 0.75rem;
      border: 1px solid var(--border);
    }

    .facility-details dt {
      font-weight: 600;
      color: #c7d2fe;
      margin: 0 0 0.35rem;
    }

    .facility-details dd {
      margin: 0;
      line-height: 1.5;
    }
    """
    assets_dir.joinpath("style.css").write_text(textwrap.dedent(css), encoding="utf-8")


def build_site() -> None:
    facilities = extract_facilities()
    _write_json(facilities)
    _write_styles()
    for facility in facilities:
        _write_facility_page(facility)
    _write_index(facilities)
    print(f"Generated {len(facilities)} facility pages into {DOCS_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    build_site()
