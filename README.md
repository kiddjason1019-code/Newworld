# Newworld

## GitHub Pages：新市區防空避難設施

本倉庫已從 `新市區-1130702.pdf` 解析出 41 筆防空避難設施，並在 `docs/` 生成對應的獨立靜態頁面，適用於 GitHub Pages。

### 如何重新產生靜態頁面

1. 確認 Python 3 可執行。
2. 執行指令：

   ```bash
   python scripts/generate_pages.py
   ```

   會在 `docs/` 重新輸出首頁、每一個設施的獨立頁面，以及 `docs/data/facilities.json`。
