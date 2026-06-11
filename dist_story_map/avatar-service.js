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
        "莉莉": 125811,
        "可璃": 126011,
        "可璃亞": 126011,
        "八斗神局長": 193631,
        "八斗金局長": 193631,
        "八斗": 193631,
        "八斗神": 193631,
        "剎鬼‧八斗神": 193631,
        "菲絲雷斯": 193732,
        "菲絲": 193732,
        "媞雅": 193211,
        "格魯尼": 194311,
        "羅蘭": 194211,
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
        
        // 1. webp 格式 (優先)
        // 本地：base+31 (Live2D/大圖)
        candidates.push(`${this.localBase}${baseId + 31}.webp`);
        // CDN：base+31
        this.cdnBases.forEach(cdn => candidates.push(`${cdn}${baseId + 31}.webp`));
        // 本地：base+11 (SD/小圖)
        candidates.push(`${this.localBase}${baseId + 11}.webp`);
        // CDN：base+11
        this.cdnBases.forEach(cdn => candidates.push(`${cdn}${baseId + 11}.webp`));

        // 2. png 格式 (降級備用，特別是 NPC 資源)
        // 本地：base+31 (Live2D/大圖)
        candidates.push(`${this.localBase}${baseId + 31}.png`);
        // CDN：base+31
        this.cdnBases.forEach(cdn => candidates.push(`${cdn}${baseId + 31}.png`));
        // 本地：base+11 (SD/小圖)
        candidates.push(`${this.localBase}${baseId + 11}.png`);
        // CDN：base+11
        this.cdnBases.forEach(cdn => candidates.push(`${cdn}${baseId + 11}.png`));

        return candidates;
    },

    // 公開 API：取得最佳頭像 img 元素 HTML
    getAvatarHtml(charaName, externalAvatars = {}) {
        const cleanName = this.cleanName(charaName);
        const unitId = this.getUnitId(cleanName, externalAvatars);

        if (!unitId || unitId < 100000) {
            return this.getFallbackHtml(cleanName);
        }

        const baseId = Math.floor(unitId / 100) * 100;
        const mainId = (unitId < 190000) ? (baseId + 31) : unitId;
        // 優先使用本地端的 .png 圖片
        const src = `icon/unit/${mainId}.png`;
        const safeName = this.escapeForJsString(cleanName);

        return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleError(this, '${safeName}', ${baseId}, ${unitId})">`;
    },

    // 取得最佳頭像 img 元素 HTML (根據 unit_id)
    getAvatarHtmlByUnitId(unitId, charaName, externalAvatars = {}) {
        const cleanName = this.cleanName(charaName);
        let finalUnitId = unitId;
        if (!finalUnitId || finalUnitId < 100000) {
            finalUnitId = this.getUnitId(cleanName, externalAvatars);
        }

        if (!finalUnitId || finalUnitId < 100000) {
            return this.getFallbackHtml(cleanName);
        }

        const baseId = Math.floor(finalUnitId / 100) * 100;
        const mainId = (finalUnitId < 190000) ? (baseId + 31) : finalUnitId;
        // 優先使用本地端的 .png 圖片
        const src = `icon/unit/${mainId}.png`;
        const safeName = this.escapeForJsString(cleanName);

        return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleError(this, '${safeName}', ${baseId}, ${finalUnitId})">`;
    },

    // 靜態錯誤處理函式，用於逐步降級載入圖片或顯示文字佔位符
    handleError(img, safeName, baseId, finalUnitId) {
        if (!img.dataset.step) {
            img.dataset.step = "1";
        }
        const step = parseInt(img.dataset.step);
        const mainId = (finalUnitId < 190000) ? (baseId + 31) : finalUnitId;

        if (step === 1) {
            img.dataset.step = "2";
            // 第一步：如果本地 png 失敗，嘗試 So-net 00500012 的 .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/icon/unit/${mainId}.png`;
            return;
        }
        if (step === 2) {
            img.dataset.step = "3";
            // 第二步：如果 So-net 00500012 失敗，嘗試 So-net 00500015 的 .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500015/Jpn/AssetBundles/Android/icon/unit/${mainId}.png`;
            return;
        }
        if (step === 3) {
            img.dataset.step = "4";
            // 第三步：如果 So-net 皆失敗，嘗試 EsterTion 的 .webp (EsterTion 頭像最齊全的格式)
            img.src = `https://redive.estertion.win/icon/unit/${mainId}.webp`;
            return;
        }
        // 最後失敗：隱藏圖片並顯示文字佔位符
        img.style.display = 'none';
        if (img.parentNode) {
            img.parentNode.innerHTML = `<div class="npc-avatar-placeholder">${safeName.substring(0, 2)}</div>`;
        }
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

    // 取得技能圖示 HTML
    getSkillIconHtml(iconType) {
        if (!iconType) {
            return `<img src="https://redive.estertion.win/icon/unit/000000.png" style="width: 100%; height: 100%; object-fit: cover;">`;
        }
        // 優先使用本地端的 .png 圖片
        const src = `icon/skill/${iconType}.png`;
        return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleSkillError(this, ${iconType})">`;
    },

    // 技能圖示錯誤處理
    handleSkillError(img, iconType) {
        if (!img.dataset.step) {
            img.dataset.step = "1";
        }
        const step = parseInt(img.dataset.step);

        if (step === 1) {
            img.dataset.step = "2";
            // 第一步：如果本地 png 失敗，嘗試 So-net 00500012 的 .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/icon/skill/${iconType}.png`;
            return;
        }
        if (step === 2) {
            img.dataset.step = "3";
            // 第二步：如果 So-net 00500012 失敗，嘗試 So-net 00500015 的 .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500015/Jpn/AssetBundles/Android/icon/skill/${iconType}.png`;
            return;
        }
        if (step === 3) {
            img.dataset.step = "4";
            // 第三步：如果 So-net 都失敗，嘗試 EsterTion 的 .webp
            img.src = `https://redive.estertion.win/icon/skill/${iconType}.webp`;
            return;
        }
        if (step === 4) {
            img.dataset.step = "5";
            // 第四步：嘗試 EsterTion 的 .png
            img.src = `https://redive.estertion.win/icon/skill/${iconType}.png`;
            return;
        }
        // 最後失敗：顯示 000000 佔位符
        img.src = 'https://redive.estertion.win/icon/unit/000000.png';
    }
};