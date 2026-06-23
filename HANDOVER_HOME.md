# PCRD 劇情與數據導航站 — 晚上回家繼續開發交接文件

這份交接文件旨在讓您晚上回到家、使用家裡電腦接手本專案（`PCRD_tool`）時，能以最快速度同步開發環境，了解今天下午已完成的進度與接下來的待辦事項。

---

> [!WARNING]
> ### ⚠️ 明日待辦事項：主線現實劇情摘要校對與重做
> 目前 `chapters.json` 中所有的 **現實線劇情摘要 (`real_world_summary`)** 均為 AI 離線自動生成，**可能存在名詞或時空幻覺**。
>
> **明日任務**：請到公司後，全域搜尋專案中的 `real_world_summary` 並進行人工校對，或者在公司利用更強的模型重新跑一遍摘要生成。
>
> *注意：前端網頁上的警示標籤已被移除，您可以直接全域搜尋專案 `chapters.json` 的 `real_world_summary` 欄位進行修改。*

---

## 📅 當前最新狀態 (截止至 2026-06-12 16:00)

今天下午，我們完成了以下核心功能與優化：

1. 🎨 **CG 劇情插畫內嵌重構**  
   - **實作內容**：在對話歷史串流中遇到 `item.type === 'still'` 節點時，將其由原本的簡易 `img` 改為調用 `StoryAssetService.getStillHtml`，透過多層 CDN（Estertion 主鏡像、Fallback 鏡像、以及備用 CDN）進行載入。
   - **防破圖降級**：當所有外部 CDN 均載入失敗時，會降級成 `1px` 透明 GIF 並自動隱藏整個插畫容器（`.game-dialogue-still-wrap`），避免頁面上出現破圖圖示。
   - **位置**：[dashboard/map.js](file:///e:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/map.js) 與 [dashboard/style.css](file:///e:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/style.css)。

2. ⚖️ **繁中代理商官方版權聲明 (Footer)**  
   - **實作內容**：在主頁面底部新增了符合正式法規格式的 Footer 聲明：
     > © Cygames, Inc. / © So-net Entertainment Taiwan Limited. All Rights Reserved.  
     > 本站為非官方粉絲工具，所有遊戲素材版權均屬 Cygames 及台灣代理商台灣索尼網路娛樂股份有限公司所有。
   - **位置**：`dashboard/index.html` 以及發佈目錄的 `dist_story_map/index.html`。

3. 🚀 **GitHub Pages 部署與上線**  
   - **成果**：已建立 `.nojekyll` 檔案以相容 SQLite 資料庫（`redive_tw.db`）加載。
   - **已部署網址**：[https://smallorange0323.github.io/PCRD_transtool/](https://smallorange0323.github.io/PCRD_transtool/) (對應 `gh-pages` 分支)。

---

## 🛠️ 家中電腦接手步驟

請在您家裡的電腦上執行以下步驟，即可無縫恢復開發環境：

### 1. 同步代碼與 Git 分支
首先，確保您家裡的 local repo 有拉取最新的變更（由於是在 OneDrive 共用資料夾下，若 OneDrive 已自動同步完成，可直接檢查 git 狀態）：
```bash
# 1. 檢查當前分支狀態
git status

# 2. 如果您在公司有 Push，可以在家裡 Pull 最新代碼
git pull origin main
```

### 2. 啟動本地測試伺服器
專案根目錄下有配置好了的腳本：
- **選項 A (推薦)**：直接執行 `start.bat` (會同時開啟後端服務與監聽工具)。
- **選項 B (手動啟動)**：
  ```bash
  # 在專案根目錄 PCRD_tool/ 下啟動 Python 伺服器
  python -m http.server 8085
  ```
- **測試網址**：
  - 劇情地圖主頁：[http://localhost:8085/dashboard/story_map.html](http://localhost:8085/dashboard/story_map.html)
  - 獨立打包發佈版：[http://localhost:8085/dist_story_map/index.html](http://localhost:8085/dist_story_map/index.html)

### 3. 編譯打包命令
如果您晚上有修改 `dashboard/` 底下的 CSS、JS 或 HTML 檔案，修改完成後，**必須執行編譯打包腳本**來同步更新發佈用的 `dist_story_map/` 資料夾：
```bash
# 執行打包編譯
python dashboard/scripts/bundle_story_map.py
```

---

## 📝 晚上回家後可以繼續處理的事項 (Todo / Backlog)

1. **三級話數列表縮圖卡片化**
   - **構想**：當點選角色或公會進入「話數清單」時，目前的 UI 採用了摺疊手風琴（Accordion）清單。可將其重構為更貼近遊戲風格的圓角長條型大卡片——左側有對應劇照大圖的 16:9 縮圖，右側則是第 X 話和標題，提升視覺精緻度。
   
2. **特殊字元 Modal onclick 修復**
   - **構想**：目前有極少數角色的名字若包含特殊符號，在 `onclick` 行內 JS 觸發角色詳情彈窗時，可能會遇到逸出與轉義問題。後續可考慮將 DOM 生成改為使用 `addEventListener` 的方式進行動態事件綁定，以求徹底防禦。

3. **露娜塔與活動獨立大卡片選單**
   - **構想**：在大廳點擊「額外劇情」分類時，目前是直接呈現清單，可以進一步仿照遊戲實作「露娜塔」與「活動劇情」兩個大卡片入口。

---

> [!NOTE]
> **已完成的變更尚未全數 staging commit**：目前本地還有 `dashboard/index.html`、`dashboard/map.js`、`dashboard/style.css` 等檔案的細微調整尚未 Commit。您可以選擇在公司的電腦直接 Commit 後 Push，或者晚上回家在 OneDrive 同步完成後，在家裡的電腦一起進行 Commit 與部署。
