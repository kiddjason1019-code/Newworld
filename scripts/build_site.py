from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote_plus

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

from extract_shelters import extract_shelters, write_json


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "shelters.json"
DOCS_PATH = ROOT / "docs"


def slugify(text: str, index: int) -> str:
    base = f"{index + 1}-{text}"
    safe = re.sub(r"[^\w\u4e00-\u9fff-]", "-", base)
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe or f"shelter-{index + 1}"


def with_slug(shelters: List[Dict[str, str | int]]) -> List[Dict[str, str | int]]:
    enriched: List[Dict[str, str | int]] = []
    for idx, shelter in enumerate(shelters):
        label = f"{shelter['village']}-{shelter['name']}"
        enriched.append({**shelter, "slug": slugify(label, idx)})
    return enriched


def render_index(shelters: List[Dict[str, str | int]]) -> str:
    shelters_json = json.dumps(shelters, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>新市區防空避難設施</title>
  <link rel="stylesheet" href="./assets/style.css">
</head>
<body>
  <header class="hero">
    <div class="container">
      <p class="eyebrow">臺南市新市區</p>
      <h1>防空疏散避難設施一覽</h1>
      <p class="lede">113/07/02 最新資料，為每個避難設施提供獨立的頁面與地圖導覽連結。</p>
      <label class="search-label">
        <span>搜尋名稱、里別或地址</span>
        <input id="search" type="search" placeholder="例：豐華里、聯華電子、看西路">
      </label>
    </div>
  </header>

  <main class="container">
    <section id="results" class="grid" aria-live="polite"></section>
  </main>

  <script id="shelter-data" type="application/json">{html.escape(shelters_json)}</script>
  <script src="./assets/main.js"></script>
</body>
</html>
"""


def render_shelter_page(shelter: Dict[str, str | int]) -> str:
    address = html.escape(str(shelter["address"]))
    name = html.escape(str(shelter["name"]))
    village = html.escape(str(shelter["village"]))
    capacity = html.escape(str(shelter["capacity"]))
    branch = html.escape(str(shelter["branch"]))
    map_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(str(shelter['address']))}"

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name}｜新市區防空避難設施</title>
  <link rel="stylesheet" href="../assets/style.css">
</head>
<body class="detail">
  <header class="hero">
    <div class="container">
      <p class="eyebrow">臺南市新市區 · {village}</p>
      <h1>{name}</h1>
      <p class="lede">收容量：{capacity} 人 · 轄管分局：{branch}</p>
      <div class="actions">
        <a class="button" href="{map_url}" target="_blank" rel="noopener">在地圖上查看</a>
        <a class="ghost" href="../index.html">返回列表</a>
      </div>
    </div>
  </header>

  <main class="container card">
    <dl class="meta">
      <div>
        <dt>地址</dt>
        <dd>{address}</dd>
      </div>
      <div>
        <dt>里別</dt>
        <dd>{village}</dd>
      </div>
      <div>
        <dt>收容量</dt>
        <dd>{capacity} 人</dd>
      </div>
      <div>
        <dt>轄管分局</dt>
        <dd>{branch}</dd>
      </div>
    </dl>
  </main>
</body>
</html>
"""


def write_assets() -> None:
    assets_dir = DOCS_PATH / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    (assets_dir / "style.css").write_text(
        (
            ROOT / "scripts" / "style.css.template"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    (assets_dir / "main.js").write_text(
        (
            ROOT / "scripts" / "main.js.template"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def write_pages(shelters: List[Dict[str, str | int]]) -> None:
    DOCS_PATH.mkdir(parents=True, exist_ok=True)
    write_assets()

    (DOCS_PATH / "index.html").write_text(render_index(shelters), encoding="utf-8")

    facilities_dir = DOCS_PATH / "facilities"
    if facilities_dir.exists():
        shutil.rmtree(facilities_dir)
    facilities_dir.mkdir()

    for shelter in shelters:
        page_dir = facilities_dir / str(shelter["slug"])
        page_dir.mkdir(exist_ok=True)
        (page_dir / "index.html").write_text(render_shelter_page(shelter), encoding="utf-8")


def main() -> None:
    shelters = with_slug(extract_shelters())
    write_json(DATA_PATH, shelters)
    write_pages(shelters)
    print(f"Generated {len(shelters)} shelter pages in docs/")


if __name__ == "__main__":
    main()
