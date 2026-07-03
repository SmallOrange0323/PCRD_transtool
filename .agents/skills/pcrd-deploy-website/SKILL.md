---
name: pcrd-deploy-website
description: >-
  將公主連結 Re:Dive 台版工具網站的最新角色資料與前端代碼打包，推送到 GitHub Pages 並監控部署狀態。使用時機：使用者已確認 pcrd-fetch-new-data 的資料報告無誤，需要將新角色或新劇情發佈到線上網頁時觸發。執行前必須先取得使用者明確確認。
---

# PCRD 網頁部署 Skill

## Overview

將 `dashboard/` 目錄下已更新的資料與前端代碼，自動注入新角色定義、打包到 `dist_story_map/`，並強制推送到 GitHub Pages `gh-pages` 分支，最後監控線上部署狀態。

**此 Skill 是 `pcrd-fetch-new-data` 的下游流程，必須在使用者確認資料報告無誤後才可執行。**

## Dependencies

無外部 Skill 依賴。

## Quick Start

```
# 使用者確認資料後觸發
「資料確認沒問題，幫我更新到網站上」
「把剛才抓的新劇情部署到 GitHub Pages」
「上線！」
```

## Utility Scripts

使用 `tools/pcrd_deploy.py` CLI 工具：

### `inject-character` — 注入新角色到前端

```bash
python tools/pcrd_deploy.py inject-character --unit-id 138301 --name "貪吃佩可（阿斯特萊亞）" --output tools/inject_report.json
```

在 `dashboard/characters.js` 中尋找注入點，插入新角色的 JS 物件定義（ID、名稱、故事 ID 清單）。若角色已存在則跳過（冪等操作）。

### `bundle` — 打包靜態資源

```bash
python tools/pcrd_deploy.py bundle --output tools/bundle_report.json
```

執行 `dashboard/scripts/bundle_story_map.py`，根據 `dashboard/data/tracked_characters.json` 複製所有已追蹤角色的素材到 `dist_story_map/`。

### `push-pages` — 推送到 GitHub Pages

```bash
python tools/pcrd_deploy.py push-pages --message "deploy: add new character" --output tools/push_report.json
```

在 `dist_story_map/` 執行 Git 操作（清除 index.lock → reset → add -A → commit → push -f origin gh-pages），並同步將前端源碼 push 到 master 分支。

### `monitor` — 監控部署狀態

```bash
python tools/pcrd_deploy.py monitor --timeout 300 --output tools/monitor_report.json
```

輪詢 GitHub REST API，確認 `gh-pages` 分支最新 commit 已被 GitHub Pages CDN 正式上線，超時則通知使用者手動刷新。

## Workflow

### 完整部署新角色的標準流程

1. **AI 再次確認** → 向使用者說明即將執行的操作（注入哪個角色、推送到哪個 Repo），取得確認
2. **執行** `inject-character --unit-id {id}` → 注入前端 JS 定義
3. **執行** `bundle` → 打包所有靜態資源
4. **執行** `push-pages` → 清除鎖定、提交、強制推送
5. **執行** `monitor` → 監控 CDN 上線狀態
6. **呈報結果** → 告知使用者部署成功，提示以 Ctrl+F5 強制刷新瀏覽器

## Rate Limiting

- **GitHub API**：未認證請求限速 60 次/小時，monitor 每 10 秒一次，不會超出限制

## Common Mistakes

1. **index.lock 殘留**：前次中斷的 Git 進程會留下鎖定檔，`push-pages` 已自動處理，但若仍失敗請手動確認 `dist_story_map/.git/` 下無 lock 檔。
2. **音訊目錄被誤追蹤**：`dist_story_map/.gitignore` 已設定忽略 `sound/`，若音訊誤入 staging 會導致 `git add` 卡死數分鐘，需執行 `git rm -r --cached sound` 解除追蹤。
3. **瀏覽器強快取**：GitHub Pages 成功部署後，使用者仍需按 Ctrl+F5 強制刷新才能看到最新版，純刷新 F5 可能仍顯示舊版。
