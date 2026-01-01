"""Generate static GitHub Pages for each shelter facility.

The script reads ``data/facilities.json`` (created by ``extract_facilities.py``)
and writes HTML files to the ``docs`` directory so GitHub Pages can host them.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "facilities.json"
DOCS_ROOT = ROOT / "docs"


def load_facilities() -> List[Dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_layout(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang=\"zh-Hant\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(title)}</title>
  <link rel=\"stylesheet\" href=\"/styles.css\" />
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <nav><a href=\"/index.html\">回首頁</a></nav>
  </header>
  <main>
    {body}
  </main>
  <footer>
    <p>資料來源：新市區防空疏散避難設施 (113/07/02 更新)</p>
  </footer>
</body>
</html>
"""


def render_index(facilities: List[Dict]) -> str:
    rows = []
    for facility in facilities:
        rows.append(
            f"<tr><td>{facility['id']}</td>"
            f"<td><a href=\"/facilities/{facility['slug']}/index.html\">{html.escape(facility['site_name'])}</a></td>"
            f"<td>{html.escape(facility['village'])}</td>"
            f"<td>{html.escape(facility['address'])}</td>"
            f"<td>{facility['capacity']}</td>"
            f"<td>{html.escape(facility['precinct'])}</td></tr>"
        )
    body = """
<section class=\"intro\">
  <p>以下列出新市區 113/07/02 更新的防空疏散避難設施，點擊每筆可查看獨立頁面。</p>
</section>
<table>
  <thead>
    <tr><th>#</th><th>避難設施</th><th>里別</th><th>地址</th><th>容量</th><th>轄管分局</th></tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
""".format(rows="\n    ".join(rows))
    return render_layout("新市區防空避難設施", body)


def render_detail(facility: Dict) -> str:
    body = f"""
<section class=\"detail\">
  <p class=\"breadcrumb\"><a href=\"/index.html\">&larr; 返回列表</a></p>
  <h2>{html.escape(facility['site_name'])}</h2>
  <dl>
    <dt>里別</dt><dd>{html.escape(facility['village'])}</dd>
    <dt>地址</dt><dd>{html.escape(facility['address'])}</dd>
    <dt>可容納人數</dt><dd>{facility['capacity']}</dd>
    <dt>轄管分局</dt><dd>{html.escape(facility['precinct'])}</dd>
  </dl>
  <p class=\"note\">此頁面由 JSON 資料自動產生。</p>
</section>
"""
    return render_layout(facility["name"], body)


def write_stylesheet() -> None:
    styles = """
* { box-sizing: border-box; }
body { font-family: "Noto Sans TC", "PingFang TC", system-ui, -apple-system, sans-serif; margin: 0; color: #1f2937; background: #f9fafb; }
header { background: #111827; color: #f9fafb; padding: 1.5rem 1rem; }
header nav a { color: #93c5fd; text-decoration: none; }
main { max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
footer { background: #111827; color: #9ca3af; padding: 1rem; text-align: center; }
table { width: 100%; border-collapse: collapse; margin-top: 1rem; background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
th, td { padding: 0.75rem; border-bottom: 1px solid #e5e7eb; text-align: left; }
thead { background: #f3f4f6; }
tbody tr:nth-child(even) { background: #f9fafb; }
tbody tr:hover { background: #eef2ff; }
a { color: #2563eb; }
.detail dl { display: grid; grid-template-columns: 120px 1fr; gap: 0.5rem 1rem; background: white; padding: 1rem; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
.detail dt { font-weight: 700; }
.note { margin-top: 1rem; color: #6b7280; }
.intro { background: #e0f2fe; padding: 1rem; border: 1px solid #bfdbfe; border-radius: 8px; }
.breadcrumb { margin: 0 0 1rem; }
"""
    write_file(DOCS_ROOT / "styles.css", styles)


def build() -> None:
    facilities = load_facilities()
    write_stylesheet()
    write_file(DOCS_ROOT / "index.html", render_index(facilities))
    for facility in facilities:
        detail_path = DOCS_ROOT / "facilities" / facility["slug"] / "index.html"
        write_file(detail_path, render_detail(facility))
    print(f"Generated {len(facilities)} facility pages plus index in {DOCS_ROOT}")


if __name__ == "__main__":
    build()
