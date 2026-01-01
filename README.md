# Newworld

這個專案會從「新市區防空疏散避難設施」PDF 轉換出靜態網站（存放在 `docs/` 目錄，可直接用 GitHub Pages 發佈），每個避難設施都會有獨立頁面。

## 如何重新產生網站

1. 安裝 Python 3（不需額外套件）。
2. 重新產出資料與頁面：

```bash
python generate_sites.py
```

腳本會：

- 解碼 `新市區-1130702.pdf`，將避難設施資訊存為 `data/facilities.json`。
- 在 `docs/` 下建立首頁與 41 個設施專頁，方便用 GitHub Pages 托管。
