---
name: pcrd-deploy-website
description: >-
  將公主連結 Re:Dive 劇情地圖（Story Map）最新資料與前端代碼發布到 GitHub Pages。使用時機：使用者已確認更新數據無誤，並明確批准發布時觸發。核心入口唯一為 python update_story_map.py --deploy。
---

# PCRD 網頁部署 Skill

## Overview

將劇情地圖（Story Map）已更新驗證的資料與前端代碼發布至 GitHub Pages（`gh-pages` 分支）。

**核心規則**：
**專案唯一對外部署入口為：**
```bash
python update_story_map.py --deploy
```

**嚴禁代理人直接執行 `python -m pipeline.deploy`**。底層 `pipeline/deploy.py` 屬於內部模組（Internal Only），只能由 `pipeline.update` 在通過完整的前置驗證與門禁後內部授權呼叫。

---

## 核心部署工作流 (Canonical Workflow)

### 1. 使用者明確授權 (User Approval)
發布到線上生產環境具有不可逆之影響。在執行實際部署指令前，**必須取得使用者明確確認**。

```text
# 使用者明確確認範例
「確認資料與驗證無誤，請部署到線上。」
「可以發布了。」
「請執行 deploy 上線。」
```

### 2. 安全預檢 (Safe Preflight)
若尚未在當前確切狀態下通過完整門禁，或需要向使用者呈報發布影響範圍，建議先執行零副作用的乾跑預檢：
```bash
python update_story_map.py --dry-run
```
*功能*：執行完整的管線驗證、CDN 新鮮度比對與構建模擬，不產生檔案寫入或 Git 推送。若當前狀態已剛通過相同門禁，則無須重複執行。

### 3. 正式發布 (Production Deployment)
取得使用者確認後，執行官方標準發布命令：
```bash
python update_story_map.py --deploy
```
可選自訂 Commit 訊息：
```bash
python update_story_map.py --deploy -m "deploy: update story map to version <ver>"
```

---

## 內部部署原語與門禁 (Internal Deployment Primitives)

底層模組 `pipeline/deploy.py` 為專案內部實作，由 `pipeline.update` 依序在完成以下檢驗後受控調用：
1. **官方 CDN 新鮮度評估 (Freshness Evaluation)**：確認當前資料庫與 CDN 版本一致或處於已知基準。
2. **話數覆蓋率檢查 (Story Coverage Checks)**：確保所有必要劇情章節與對白未有缺漏。
3. **正規 Master DB 處理 (Master DB Handling)**：確保資料庫完整解密且雜湊可追蹤。
4. **資源完整性門禁 (Asset Completeness Gate)**：確認頭像、CG 插畫、背景圖等無遺漏。
5. **決定性打包 (Deterministic Bundle)**：將資源與 cache-busting 元數據確定性地同步至 `dist_story_map/`。
6. **全量驗證 (Full Pipeline Validation)**：執行 `pipeline.validate`（包含二進位 Avatar Manifest 對等性等三重驗證）。

**代理人絕對不得繞過上述流程直接調用 `pipeline.deploy`。**

---

## 安全不變式 (Safety Invariants)

發布過程中嚴格禁止以下危險行為：
- ❌ **嚴禁對 `gh-pages` 執行強制推送 (`git push -f`)**。
- ❌ **嚴禁手動刪除 `.git/index.lock`**。
- ❌ **嚴禁手動修改或破壞 `dist_story_map/.git` 內部狀態**。
- ❌ **嚴禁在部署過程中自動對源碼分支執行 `git add`、`git commit` 或 `git push`**。
- ❌ **嚴禁直接推送到 `master` 分支**。
- ❌ **嚴禁跳過任何安全與資料驗證門禁**。
- ❌ **嚴禁使用已廢棄的舊部署腳本（如 `tools/pcrd_deploy.py`、`tools/force_deploy.py`）**。

---

## 源碼倉庫與部署目錄分離原則 (Source vs Deployment Separation)

- **`PCRD_transtool` 主倉庫（`main` 分支）**：專注保存源碼、管線代碼、資料定義與歷史演進。主分支之提交與推送必須由工程師或代理人手動獨立審查完成。
- **`dist_story_map` 部署目錄（獨立 `gh-pages` 分支）**：純粹為 GitHub Pages 提供線上靜態網頁與資源產物。

**部署管線只會將打包驗證後的產物推送到 `origin/gh-pages`，絕不會也不得自動提交或推送主倉庫源碼。**

---

## 新鮮度覆寫機制 (Freshness Override)

參數 `--allow-unconfirmed-freshness` 屬於**緊急/手動覆寫開關**：
- **禁止自動套用**。
- **使用條件**：
  1. 發布被阻擋的**唯一原因**為 CDN 新鮮度未確認（Freshness uncertainty）。
  2. 經工程審查確認本地資料無誤，且經**使用者明確授權**。
- **限制**：該開關**無法**也不得覆寫話數結構覆蓋率不足或 `pipeline.validate` 失敗等硬性門禁。

---

## 門禁失敗處置原則 (Gate Failure Behavior)

若任何部署門禁（CDN 新鮮度、話數覆蓋率、資源完整性、靜態驗證等）失敗：
1. **立即停止 (STOP)**。
2. **呈報詳細診斷**：
   - 失敗之具體門禁名稱與原因。
   - 當前新鮮度狀態（Freshness State）。
   - 驗證錯誤摘要（Validation Result）。
   - 明確說明**尚未執行任何 Git 推送**。
3. **嚴禁嘗試任何 fallback 備用腳本或 force-push**。

---

## 部署後監控說明 (Monitoring)

- 當官方權威指令 `python update_story_map.py --deploy` 執行成功，即代表已通過所有門禁並成功將驗證產物推送至 `origin/gh-pages`。
- GitHub Pages CDN 或用戶端瀏覽器可能存在快取延遲（數十秒至數分鐘不等）。
- **嚴禁**僅因瀏覽器暫時顯示快取舊內容而採取任何具破壞性的重試或 force-push 操作；應提示使用者使用 Ctrl+F5 或無痕視窗檢查。
