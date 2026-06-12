# PCRD 劇情編年史網頁工具交接清單

本文件記錄了近期針對 `PCRD_tool` 專案中「劇情與角色導航站（story_map）」進行的 UI/UX 優化、性能提升以及 bug 修復項目。

---

## 1. 核心優化項目

### 🎨 介面與視覺體驗（UI/UX）
* **大廳選單卡片文字易讀性**：
  * **問題**：在大廳淺色背景下，選單卡片的標題與描述使用白色文字，幾乎無法看清。
  * **改善**：調整了卡片背景為半透明白色磨砂玻璃感（`rgba(255, 255, 255, 0.6)`），並將標題與描述文字改為深色（`--text-primary` / `--text-secondary`），加入微弱邊框增強層次感。
* **平滑過渡動畫**：
  * 返回大廳、切換不同分頁時，加入了透明度淡入淡出（Fade Transition）動畫，提升頁面切換的流暢度。
  * 話數目錄的摺疊手風琴（Accordion）展開收合加入動態計算 `scrollHeight`，配合 `requestAnimationFrame` 實現平滑 of 展開/收攏效果。

### ⚡ 效能與搜尋體驗
* **搜尋防抖 (Debounce) 機制**：
  * **問題**：原本在「登場角色」分頁中搜尋名字時，每輸入一個字就會完整銷毀並重新生成整個頁面 DOM，導致輸入極度卡頓且輸入框失去焦點。
  * **改善**：加入了 `300ms` 的搜尋防抖。同時重構為局部更新網格（`_updateSpeakerGrid()`），搜尋時只更新角色卡片 grid，不重建整個 Tab，完美保留輸入焦點且極致流暢。

### 🖼️ 資源載入與 Bug 修復
* **劇照縮圖加載修復**：
  * **問題**：話數卡片左側的 16:9 縮圖全為灰色或透明。
  * **原因**：CDN 拼裝路徑不正確（原先全拼裝為 `still/story/...`）。
  * **修復**：修改 [story-asset-service.js](file:///g:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/story-asset-service.js) 中的 `getStillUrls`，精確區分：
    * **9 位數劇情劇照**（大於 `10000000`）➔ 請求 `card/story/{id}.webp`。
    * **6 位數角色卡面** ➔ 請求 `card/full/{id}.webp`。
* **對話氣泡斷句合併**：
  * **問題**：因字幕數據將一句語音切成了多行，網頁版中每個斷句都產生了獨立的氣泡、頭像與播放按鈕。
  * **修復**：在 [map.js](file:///g:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/map.js) 的 `loadDialogue` 加入預處理：當**發言人相同**時，若後續斷句**沒有語音 ID**，或是**語音 ID 與上一句完全相同**，會直接將文字內容以換行合併在同一個氣泡框中展示，旁白的多行碎化斷句也同步予以合併。

### 🔗 導航路由與跳轉
* **跨分頁跳轉路由（`jumpToStory`）**：
  * **修復**：在角色詳情彈窗（Chara Modal）中點擊登場話數時，能正確識別目標故事的類型（主線、活動、角色、公會、露娜塔等），並自動切換到對應的分頁（`activeTabType`）、重新分組並載入對話（`loadDialogue`），最後平滑捲動到目標卡片位置。

---

## 2. 檔案異動清單

* [dashboard/map.js](file:///g:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/map.js)
  * 實作對話載入合併邏輯、局部更新 Grid、搜尋防抖、摺疊動畫與跳轉路由。
* [dashboard/story-asset-service.js](file:///g:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/story-asset-service.js)
  * 修復與重構劇照與卡面的鏡像 CDN 資源網址拼接規則（`getStillUrls`）。
* [dashboard/style.css](file:///g:/OneDrive%20-%20%E5%AF%B0%E5%AE%87%E7%9F%A5%E8%AD%98%E7%A7%91%E6%8A%80%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/PCRD_tool/dashboard/style.css)
  * 大廳選單卡片配色、對白面高度、過渡動畫等樣式調整。
* `dist_story_map/`
  * 已執行 `bundle_story_map.py` 自動將上述修改編譯並部署到發佈目錄中。

---

## 3. 後續待辦/未竟事項

1. **色彩層級優化**：建立金/銀/灰等更精緻的背景或邊框色彩層級。
2. **特殊字元 onclick 修復**：部分角色名字若帶有特殊字元，在觸發 modal 時可能會有轉義問題，後續可進一步用 `addEventListener` 取代行內 `onclick` 進行綁定。
3. **活動話數標題顯示錯誤微調**：有時 sub_title 與 title 的顯示映射需要依據不同章節做客製調整。
