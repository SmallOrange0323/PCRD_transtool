# PCRD Data Hub - 專案交接文件

**最後更新**：2026-06-09
**提交基準**：`c9b6913` (Phase 1 pre-backup) + 後續修正

---

## 專案概況

修正 `chapters.json` 結構與 Part 3 主線/幕間劇情分類錯誤，重建正確的章節對應關係。

### 核心問題
- 原 `chapters.json` 結構扁平、Part 3 群組 ID 錯誤（3001-3015 實為公會幕間，非主線）
- 主線 Part 3 (2201-2215) 完全遺失
- 摘要內容為模型幻覺，非真實劇情
- Part 3 顯示邏輯混雜主線與公會劇情

---

## 變更摘要

### Phase 1：重建 chapters.json ✅
**檔案**：`dashboard/scripts/rebuild_chapters.py` → `dashboard/data/chapters.json`

| 部分 | 群組 ID 範圍 | 結構 | 筆數 | 備註 |
|------|-------------|------|------|------|
| Part 1 | 2000-2015 | `1.game_world` | 16 | 序章 + 第 1-15 章 |
| Part 2 | 2101-2116 | `2.game_world` | 16 | 第 1-16 章 |
| Part 3 主線 | 2201-2215 | `3.game_world` | 15 | 第 1-15 章，含手寫摘要 |
| Part 3 幕間 | 3001-3017, 3022, 4001-4013 | `3.interlude` | 28 | 暫無摘要，待後續生成 |

**關鍵修正**：
- 巢狀結構：`{ "1": { "game_world": {...} }, "3": { "game_world": {...}, "interlude": {...} } }`
- UTF-8 編碼（原 Big5 讀成 UTF-8 導致亂碼）
- Part 2 對應：舊 2007-2022 → 新 2101-2116 依序對應

---

### Phase 2：chapter-data.js 重構 ✅
**檔案**：`dashboard/chapter-data.js`

| 方法 | 變更內容 |
|------|----------|
| `getChapterInfo` | Part 3 支援 `game_world` / `interlude` 巢狀查找 |
| `getAllChapters` | Part 3 合併兩子物件並依 `order` 排序 |
| `getPartFromGroupId` | 精確區間：2000-2015→1, 2101-2116→2, **2201-2215→3**, 3000+→3 |
| `getChapterKey` | Part 3 回退邏輯：2201-2215→第N章, 3001-3022→幕間N, 4000+→幕間N |

---

### Phase 3：map.js 修正 ✅
**檔案**：`dashboard/map.js`

| 位置 | 變更 |
|------|------|
| L138 | SQL 範圍：`story_id < 3000000` → `< 5000000`（納入 Part 3 幕間） |
| L327 | 移除死代碼 `partTitles` |
| L325-330 | 移除錯誤的 Part 3 「🏙️ 現實世界篇 / 🎮 遊戲世界」標籤邏輯 |
| L194-197 | **新增**：Part 3 主線分頁隱藏 `group_id >= 3000` 幕間劇情 |

---

### Phase 4：download_stories_tw.py 擴充 ✅
**檔案**：`download_stories_tw.py`

| 行號 | 變更 |
|------|------|
| L346 | 主線抓取 SQL：`story_id < 3000000` → `< 5000000` |
| L345 | 註解更新：「第一部～第三部主線與所有幕間 ID (2000000 ~ 4999999)」 |

---

### Phase 5：啟動腳本 ✅
**檔案**：`start.bat` (新增)

```bat
@echo off
chcp 65001 >nul
python -m http.server 8080
```
用途：一鍵啟動 HTTP 伺服器繞過 CORS。

---

## 資料結構對照

### chapters.json 結構
```json
{
  "1": { "game_world": { "2000": {...}, "2001": {...}, ... } },
  "2": { "game_world": { "2101": {...}, "2102": {...}, ... } },
  "3": {
    "game_world": { "2201": {...}, ..., "2215": {...} },
    "interlude": { "3001": {...}, ..., "4013": {...} }
  }
}
```

### 群組 ID ↔ 部別對照表
| 群組 ID | 部別 | 類型 | 說明 |
|---------|------|------|------|
| 2000-2015 | 1 | 主線 | 序章 + 15 章 |
| 2101-2116 | 2 | 主線 | 16 章 |
| **2201-2215** | **3** | **主線** | **15 章（新增）** |
| 3001-3022 | 3 | 幕間 | 公會劇情 |
| 4001-4013 | 3 | 幕間 | 系統/特殊劇情 |

---

## 已知限制 / 後續待辦

1. **Part 3 幕間摘要為空** — 需從對話 JSON 生成或手寫
2. **Part 3 幕間顯示** — 目前隱藏於主線分頁，未來需加入子分頁或獨立按鈕切換
3. **group_id 9001-9012** — 存於 `story_id 9000000+`，未納入現有結構（屬未來資料）
4. **4010 特殊故事** — 171 話，歸類於幕間，可能需獨立分類

---

## 驗證指令

```bash
# 1. 啟動伺服器
python -m http.server 8080

# 2. 瀏覽器開啟
# http://localhost:8080/dashboard/

# 3. 切換到「第三部：全新世界篇」
# 應只看到「第 1 章」~「第 15 章」，無「幕間」項目

# 4. 驗證 chapters.json 結構
python -c "import json; d=json.load(open('dashboard/data/chapters.json','r',encoding='utf-8')); print('P1:',len(d['1']['game_world']),'P2:',len(d['2']['game_world']),'P3 GW:',len(d['3']['game_world']),'P3 IL:',len(d['3']['interlude']))"
# 預期輸出: P1: 16 P2: 16 P3 GW: 15 P3 IL: 28
```

---

## 關鍵檔案清單

| 檔案 | 角色 | 狀態 |
|------|------|------|
| `dashboard/data/chapters.json` | 章節中繼資料核心 | ✅ 重建完成 |
| `dashboard/chapter-data.js` | 章節查詢服務 | ✅ 重構完成 |
| `dashboard/map.js` | 主線劇情 UI 模組 | ✅ 修正完成 |
| `download_stories_tw.py` | 對白下載腳本 | ✅ 擴充完成 |
| `dashboard/scripts/rebuild_chapters.py` | chapters.json 產生器 | ✅ 保留供未來更新 |
| `dashboard/redive_tw.db` | 來源資料庫 | 不變 |
| `start.bat` | 快速啟動腳本 | ✅ 新增 |

---

## 回滾參考

```bash
# 回到 Phase 1 前狀態
git reset --hard c9b6913

# 查看本次所有變更
git diff c9b6913 HEAD
```