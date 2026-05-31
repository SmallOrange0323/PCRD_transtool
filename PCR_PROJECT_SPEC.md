# PCR 台版數據導航站 - Project Spec

## 1. 專案願景
為《公主連結 Re:Dive》台服玩家提供一個美觀、即時且零門檻的數據查詢平台。使用者無需安裝 APP，即可透過瀏覽器掌握最新遊戲動態與角色資訊。

## 2. 技術棧 (Tech Stack)
*   **前端**：HTML5, CSS3 (Vanilla), JavaScript (ES6+)
*   **美學風格**：Dark Mode, Glassmorphism (玻璃擬態), CSS Animations
*   **數據獲取**：Fetch API (非同步請求)
*   **第三方來源**：
    *   **API 主機**：`https://wthee.xyz/pcr/api/v1/`
    *   **數據庫存儲**：`http://wthee.xyz/db/`
    *   **角色圖片鏡像**：`https://redive.estertion.win/icon/unit/`

## 3. 核心功能模組 (Feature Modules)
*   **Monitor**: 即時追蹤數據庫 Truth Version 與更新時間。
*   **Gallery**: 角色圖鑑列表，顯示評分與基本屬性。
*   **News**: 官方公告整合列表。
*   **Arena**: 競技場對戰策略查詢介面。

## 4. 數據規範
*   **Region Code**: `3` (台版)
*   **Region String**: `"tw"`

## 5. 開發護欄
*   嚴禁使用未經授權的第三方框架。
*   所有 API 請求需考慮 CORS 限制，並提供 Mock Data 降級方案。
*   UI 必須符合高級美學準則，不得使用預設樣式。
