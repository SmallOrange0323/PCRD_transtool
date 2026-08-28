# 👑 公主連結 Re:Dive 劇情地圖 (PCRD Story Map)

[![GitHub License](https://img.shields.io/github/license/SmallOrange0323/PCRD_transtool?style=flat-square&color=blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat-square)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Active%20Production-success?style=flat-square)]()

本專案的核心產品為 **「公主連結劇情地圖（PCRD Story Map）」** —— 一個高沉浸感、全話數涵蓋、支援官方繁體中文全對白檢索、專屬 CG 劇照、場景背景與語音播放的 Web 應用系統。

專案包含完整的 **CDN ➡️ Story Map 自動化資料管線**，可定期同步台服 So-net 遊戲 CDN，自動下載並解密最新主線章節、活動劇情、角色好感度劇本與多媒體素材。

---

## 🌟 核心功能：公主連結劇情地圖 (Story Map)

* **📖 全量劇本收錄**：已收錄超過 **9,000+ 篇** 官方繁體中文對白 JSON（包含第一部至第三部主線、角色個人好感度、公會與歷年活動劇情）。
* **🎨 高畫質美術與 CG**：完整整合章節專屬 CG 劇照、場景背景與角色立繪。
* **🔊 實體語音支援**：支援官方 `.m4a` 劇情音檔串流與本地播放。
* **⚡ 輕量純前端架構**：採用 HTML5 / Vanilla JS / SQLite WebAssembly（WASM）技術，支援秒級全劇本關鍵字搜尋與人物登場統計。

---

## 🚀 快速開始

### 1. 本地啟動劇情地圖
```bash
# 啟動本地伺服器 (包含 WASM / MIME 支援)
python tools/local_server.py
```
啟動後在瀏覽器中開啟：👉 **`http://localhost:8000/`**

---

## 🔄 資料更新管線 (Pipeline)

當遊戲有新版本或新劇情上線時，可透過單一指令完成全自動更新：

```bash
# 一鍵全自動更新：探測 CDN ➡️ 下載解密 ➡️ 封裝 ➡️ 驗證 ➡️ 發布
python update_story_map.py
```

### 常用管線指令
* **僅檢查更新 / 模擬運行 (Dry-run)**：
  ```bash
  python update_story_map.py --dry-run
  ```
* **下載指定活動/主線之語音與 CG 素材**：
  ```bash
  python -m pipeline.fetch fetch-story-voices --story-id <STORY_ID>
  python -m pipeline.fetch fetch-story-images --story-id <STORY_ID>
  ```
* **手動執行 Story Map 封裝與 Cache-Busting**：
  ```bash
  python -m pipeline.bundle
  ```
* **手動執行全量資料一致性自檢**：
  ```bash
  python -m pipeline.validate
  ```

---

## 📁 專案架構概覽

```text
PCRD_transtool/
├── dashboard/                  # ⭐ Story Map 前端原始碼與本地開發目錄
│   ├── story_map.html          # 主介面
│   ├── map.js, characters.js   # 業務邏輯控制器
│   ├── data/                   # 章節與活動元數據 JSON
│   └── story/                  # 官方解密對白 JSON (9000+ 篇)
├── dist_story_map/             # 🚀 GitHub Pages 獨立發布目錄
├── pipeline/                   # ⭐ CDN ➡️ Story Map 資料管線模組
│   ├── fetch.py                # CDN 資源探測與下載解密
│   ├── bundle.py               # 前端打包、內嵌與 Cache-Busting
│   ├── deploy.py               # 部署與 GitHub Pages 推送
│   ├── validate.py             # 資料完整性與三道綠燈自檢
│   └── update.py               # 單一更新協調器
├── update_story_map.py         # 🌟 根目錄一鍵更新快捷指令
├── tools/                      # 🛠️ 維護與診斷工具集
├── experiments/                # 🧪 歷史/獨立實驗專案 (如 AI 翻譯器)
├── archive/                    # 📦 歷史特定活動一次性修正腳本
└── docs/                       # 📚 架構指南與資料流規格文檔
```

---

## 🧪 其他實驗性專案 (Experiments)

* **[PC 遊戲即時 AI 翻譯器](experiments/translator/)**：專為日版遊戲設計的 OCR + Gemini Vision 即時懸浮翻譯工具。
