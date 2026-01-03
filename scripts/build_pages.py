from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "shelters.json"
FACILITY_DIR = ROOT / "facilities"
INDEX_PATH = ROOT / "index.html"


def format_capacity(value: int | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,}"


def facility_slug(index: int) -> str:
    return f"shelter-{index + 1:02d}"


def render_facility_page(shelter: dict, slug: str) -> str:
    address = shelter["address"]
    map_link = (
        "https://www.google.com/maps/search/?api=1&query=" + quote_plus(address)
    )
    return f"""<!doctype html>
<html lang=\"zh-Hant\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{shelter['name']}｜新市區防空避難設施</title>
  <link rel=\"stylesheet\" href=\"../assets/style.css\" />
</head>
<body class=\"page\">
  <header class=\"site-header\">
    <div class=\"container\">
      <a href=\"../index.html\" class=\"brand\">新市區防空避難設施</a>
      <nav class=\"breadcrumb\">
        <a href=\"../index.html\">首頁</a>
        <span aria-hidden=\"true\">/</span>
        <span>{shelter['name']}</span>
      </nav>
    </div>
  </header>

  <main class=\"container\">
    <article class=\"facility-card\">
      <p class=\"eyebrow\">防空避難設施</p>
      <h1>{shelter['name']}</h1>
      <dl class=\"facility-meta\">
        <div>
          <dt>地址</dt>
          <dd>{address}</dd>
        </div>
        <div>
          <dt>可容納人數</dt>
          <dd>{format_capacity(shelter['capacity'])}</dd>
        </div>
        <div>
          <dt>轄管分局</dt>
          <dd>{shelter['precinct']}</dd>
        </div>
      </dl>
      <div class=\"actions\">
        <a class=\"button primary\" href=\"{map_link}\" target=\"_blank\" rel=\"noreferrer\">在地圖中查看</a>
        <a class=\"button ghost\" href=\"../新市區-1130702.pdf\" target=\"_blank\" rel=\"noreferrer\">查看原始 PDF</a>
      </div>
      <p class=\"note\">資料來源：臺南市新市區防空疏散避難設施一覽表（113/07/02 更新）。</p>
    </article>
  </main>
</body>
</html>
"""


def render_index(shelters: list[dict]) -> str:
    cards_html = []
    for idx, shelter in enumerate(shelters):
        slug = facility_slug(idx)
        cards_html.append(
            f"""
        <article class=\"card\" data-card data-index=\"{idx}\" data-name=\"{shelter['name']}\" data-address=\"{shelter['address']}\" data-precinct=\"{shelter['precinct']}\" data-capacity=\"{shelter['capacity']}\">
          <p class=\"eyebrow\">防空避難設施</p>
          <h2>{shelter['name']}</h2>
          <p class=\"muted\">{shelter['address']}</p>
          <div class=\"meta\">
            <span>容量：{format_capacity(shelter['capacity'])}</span>
            <span>分局：{shelter['precinct']}</span>
          </div>
          <a class=\"button ghost\" href=\"facilities/{slug}.html\">查看獨立頁面</a>
        </article>
        """
        )

    precincts = sorted({s["precinct"] for s in shelters})
    precinct_options = "".join(
        f"<option value=\"{precinct}\">{precinct}</option>" for precinct in precincts
    )

    return f"""<!doctype html>
<html lang=\"zh-Hant\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>新市區防空避難設施｜GitHub Pages 網站</title>
  <link rel=\"stylesheet\" href=\"assets/style.css\" />
</head>
<body>
  <header class=\"hero\">
    <div class=\"container\">
      <p class=\"eyebrow\">GitHub Pages</p>
      <h1>新市區防空避難設施</h1>
      <p class=\"lead\">直接從倉庫生成的靜態網站，為每一個避難設施提供獨立頁面。</p>
      <div class=\"controls\">
        <label class=\"control\">
          <span>搜尋名稱或地址</span>
          <input id=\"search\" type=\"search\" placeholder=\"輸入關鍵字\" />
        </label>
        <label class=\"control\">
          <span>轄管分局</span>
          <select id=\"precinct-filter\">
            <option value=\"\">全部</option>
            {precinct_options}
          </select>
        </label>
        <label class=\"control\">
          <span>排序</span>
          <select id=\"sort\">
            <option value=\"default\">原始順序</option>
            <option value=\"capacity-desc\">容量（大 → 小）</option>
            <option value=\"capacity-asc\">容量（小 → 大）</option>
          </select>
        </label>
      </div>
      <p id=\"result-count\" class=\"muted\"></p>
    </div>
  </header>

  <main class=\"container\">
    <section id=\"card-grid\" class=\"grid\">
      {''.join(cards_html)}
    </section>
  </main>

  <footer class=\"site-footer\">
    <div class=\"container\">
      <p>資料來源：<a href=\"新市區-1130702.pdf\" target=\"_blank\" rel=\"noreferrer\">臺南市新市區防空疏散避難設施一覽表</a>（113/07/02 更新）。</p>
      <p>此站點可直接部署於 GitHub Pages。</p>
    </div>
  </footer>

  <script src=\"assets/main.js\"></script>
</body>
</html>
"""


def build() -> None:
    shelters = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    FACILITY_DIR.mkdir(parents=True, exist_ok=True)

    for idx, shelter in enumerate(shelters):
        slug = facility_slug(idx)
        html = render_facility_page(shelter, slug)
        (FACILITY_DIR / f"{slug}.html").write_text(html, encoding="utf-8")

    INDEX_PATH.write_text(render_index(shelters), encoding="utf-8")
    print(f"Generated index and {len(shelters)} facility pages.")


if __name__ == "__main__":
    build()
