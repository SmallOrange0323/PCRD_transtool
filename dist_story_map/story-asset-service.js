console.log("story-asset-service.js loaded");
/**
 * PCRD Data Hub - 劇情背景與 CG 資源服務
 * 集中管理劇情背景 (Background) 與 CG 插畫 (Still) URL 的生成、降級邏輯與 HTML 封裝
 */

window.StoryAssetService = {
    // So-net CDN 資源前綴路徑 (台版 CDN)
    sonetCdnBases: [
        'https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/',
        'https://img-pc.so-net.tw/dl/Resources/00500015/Jpn/AssetBundles/Android/'
    ],

    // EsterTion 資源前綴路徑 (日版/通用鏡像)
    estertionBase: 'https://redive.estertion.win/',

    // 本地資源前綴路徑
    localBase: '',

    // 預設降級背景 ID (草原)
    defaultBgId: 10000,

    /**
     * HTML 實體編碼輔助函數，避免 XSS
     */
    escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    /**
     * 取得劇情背景的 CDN/本地 URL 候選清單
     * 背景 ID 通常為 5 位數 (例如 10040)
     * @param {number|string} bgId 背景 ID
     * @returns {string[]} URL 候選清單
     */
    getBackgroundUrls(bgId) {
        const id = bgId ? String(bgId).trim() : String(this.defaultBgId);
        const candidates = [];

        // 1. 本地候選路徑 (.webp 與 .png)
        candidates.push(`${this.localBase}bg/story/${id}.webp`);
        candidates.push(`${this.localBase}bg/story/${id}.png`);

        // 2. EsterTion 鏡像 (.webp 與 .png)
        candidates.push(`${this.estertionBase}bg/story/${id}.webp`);
        candidates.push(`${this.estertionBase}bg/story/${id}.png`);

        // 3. So-net CDN 鏡像 (.png)
        this.sonetCdnBases.forEach(cdn => {
            candidates.push(`${cdn}bg/story/${id}.png`);
        });

        // 4. 降級至預設背景 (草原 10000) 的候選清單，避免最終顯示破圖
        if (id !== String(this.defaultBgId)) {
            const defaultCandidates = [
                `${this.localBase}bg/story/${this.defaultBgId}.webp`,
                `${this.localBase}bg/story/${this.defaultBgId}.png`,
                `${this.estertionBase}bg/story/${this.defaultBgId}.webp`,
                `${this.estertionBase}bg/story/${this.defaultBgId}.png`
            ];
            this.sonetCdnBases.forEach(cdn => {
                defaultCandidates.push(`${cdn}bg/story/${this.defaultBgId}.png`);
            });
            candidates.push(...defaultCandidates);
        }

        return candidates;
    },

    /**
     * 取得 CG 插畫的 CDN/本地 URL 候選清單
     * CG ID 通常為 6 位數 (例如 100401)
     * @param {number|string} stillId CG 插畫 ID
     * @returns {string[]} URL 候選清單
     */
    getStillUrls(stillId) {
        const id = stillId ? String(stillId).trim() : "";
        const candidates = [];

        if (id) {
            // 1. 本地候選路徑 (.webp 與 .png)
            candidates.push(`${this.localBase}still/story/${id}.webp`);
            candidates.push(`${this.localBase}still/story/${id}.png`);

            // 2. EsterTion 鏡像 (.webp 與 .png)
            candidates.push(`${this.estertionBase}still/story/${id}.webp`);
            candidates.push(`${this.estertionBase}still/story/${id}.png`);

            // 3. So-net CDN 鏡像 (.png)
            this.sonetCdnBases.forEach(cdn => {
                candidates.push(`${cdn}still/story/${id}.png`);
            });
        }

        // 4. 降級備用：使用透明 1px 圖片佔位符，避免在畫面上留下破圖標誌
        candidates.push('data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7');

        return candidates;
    },

    /**
     * 取得封裝好的背景 HTML <img> 標籤
     * 內建 onerror 逐步降級機制
     * @param {number|string} bgId 背景 ID
     * @param {string} className 額外的 CSS class
     * @param {string} style 額外的行內樣式
     * @returns {string} HTML img 標籤字串
     */
    getBackgroundHtml(bgId, className = "", style = "") {
        const candidates = this.getBackgroundUrls(bgId);
        const firstSrc = candidates[0];
        const remainingCandidates = candidates.slice(1);
        
        // 將剩餘的候選網址序列化並編碼，存入 dataset 中
        const serialized = encodeURIComponent(JSON.stringify(remainingCandidates));
        const safeClass = this.escapeHtml(className);
        const safeStyle = this.escapeHtml(style);

        return `<img class="${safeClass}" style="${safeStyle}" src="${firstSrc}" data-candidates="${serialized}" data-step="0" onerror="StoryAssetService.handleImageError(this)">`;
    },

    /**
     * 取得封裝好的 CG HTML <img> 標籤
     * 內建 onerror 逐步降級機制
     * @param {number|string} stillId CG ID
     * @param {string} className 額外的 CSS class
     * @param {string} style 額外的行內樣式
     * @returns {string} HTML img 標籤字串
     */
    getStillHtml(stillId, className = "", style = "") {
        const candidates = this.getStillUrls(stillId);
        const firstSrc = candidates[0];
        const remainingCandidates = candidates.slice(1);
        
        // 將剩餘的候選網址序列化並編碼，存入 dataset 中
        const serialized = encodeURIComponent(JSON.stringify(remainingCandidates));
        const safeClass = this.escapeHtml(className);
        const safeStyle = this.escapeHtml(style);

        return `<img class="${safeClass}" style="${safeStyle}" src="${firstSrc}" data-candidates="${serialized}" data-step="0" onerror="StoryAssetService.handleImageError(this)">`;
    },

    /**
     * 全域的 onerror 錯誤處理回調函式
     * @param {HTMLImageElement} img 發生錯誤的 img 元素
     */
    handleImageError(img) {
        try {
            const step = parseInt(img.dataset.step || "0");
            const serialized = img.dataset.candidates;
            if (!serialized) {
                // 若無候選 URL，降級至透明占位符
                img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                return;
            }
            const candidates = JSON.parse(decodeURIComponent(serialized));
            if (step < candidates.length) {
                img.dataset.step = step + 1;
                img.src = candidates[step];
            } else {
                // 已試過所有候選 URL，最後降級為透明 1px 圖片
                img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
            }
        } catch (e) {
            console.error('[StoryAssetService] 錯誤處理失效:', e);
            img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
        }
    },

    /**
     * 套用背景圖至指定的 HTML 元素 (用於 CSS background-image 降級機制)
     * 會逐一嘗試載入 URL，直到成功後才套用到 background-image 上
     * @param {HTMLElement} element 要設定背景的 DOM 元素
     * @param {number|string} bgId 背景 ID
     */
    applyBackgroundToElement(element, bgId) {
        if (!element) return;
        const candidates = this.getBackgroundUrls(bgId);
        
        let index = 0;
        const tryLoad = () => {
            if (index >= candidates.length) {
                // 所有圖片皆載入失敗，移除背景圖
                element.style.backgroundImage = 'none';
                return;
            }
            const img = new Image();
            img.onload = () => {
                element.style.backgroundImage = "url('" + candidates[index] + "')";
            };
            img.onerror = () => {
                index++;
                tryLoad();
            };
            img.src = candidates[index];
        };
        tryLoad();
    }
};