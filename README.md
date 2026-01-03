# 新市區防空避難設施 GitHub Pages

這個倉庫會把「新市區防空避難設施一覽表」PDF 轉成靜態網站，方便部署到 GitHub Pages。根目錄下的 `index.html` 是入口頁，`facilities/` 底下則是每一個避難設施的獨立頁面。

## 如何重新產生資料與頁面

1. 從 PDF 萃取最新資料（會輸出 `data/shelters.json`）：

   ```bash
   python scripts/extract_shelters.py
   ```

2. 依據 JSON 產生首頁與 41 個獨立頁面：

   ```bash
   python scripts/build_pages.py
   ```

3. 將產出的 `index.html`、`facilities/`、`assets/` 直接推到 GitHub Pages，或在本機用瀏覽器開啟 `index.html` 確認內容。

## 資料來源

`新市區-1130702.pdf`：臺南市新市區防空疏散避難設施一覽表（113/07/02 更新）。
