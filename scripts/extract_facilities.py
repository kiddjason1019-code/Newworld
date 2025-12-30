"""Extract shelter data from the provided PDF and generate static pages.

This script is intentionally dependency-free so it can run in restricted
environments. It decodes the embedded ToUnicode CMap to recover UTF-8 text,
parses the table-like output, writes a JSON dataset, and builds GitHub Pages
friendly HTML files (one page per facility plus an index).
"""

from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


PDF_PATH = Path("新市區-1130702.pdf")
DATA_DIR = Path("data")
DOCS_DIR = Path("docs")


@dataclass
class Facility:
    name: str
    address: str
    capacity: int
    branch: str
    district: str | None = None
    li: str | None = None
    slug: str | None = None


def load_cmap(raw_pdf: bytes) -> Dict[int, int]:
    """Parse the embedded ToUnicode CMap into a mapping.

    The CMap is stored as a stream; we pull the text between ``stream`` and
    ``endstream`` and then read ``beginbfchar`` / ``beginbfrange`` sections to
    build the full character map.
    """

    pos = raw_pdf.find(b"/CMapName /Adobe-Identity-UCS")
    stream_start = raw_pdf.rfind(b"stream", 0, pos)
    stream_end = raw_pdf.find(b"endstream", stream_start)
    content = raw_pdf[stream_start:stream_end]
    content = content.split(b"stream", 1)[1]
    content = content.split(b"endstream")[0].decode("latin1")

    mapping: Dict[int, int] = {}

    for match in re.finditer(r"(\d+)\s+beginbfchar(.*?)endbfchar", content, re.S):
        body = match.group(2)
        for src, dst in re.findall(r"<([0-9A-F]{4})>\s+<([0-9A-F]{4})>", body):
            mapping[int(src, 16)] = int(dst, 16)

    for match in re.finditer(r"(\d+)\s+beginbfrange(.*?)endbfrange", content, re.S):
        body = match.group(2)
        for start, end, base in re.findall(
            r"<([0-9A-F]{4})>\s+<([0-9A-F]{4})>\s+<([0-9A-F]{4})>", body
        ):
            start_int, end_int, base_int = int(start, 16), int(end, 16), int(base, 16)
            for offset, code in enumerate(range(start_int, end_int + 1)):
                mapping[code] = base_int + offset

        for range_match in re.finditer(r"<([0-9A-F]{4})>\s+<([0-9A-F]{4})>\s+\[(.*?)\]", body, re.S):
            start_int, end_int = int(range_match.group(1), 16), int(range_match.group(2), 16)
            entries = re.findall(r"<([0-9A-F]{4})>", range_match.group(3))
            for offset, code in enumerate(range(start_int, end_int + 1)):
                if offset < len(entries):
                    mapping[code] = int(entries[offset], 16)

    return mapping


def decode_hex_string(hex_string: bytes, cmap: Dict[int, int]) -> str:
    text = ""
    for i in range(0, len(hex_string), 4):
        code = int(hex_string[i : i + 4], 16)
        text += chr(cmap.get(code, 0xFFFD))
    return text


def extract_stream_text(data: bytes, cmap: Dict[int, int]) -> Iterable[str]:
    if data.startswith(b"x\x9c"):
        data = zlib.decompress(data)

    for array in re.finditer(rb"\[([^\]]+)\]\s+TJ", data):
        parts = re.findall(rb"<([0-9A-F]+)>", array.group(1))
        yield "".join(decode_hex_string(part, cmap) for part in parts)


def extract_lines(raw_pdf: bytes, cmap: Dict[int, int]) -> List[str]:
    text_blocks: List[str] = []
    for match in re.finditer(b"stream\r?\n", raw_pdf):
        start = match.end()
        end = raw_pdf.find(b"endstream", start)
        if end == -1:
            continue
        stream_data = raw_pdf[start:end].rstrip(b"\r\n")
        block_text = "\n".join(extract_stream_text(stream_data, cmap))
        if block_text.strip():
            text_blocks.append(block_text)

    lines = [line.strip() for block in text_blocks for line in block.splitlines() if line.strip()]

    def should_skip(line: str) -> bool:
        return any(
            pattern in line
            for pattern in (
                "區別里別名稱地址",
                "容量(可容",
                "轄管分局",
                "防空疏散避難設施一覽表",
                "更新",
                "第1頁",
                "第2頁",
            )
        )

    return [line for line in lines if not should_skip(line)]


def parse_facilities(lines: Sequence[str]) -> List[Facility]:
    facilities: List[Facility] = []
    pending: List[str] = []
    cap_branch_pattern = re.compile(r"(\d+)(.+分局)$")

    for line in lines:
        match = cap_branch_pattern.match(line)
        if match:
            capacity = int(match.group(1))
            branch = match.group(2)
            name_parts: List[str] = []
            address_parts: List[str] = []
            for entry_line in pending:
                if entry_line.startswith("臺南市") or address_parts:
                    address_parts.append(entry_line)
                else:
                    name_parts.append(entry_line)

            name = "".join(name_parts).strip()
            address = "".join(address_parts).strip()

            facilities.append(
                Facility(
                    name=name,
                    address=address,
                    capacity=capacity,
                    branch=branch,
                    district="新市區" if "新市區" in name or "新市區" in address else None,
                    li=_extract_li(name, address),
                )
            )
            pending = []
        else:
            pending.append(line)

    return facilities


def _extract_li(name: str, address: str) -> str | None:
    for text in (name, address):
        match = re.search(r"新市區(\S+里)", text)
        if match:
            return match.group(1)
    return None


def slugify(sequence: int, name: str) -> str:
    fallback = f"facility-{sequence:03d}"
    ascii_name = re.sub(r"[^a-zA-Z0-9]+", "-", name)
    ascii_name = ascii_name.strip("-")
    return f"{fallback}-{ascii_name.lower()}" if ascii_name else fallback


def write_json(facilities: Sequence[Facility]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    output = [facility.__dict__ for facility in facilities]
    json_path = DATA_DIR / "facilities.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


def build_docs(facilities: Sequence[Facility]) -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "styles.css").write_text(_base_styles(), encoding="utf-8")

    # Index page
    index_html = DOCS_DIR / "index.html"
    index_html.write_text(_render_index(facilities), encoding="utf-8")

    # Facility pages
    for facility in facilities:
        page = DOCS_DIR / f"{facility.slug}.html"
        page.write_text(_render_facility(facility), encoding="utf-8")


def _base_styles() -> str:
    return """
:root {
  font-family: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif;
  color: #13293d;
  background: #f7f9fb;
}

body {
  margin: 0;
  padding: 0;
  line-height: 1.6;
}

header {
  background: linear-gradient(135deg, #1f7a8c, #51adcf);
  color: #fff;
  padding: 1.5rem 1rem;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

main {
  max-width: 1080px;
  margin: 0 auto;
  padding: 1.5rem;
}

.search {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

input[type="search"] {
  flex: 1 1 280px;
  padding: 0.75rem 1rem;
  border: 1px solid #d0d7de;
  border-radius: 12px;
  font-size: 1rem;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.08);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem;
}

.card {
  background: #fff;
  border-radius: 14px;
  padding: 1rem 1.1rem;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
  border: 1px solid #e5e7eb;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
}

.pill {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  background: #eef6fb;
  color: #1f7a8c;
  font-weight: 600;
  margin-right: 0.4rem;
  font-size: 0.85rem;
}

a {
  color: #1f7a8c;
  text-decoration: none;
  font-weight: 700;
}

a:hover {
  text-decoration: underline;
}

.details {
  background: #fff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e5e7eb;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

.meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
  margin: 1rem 0;
}

.meta div {
  background: #f7f9fb;
  border-radius: 10px;
  padding: 0.75rem 0.9rem;
  border: 1px solid #e5e7eb;
}

.actions {
  margin-top: 1rem;
}

.btn {
  display: inline-block;
  padding: 0.75rem 1.1rem;
  border-radius: 10px;
  background: #1f7a8c;
  color: #fff;
  font-weight: 700;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}

.btn:hover {
  background: #166079;
}

footer {
  text-align: center;
  padding: 1rem;
  color: #4b5563;
}
"""


def _render_index(facilities: Sequence[Facility]) -> str:
    cards = "\n".join(
        f"""
      <article class=\"card\" data-name=\"{facility.name}\" data-li=\"{facility.li or ''}\">
        <div>
          <div class=\"pill\">{facility.li or '里別未詳'}</div>
          <div class=\"pill\">{facility.branch}</div>
        </div>
        <h3><a href=\"{facility.slug}.html\">{facility.name}</a></h3>
        <p>{facility.address}</p>
        <p>可容納人數：{facility.capacity:,}</p>
      </article>"""
        for facility in facilities
    )

    return f"""
<!doctype html>
<html lang=\"zh-Hant\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>新市區防空避難設施索引</title>
  <link rel=\"stylesheet\" href=\"styles.css\" />
</head>
<body>
  <header>
    <h1>新市區防空避難設施</h1>
    <p>每個避難設施都有專屬頁面，方便 GitHub Pages 發佈與導覽。</p>
  </header>
  <main>
    <section class=\"search\">
      <input id=\"filter\" type=\"search\" placeholder=\"輸入里別或關鍵字搜尋\" aria-label=\"搜尋避難設施\" />
      <div class=\"pill\">總數：{len(facilities)}</div>
    </section>
    <section class=\"grid\" id=\"facility-grid\">
      {cards}
    </section>
  </main>
  <footer>資料來源：新市區113/07/02更新避難設施表</footer>
  <script>
    const input = document.getElementById('filter');
    const cards = Array.from(document.querySelectorAll('.card'));
    input.addEventListener('input', (event) => {{
      const query = event.target.value.trim();
      const words = query.split(/\s+/).filter(Boolean);
      cards.forEach(card => {{
        const haystack = (card.dataset.name + ' ' + card.dataset.li).toLowerCase();
        const matches = words.every(word => haystack.includes(word.toLowerCase()));
        card.style.display = matches ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>
"""


def _render_facility(facility: Facility) -> str:
    map_url = f"https://www.google.com/maps/search/?api=1&query={facility.address}"
    return f"""
<!doctype html>
<html lang=\"zh-Hant\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{facility.name}｜避難設施</title>
  <link rel=\"stylesheet\" href=\"styles.css\" />
</head>
<body>
  <header>
    <h1>{facility.name}</h1>
    <p>獨立介紹頁面，可直接透過 GitHub Pages 存取。</p>
  </header>
  <main>
    <nav><a href=\"index.html\">← 回到避難設施清單</a></nav>
    <article class=\"details\">
      <div class=\"meta\">
        <div><strong>里別：</strong>{facility.li or '未標示'}</div>
        <div><strong>容量：</strong>{facility.capacity:,} 人</div>
        <div><strong>轄管分局：</strong>{facility.branch}</div>
        <div><strong>行政區：</strong>{facility.district or '未標示'}</div>
      </div>
      <p><strong>地址：</strong>{facility.address}</p>
      <div class=\"actions\">
        <a class=\"btn\" href=\"{map_url}\" target=\"_blank\" rel=\"noopener noreferrer\">在地圖上查看</a>
      </div>
    </article>
  </main>
  <footer>資料來源：新市區113/07/02更新避難設施表</footer>
</body>
</html>
"""


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError("找不到避難設施資料的 PDF 檔案")

    raw_pdf = PDF_PATH.read_bytes()
    cmap = load_cmap(raw_pdf)
    lines = extract_lines(raw_pdf, cmap)
    facilities = parse_facilities(lines)

    for idx, facility in enumerate(facilities, start=1):
        facility.slug = slugify(idx, facility.name)

    write_json(facilities)
    build_docs(facilities)

    print(f"共整理 {len(facilities)} 筆避難設施資料，並已生成 docs/ 靜態網頁。")


if __name__ == "__main__":
    main()
