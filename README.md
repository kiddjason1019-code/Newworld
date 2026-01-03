# Newworld

## 新市區防空避難設施 GitHub Pages

這個 repo 會直接將 `docs/` 目錄部署到 GitHub Pages，並為新市區的每個防空避難設施提供獨立的介紹頁面（共 41 筆）。首頁支援名稱、地址、里別與轄管分局的快速篩選，並可點擊前往個別頁面查看詳細資訊與地圖連結。

### 如何重新產生網站

1. 確保根目錄的 PDF 檔案 `新市區-1130702.pdf` 存在。
2. 執行：
   ```bash
   python scripts/generate_site.py
   ```
   會解析 PDF、輸出 `docs/data/facilities.json`，並重建首頁與 41 個獨立設施頁。
3. 將 `docs/` 設定為 GitHub Pages 的發佈來源即可直接上線。
