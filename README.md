# 👑 公主連結 Re:Dive 劇情地圖 (PCRD Story Map)

[![GitHub License](https://img.shields.io/github/license/SmallOrange0323/PCRD_transtool?style=flat-square&color=blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat-square)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Active%20Production-success?style=flat-square)]()

本專案的核心產品為 **「公主連結劇情地圖（PCRD Story Map）」** —— 一個高沉浸感、全話數涵蓋、支援官方繁體中文全對白檢索、專屬 CG 劇照、場景背景與語音播放的 Web 應用系統。

專案具備 **Story Map Update Pipeline v1**，提供從 So-net CDN 進行資料庫版號探測、SQLite 資料庫更新、追蹤角色好感度劇本增量補齊、決定性打包與全量深度驗證的標準化流程。

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

## 🔄 資料更新管線 (Pipeline v1)

當遊戲有新版本或新角色好感度劇本上線時，可透過單一指令執行管線：

```bash
# 本地增量同步 ➡️ 決定性打包 ➡️ 全量驗證門禁 (預設不發布)
python update_story_map.py
```

### Pipeline v1 支援範疇
* ✅ **CDN TruthVersion 探測與狀態持久化**：自動比對線上與本地版本。
* ✅ **台版 SQLite 資料庫同步**：自動下載並解密最新 `redive_tw.db`。
* ✅ **追蹤角色劇情增量下載**：自動掃描 `tracked_characters.json` 中尚未就緒的角色好感度話數並下載解密。
* ✅ **決定性前端封裝 (Deterministic Bundle)**：基於 SHA-256 Content 比對與 Cache-Busting。
* ✅ **全量深度驗證門禁**：逐份 parse 全量 9000+ 篇對白 JSON 與 dist 一致性自檢。
* ✅ **可選 GitHub Pages 部署**：`python update_story_map.py --deploy` 僅推送 `dist_story_map` 至 `gh-pages`。

### 常用管線指令
* **模擬運行 (零副作用)**：
  ```bash
  python update_story_map.py --dry-run
  ```
* **手動執行全量資料一致性自檢**：
  ```bash
  python -m pipeline.validate
  ```
* **手動執行 Story Map 封裝**：
  ```bash
  python -m pipeline.bundle
  ```
* **下載特定話數之語音與 CG 素材 (手動工具)**：
  ```bash
  python -m pipeline.fetch fetch-story-voices --story-id <STORY_ID>
  python -m pipeline.fetch fetch-story-images --story-id <STORY_ID>
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
├── dist_story_map/             # 🚀 GitHub Pages 獨立發布目錄 (具備獨立 .git)
├── pipeline/                   # ⭐ Story Map Update Pipeline v1 核心模組
│   ├── fetch.py                # CDN 資源探測與下載解密
│   ├── bundle.py               # 決定性前端打包與 Cache-Busting
│   ├── deploy.py               # 部署發布 (只推送 dist 至 gh-pages)
│   ├── validate.py             # 全量資料一致性自檢門禁
│   └── update.py               # 統一增量更新協調器
├── update_story_map.py         # 🌟 根目錄一鍵更新快捷指令
├── tools/                      # 🛠️ 維護與診斷工具集
├── experiments/                # 🧪 歷史/獨立實驗專案 (如 AI 翻譯器)
├── archive/                    # 📦 歷史特定活動一次性修正腳本
└── docs/                       # 📚 架構指南與資料流規格文檔
```

---

## 🧪 其他實驗性專案 (Experiments)

* **[PC 遊戲即時 AI 翻譯器](experiments/translator/)**：專為日版遊戲設計的 OCR + Gemini Vision 即時懸浮翻譯工具。
