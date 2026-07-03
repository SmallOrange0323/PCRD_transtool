---
name: pcrd-fetch-new-data
description: >-
  從台服 So-net CDN 與 wthee 鏡像站下載公主連結 Re:Dive 台版新角色資料，包含解密個人劇情對白 JSON、立繪、頭像美術素材及更新台版明文資料庫，最後輸出驗證報告。使用時機：新角色換裝上線、新主線章節、新活動劇情，需要抓取台版繁體中文原始資料時觸發。
---

# PCRD 台版資料抓取 Skill

## Overview

從台服 So-net CDN 與 wthee 鏡像站下載新角色或新劇情資料，自動解密繁中對白並整理成網頁可直接使用的格式。完成後輸出驗證報告，供使用者確認後再部署網頁。

**此 Skill 只負責「抓資料」，不修改網頁前端代碼。** 確認資料無誤後，請使用 `pcrd-deploy-website` Skill 部署。

## Dependencies

無外部 Skill 依賴。僅需 Python 標準庫 + `UnityPy`（已在工具目錄中使用）。

## Quick Start

```
# 下載新角色資料（以角色名稱告知 AI，由 AI 解析 unit_id）
「幫我抓取阿斯特萊亞佩可的個人劇情和美術」

# 更新資料庫 + 指定 unit_id
「unit_id 138301 的資料需要更新」

# 主線新章節
「主線第三部第五章出了，更新劇情資料」

# 活動劇情
「幫我抓活動 event_id 10096 的劇情」

# 手動探測 CDN 有沒有新東西上架
「幫我探測 So-net CDN 有沒有新素材」
「掃一下 CDN 看有沒有新角色預上架」
```

## Utility Scripts

使用 `tools/pcrd_fetch.py` CLI 工具：

### `update-db` — 更新台版明文資料庫

```bash
python tools/pcrd_fetch.py update-db --output tools/db_update_report.json
```

從 wthee 下載最新 `redive_tw.db`，驗證資料表完整性後輸出報告。

### `fetch-stories` — 下載並解密角色個人劇情

```bash
python tools/pcrd_fetch.py fetch-stories --unit-id 138301 --output tools/story_fetch_report.json
```

自動從 So-net CDN manifest 查找對應 story_id（規則：unit_id × 10 + 1 ~ 4），下載 AssetBundle 並用 UnityPy 解密輸出繁中對白 JSON 到 `dashboard/story/`。

### `fetch-assets` — 下載立繪與頭像

```bash
python tools/pcrd_fetch.py fetch-assets --unit-id 138301 --output tools/asset_fetch_report.json
```

下載頭像（1星/3星）與立繪大圖，儲存至 `dashboard/icon/unit/` 與 `dashboard/card/full/`，同時登錄進 `dashboard/data/tracked_characters.json`。

### `report` — 產出人類可讀驗證報告

```bash
python tools/pcrd_fetch.py report --unit-id 138301 --output tools/fetch_report.md
```

整合 DB 查詢結果、對白句數、素材檔案存在狀況，輸出 Markdown 報告。

### `scan-cdn` — 手動探測 So-net CDN 是否有新內容預上架

```bash
# 自動推算候選 ID（從已知最大 unit_id 往後試探）
python tools/pcrd_fetch.py scan-cdn --output tools/scan_cdn_report.md

# 指定要探測的 ID（你有特定情報時）
python tools/pcrd_fetch.py scan-cdn --probe-ids 138401,138501 --output tools/scan_cdn_report.md
```

**完全不解密資料庫**，僅用 HTTP HEAD request 試探素材 URL 是否回應 200。
偵測到素材時自動下載到 `dashboard/versions/{日期}_{版本號}/`，並輸出偵測報告。

So-net 有時會在維護前數小時預先上傳素材（立繪、頭像），這個指令能第一時間發現。

## Workflow

### 完整抓取新角色的標準流程

1. **AI 查詢資料庫** → 在 `redive_tw.db` 查詢角色名稱對應的 `unit_id`
2. **執行** `update-db` → 更新至最新台版 DB，確認新角色已收錄
3. **執行** `fetch-stories --unit-id {id}` → 下載解密個人劇情 JSON
4. **執行** `fetch-assets --unit-id {id}` → 下載立繪與頭像
5. **執行** `report --unit-id {id}` → 輸出驗證報告，呈報使用者確認
6. **等待使用者確認** → 確認無誤後，引導使用者執行 `pcrd-deploy-website`

## Rate Limiting

- **So-net CDN**：無官方文件，預設每次請求間隔 0.5 秒，timeout 15 秒，最多重試 3 次（指數退避）
- **wthee 鏡像站**：單一大檔下載，timeout 60 秒，無需限速

## Common Mistakes

1. **story_id 推算錯誤**：part_id 有些角色不是從 1 開始，建議先查 DB 的 `chara_story_status` 資料表確認實際話數。
2. **UnityPy 版本衝突**：解密時需設定 `FALLBACK_UNITY_VERSION = '2021.3.20f1'`，否則部分 Bundle 解析失敗。
3. **wthee 更新延遲**：wthee 鏡像有時落後台服 CDN 數小時，若 DB 中尚無新角色，請等待後再試。
