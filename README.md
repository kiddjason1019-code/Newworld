# Newworld

## 防空避難設施 GitHub Pages

本專案會將 `新市區-1130702.pdf` 內的避難設施資料解析為 JSON，並在 `docs/` 產生 GitHub Pages 靜態網站（每個設施都有獨立頁面）。

### 如何重新產生網站

1. 安裝 Python（已內建於開發容器）。
2. 執行下列指令：
   ```bash
   python scripts/build_site.py
   ```
   - 會重新解析 PDF、更新 `data/shelters.json` 並在 `docs/` 建立首頁與所有設施頁面。
3. 將 GitHub Pages 指向 `docs/` 目錄即可發布。

### 發布後的瀏覽

- 首頁：`/index.html`，提供搜尋、篩選與列表。
- 個別頁面：`/facilities/<編號-里別-名稱>/`，包含容量、地址、轄管分局及 Google Maps 導覽連結。
