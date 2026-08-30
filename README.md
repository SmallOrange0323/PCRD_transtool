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
├── dist_story_map/             # 🚀 GitHub Pages 獨立發布目錄 (由 pipeline 生成，請勿手動修改)
├── pipeline/                   # ⭐ Story Map Update Pipeline v1 核心模組
│   ├── fetch.py                # CDN 資源探測與下載解密
│   ├── bundle.py               # 決定性前端打包與 Cache-Busting
│   ├── deploy.py               # 正式部署發布 (只推送 dist 至 gh-pages)
│   ├── validate.py             # 全量資料一致性自檢門禁
│   └── update.py               # 統一增量更新協調器
├── update_story_map.py         # 🌟 官方標準一鍵更新入口
├── tools/                      # 🛠️ 核心底層工具與相容性工具 (pcrd_fetch.py, pcrd_deploy.py, local_server.py 等)
│   ├── diagnostics/            # 🔍 診斷、探查與唯讀分析工具 (如 scan_highest_sonet_version.py 等)
│   └── maintenance/            # 🔧 高影響、人工啟動之批次維護工具 (如 download_stories_tw.py, download_voices_tw.py)
├── archive/                    # 📦 歷史封存目錄
│   └── legacy_scripts/         # 歷史一次性修正腳本 (具副作用或過期入口已設置 Hard Stop 防護)
├── docs/                       # 📚 世界觀規範、版本記錄、專案文件與歷史盤點
├── .agents/                    # 🤖 AI Agent 協作指南與長期記憶
├── translator/                 # 🧪 獨立實驗專案：PC 遊戲即時 AI 翻譯器
├── pcr_demo/                   # 🧪 早期展示 Demo (Legacy)
└── pcrd_sim/                   # 🧪 早期戰鬥模擬實驗 (Legacy)
```

### 🛠️ 工具層級說明 (Tools Taxonomy)
* **`tools/` (根層工具)**：核心底層引擎（如 `pcrd_fetch.py`）與舊版相容工具（如 `pcrd_deploy.py`）。正式管線發布請統一使用 `python update_story_map.py --deploy`。
* **`tools/diagnostics/`**：唯讀診斷與分析工具。提供資料表結構分析、CDN 版本探測與素材比對（註：部分工具如 `find_db_files.py` 刻意自執行當前目錄 `os.walk('.')` 開始動態尋找）。
* **`tools/maintenance/`**：人工手動觸發的批次維護與全量恢復工具。日常例行更新仍請使用標準入口 `python update_story_map.py`。
* **`archive/legacy_scripts/`**：歷史修復與過期腳本保存庫。具副作用或已廢棄之入口已配置 Execution Guard (Hard Stop)；歷史唯讀腳本則安全封存作為歷史追溯。

---

## 🧪 獨立與歷史實驗專案 (Side Projects)

* **[PC 遊戲即時 AI 翻譯器](translator/)**：專為日版遊戲設計的 OCR + Gemini Vision 即時懸浮翻譯工具。
* **早期探索專案**：`pcr_demo/`、`pcrd_sim/`（戰鬥模擬與初期原型探索，已停止維護）。

