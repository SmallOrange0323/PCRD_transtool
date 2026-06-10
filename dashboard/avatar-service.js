console.log("avatar-service.js loaded");
/**
 * PCRD Data Hub - 統一頭像服務
 * 集中管理角色頭像 URL 生成、降級邏輯、快取與預載
 */

window.AvatarService = {
    // 【修正 Bug 4 & Bug 8】HTML 實體編碼輔助函數
    escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    // 【修正 Bug 8】用於 onerror 處理器中的字串跳脫
    escapeForJsString(str) {
        if (!str) return "";
        return String(str)
            .replace(/\\/g, "\\\\") // 先處理反斜線
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"');
    },
    // CDN 域名優先序（依序嘗試）
    cdnBases: [
        'https://redive.estertion.win/icon/unit/',
        'https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/icon/unit/',
    ],
    localBase: 'icon/unit/',

    // 手動補全：顯示名稱 -> unit_id (取 MIN(unit_id) 且 < 200000)
    customMap: {
        "涅婭": 123311,
        "涅雅": 123311,
        "安涅默涅": 129611,
        "普蕾西亞": 126112,
        "莉莉": 131301,
        "可璃": 131401,
        "可璃亞": 131401,
        "八斗神局長": 193631,
        "八斗金局長": 193631,
        "八斗": 193631,
        "八斗神": 193631,
        "剎鬼‧八斗神": 193631,
        "菲絲雷斯": 193732,
        "菲絲": 193732,
        "媞雅": 193211,
        "格魯尼": 195611,
        "羅蘭": 195211,
        "涅妃‧涅羅": 129711,
    },

    // 快取：charaName -> { unitId, url, triedCdnIndex }
    cache: {},

    // 取得角色 unit_id（優先 customMap，再從外部傳入的 speakerAvatars 查找）
    getUnitId(charaName, externalAvatars = {}) {
        if (!charaName) return null;
        const cleanName = this.cleanName(charaName);
        if (this.customMap[cleanName]) return this.customMap[cleanName];
        if (externalAvatars[cleanName]) return externalAvatars[cleanName];
        if (externalAvatars[charaName]) return externalAvatars[charaName];
        return null;
    },

    // 清理名稱（移除括號限定語、「的聲音」等）
    cleanName(name) {
        if (!name) return "";
        let clean = name.split(/[、＆&]|和|與/)[0].trim();
        clean = clean.replace(/（[^）]+）/g, "").replace(/\([^)]+\)/g, "").trim();
        if (clean.endsWith("的聲音")) clean = clean.replace(/的聲音$/, "");
        return clean;
    },

    // 核心：生成頭像 URL 陣列（依優先序）
    getUrlCandidates(unitId) {
        if (!unitId || unitId < 100000) return [];
        const baseId = Math.floor(unitId / 100) * 100;
        const candidates = [];
        // 1. 本地：base+31 (Live2D/大圖)
        candidates.push(`${this.localBase}${baseId + 31}.webp`);
        // 2. CDN：base+31
        this.cdnBases.forEach(cdn => candidates.push(`${cdn}${baseId + 31}.webp`));
        // 3. 本地：base+11 (SD/小圖)
        candidates.push(`${this.localBase}${baseId + 11}.webp`);
        // 4. CDN：base+11
        this.cdnBases.forEach(cdn => candidates.push(`${cdn}${baseId + 11}.webp`));
        return candidates;
    },

    // 公開 API：取得最佳頭像 img 元素 HTML
    getAvatarHtml(charaName, externalAvatars = {}) {
        const cleanName = this.cleanName(charaName);
        const unitId = this.getUnitId(cleanName, externalAvatars);

        if (!unitId) {
            return this.getFallbackHtml(cleanName);
        }

        const candidates = this.getUrlCandidates(unitId);
        if (candidates.length === 0) {
            return this.getFallbackHtml(cleanName);
        }

        // 建立 onerror 鏈：依序嘗試下一個候選
        let onerrorChain = "";
        for (let i = 0; i < candidates.length - 1; i++) {
            const nextUrl = this.escapeForJsString(candidates[i + 1]); // 【修正 Bug 8】正確跳脫字串
            onerrorChain += `this.onerror=null; this.src='${nextUrl}'; `;
        }
        // 最後失敗：顯示文字佔位符
        const safeName = this.escapeForJsString(cleanName); // 【修正 Bug 8】正確跳脫字串
        onerrorChain += `this.style.display='none'; this.parentNode.innerHTML='<div class=\\'npc-avatar-placeholder\\'>${safeName.substring(0, 2)}</div>';`;

        return `<img src="${candidates[0]}" style="width: 100%; height: 100%; object-fit: cover;" onerror="${onerrorChain}">`;
    },

    // 取得最佳頭像 img 元素 HTML (根據 unit_id)
    // 【修正】無效 ID 兼容：若 unitId 無效，則回退至名稱查找
    getAvatarHtmlByUnitId(unitId, charaName, externalAvatars = {}) {
        const cleanName = this.cleanName(charaName);
        let finalUnitId = unitId;
        if (!finalUnitId || finalUnitId < 100000) {
            finalUnitId = this.getUnitId(cleanName, externalAvatars);
        }

        if (!finalUnitId || finalUnitId < 100000) {
            return this.getFallbackHtml(cleanName);
        }

        const candidates = this.getUrlCandidates(finalUnitId);
        if (candidates.length === 0) {
            return this.getFallbackHtml(cleanName);
        }

        // 建立 onerror 鏈：依序嘗試下一個候選
        let onerrorChain = "";
        for (let i = 0; i < candidates.length - 1; i++) {
            const nextUrl = this.escapeForJsString(candidates[i + 1]);
            onerrorChain += `this.onerror=null; this.src='${nextUrl}'; `;
        }
        // 最後失敗：顯示文字佔位符
        const safeName = this.escapeForJsString(cleanName);
        onerrorChain += `this.style.display='none'; this.parentNode.innerHTML='<div class=\\'npc-avatar-placeholder\\'>${safeName.substring(0, 2)}</div>';`;

        return `<img src="${candidates[0]}" style="width: 100%; height: 100%; object-fit: cover;" onerror="${onerrorChain}">`;
    },

    // 文字佔位符
    getFallbackHtml(charaName) {
        const safeName = this.escapeHtml((charaName || "??").substring(0, 2)); // 【修正 Bug 4】編碼顯示文字
        return `<div class="npc-avatar-placeholder">${safeName}</div>`;
    },

    // 批次預載（可選）
    preload(charaNames, externalAvatars = {}) {
        charaNames.forEach(name => {
            const cleanName = this.cleanName(name);
            const unitId = this.getUnitId(cleanName, externalAvatars);
            if (!unitId) return;
            const candidates = this.getUrlCandidates(unitId);
            candidates.forEach(url => {
                const img = new Image();
                img.src = url;
            });
        });
    },

    // 註冊自定義映射（運行時動態補全）
    registerCustom(charaName, unitId) {
        this.customMap[charaName] = unitId;
    },
};