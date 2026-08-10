---
name: pcrd-monitor-cdn-update
description: >-
  監控台服 So-net CDN 是否有新版本上線（TruthVersion 遞增）或靜默更新（DB Hash 變更），自動下載新版資料庫並與舊版 Diff 找出新角色，同時探測素材是否已預上架。使用時機：每次遊戲例行維護後、或懷疑有新角色悄悄實裝時。
---

# PCRD So-net CDN 版本監控 Skill

## Overview

台服每次維護會更新 TruthVersion 版本號（8位數字，如 `00500030`），或在相同版本號下靜默更新資料庫（DB Hash 變更）。本 Skill 自動探測版本遞增、下載並解密新版 DB、與舊版 Diff 找出新角色，並可選擇性地探測美術素材是否預上架。

**此 Skill 是純探測工具，不修改任何現有資料。** 確認有新內容後，再分別呼叫 `pcrd-fetch-new-data` 進行完整資料同步。

## Dependencies

- Python `UnityPy` 套件（用於解密 AssetBundle 形式的資料庫）
- 本地版本歷史記錄：`dashboard/versions/version_history.json`

## Quick Start

```
# 手動觸發版本監控（維護後確認）
「幫我掃一下台服有沒有更新」
「So-net 今天維護了，看看有沒有新版本」
「檢查 CDN 有沒有新角色」

# 快速 HEAD 探測（不解密 DB）
「用 scan-cdn 掃一下有沒有新素材」
python tools/pcrd_fetch.py scan-cdn --output tools/scan_cdn_report.md
```

---

## Utility Scripts

### Script A：monitor_sonet_update.py - 完整版本監控

```bash
# 正常執行（若版本與 DB Hash 均未變，會立即退出）
python tools/monitor_sonet_update.py

# 強制執行（跳過版本相同的早退邏輯）
python tools/monitor_sonet_update.py --force
```

**執行流程**：
1. 讀取 `dashboard/versions/version_history.json` 中的 `last_version` 與 `last_db_hash`
2. 從 So-net CDN 探測 TruthVersion（從上一次版本號往後試探最多 15 個）
3. 從 `masterdata2_assetmanifest` 取得 DB bundle 的 Hash
4. 若版本號或 Hash 與上次不同：
   - 備份舊版 `redive_tw.db` → 下載加密 bundle → UnityPy 解密 → 覆寫 `dashboard/redive_tw.db`
   - Diff 新舊 DB 的角色 ID 集合，輸出新增角色清單
   - 對每個新角色，自動試探並下載 `unit_icon_{id}.webp`、`card_full_{id+30}.webp` 等素材到 `dashboard/versions/{date}_{version}/`
5. 更新版本歷史記錄與 `dashboard/versions/update_log.md`

**輸出**：
- `dashboard/versions/update_log.md`：人類可讀的更新日誌
- `dashboard/versions/version_history.json`：版本歷史記錄（版本號 + DB Hash）
- `dashboard/versions/{date}_{version}/`：本次下載的新角色素材暫存目錄

### Script B：pcrd_fetch.py scan-cdn - 輕量 HEAD 探測

```bash
# 從目前已知最大 unit_id 自動推算候選 ID
python tools/pcrd_fetch.py scan-cdn --output tools/scan_cdn_report.md

# 指定要探測的 ID（有特定情報時）
python tools/pcrd_fetch.py scan-cdn --probe-ids 138401,138501 --output tools/scan_cdn_report.md
```

**特點**：不下載也不解密，僅用 HTTP HEAD 確認 `unit_icon_{id}.webp` URL 是否回應 200。速度很快，適合維護視窗剛開啟時快速確認。

---

## CDN URL 結構（備查）

```
# 版本資訊探測
https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest

# Pool（所有 AssetBundle 加密文件的統一儲存池，以 Hash 前兩位為子目錄）
https://img-pc.so-net.tw/dl/pool/AssetBundles/{hash[:2]}/{hash}

# 角色頭像（直接明文 WebP，不需解密）
https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Unit/Icon/unit_icon_{unitId}.webp

# 角色立繪（直接明文 WebP，不需解密）
https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Card/Full/card_full_{unitId}.webp
```

---

## Workflow

### 標準維護後確認流程

1. 執行完整監控腳本，確認版本是否更新：
   ```bash
   python tools/monitor_sonet_update.py
   ```
2. **【Step 1.5: 更新歷史紀錄與產生 TODO 參數清單】**：
   若確認有新版本，**第一步必須手動或自動更新 `docs/pcrd_version_update_history.md`**：
   - 使用還原後的明文 DB 查詢新增角色，只將 Rarity >= 3 的實裝角色寫入「一、更新角色」。
   - 查詢最新主線章節、新活動（含 5000+ 常規活動與 102xx 新型態活動，並從 `seven_schedule` 查詢對應月份），寫入「三、主線劇情」與「四、活動劇情前瞻」。
   - 此更新歷史文檔將作為後續所有下載/同步指令的「唯一參數依據」。
3. 查看輸出，確認是否有新角色（Diff 結果）：
   - 有新角色/新劇情 → 依據 `docs/pcrd_version_update_history.md` 中的 Unit ID 與 Story ID，引導執行 `pcrd-fetch-new-data`
   - 只有 DB Hash 變更但無新角色/劇情 → 可能是純數值或關卡更新，執行 `update-db` 即可
   - 完全無變化 → 本次維護無資料更新，無需後續操作
4. 若監控腳本已下載角色素材到暫存目錄，確認素材後複製到 `dashboard/icon/unit/` 與 `dashboard/card/full/`。


---

## Common Mistakes

1. **版本號未更新但實際有更新**：So-net 偶爾在同一版本號下靜默更新 DB，此時 `monitor_sonet_update.py` 的 DB Hash 比對機制會偵測到。若只用 `scan-cdn` 的版本號探測則會漏掉。
2. **暫存素材未複製到工作目錄**：`download_assets_for_chara` 函數將素材下載到 `dashboard/versions/{date}_{version}/` 暫存目錄，而非直接放入 `dashboard/icon/unit/`，需要手動複製或由 AI 執行搬移。
3. **強制執行時每次都重下 DB**：`--force` 選項會繞過版本相同的早退邏輯，重複執行時會每次都重新下載並覆寫 `redive_tw.db`，在版本穩定期間沒有意義。
