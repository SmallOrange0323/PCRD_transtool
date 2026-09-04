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
        "魏雅": 195211,
        "葛拉比亞": 193511,
        "葛拉菲拉": 193511,
        "澄花": 198211,
        "美穗": 139231,
        "真穗": 139331,
        "艾麗卡": 139431,
        "西住美穗": 139231,
        "西住真穗": 139331,
        "逸見艾麗卡": 139431,
    },

    // 集中定義明確指定之 Exact-Appearance 集合 (不執行普通 +11 normalization)
    exactPortraitIds: new Set([
        107411, 107412, 107431 // 幻境龍后等特殊 NPC/Boss 形態
    ]),

    // 集中定義 Exact-ID 優先並支援 Base+11 備選的特殊角色 (GuP 聯動、138331 專屬 override 等)
    exactFirstWithBaseFallback: new Set([
        138331, // dialogue-view 專屬指定之阿斯特賴亞佩可頭像 override
        139231, // 西住美穗 (GuP 官方發布之 canonical 頭像)
        139331, // 西住真穗 (GuP)
        139431  // 逸見艾麗卡 (GuP)
    ]),

    // 第 3 部分支劇情現實篇章之角色現實專屬頭像 ID 映射表
    realityAvatarMap: {
        "空花": 104532, "遠見空花": 104532, "遠見 空花": 104532,
        "莉瑪": 105231,
        "真陽": 103332, "野戶真陽": 103332, "野戶 真陽": 103332,
        "綾音": 102332, "北條綾音": 102332, "北條 綾音": 102332,
        "美美": 102032, "茜美美": 102032, "茜 美美": 102032,
        "鈴奈": 101632, "美波鈴奈": 101632, "美波 鈴奈": 101632,
        "妮諾": 103031, "妮諾・珠貝爾": 103031,
        "七七香": 101332, "丹野七七香": 101332, "丹野 七七香": 101332,
        "霞": 101431, "小霧": 101431, "霧原霞": 101431, "霧原 霞": 101431,
        "真琴": 104331, "安芸真琴": 104331, "安芸 真琴": 104331,
        "貪吃佩可": 105831, "佩可": 105831, "尤絲蒂亞娜": 105831, "尤絲蒂亞娜‧F‧阿斯特賴亞": 105831,
        "伊緒": 101832, "支倉伊緒": 101832, "支倉 伊緒": 101832,
        "美里": 101533, "愛川美里": 101533, "愛川 美里": 101533,
        "克蕾雅": 118031, "克蕾雅‧波洋希亞": 118031, "神秘女性": 118031,
        "茉莉": 100531, "織原茉莉": 100531, "織原 茉莉": 100531,
        "雪": 100832, "虹村雪": 100832, "虹村 雪": 100832,
        "美冬": 104833, "大泉美冬": 104833, "大泉 美冬": 104833,
        "祈梨": 106631, "一之瀨祈梨": 106631, "一之瀨 祈梨": 106631,
        "秋乃": 103232, "藤堂秋乃": 103232, "藤堂 秋乃": 103232,
        "珠希": 104632, "宮坂珠希": 104632, "宮坂 珠希": 104632,
        "咲戀": 102832, "佐佐木咲戀": 102832, "佐佐木 咲戀": 102832
    },

    // 明確定義的現實專屬頭像 ID 集合 (嚴格優先保留 exact ID)
    exactRealityIds: new Set([
        104532, 105231, 103332, 102332, 102032, 101632,
        103031, 101332, 101431, 104331, 105831, 101832,
        101533, 118031, 100531, 100832, 104833, 106631,
        103232, 104632, 102832
    ]),

    // 快取：charaName -> { unitId, url, triedCdnIndex }
    cache: {},

    // 取得角色 unit_id（優先 customMap，再從外部傳入的 speakerAvatars 查找）
    getUnitId(charaName, externalAvatars = {}, isReality = false) {
        if (!charaName) return null;
        const cleanName = this.cleanName(charaName);
        if (isReality && this.realityAvatarMap[cleanName]) {
            return this.realityAvatarMap[cleanName];
        }
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

    /**
     * 核心 Helper：解析發言人/角色之對話立繪頭像 ID 優先序 (Identity & Tier Resolution)
     * 分離 Identity 解析與 Portrait Tier 決策，集中管理策略集合
     * @param {number|string} unitId 
     * @returns {Array<number>} 候選 ID 陣列 (優先序由前至後)
     */
    resolveDialoguePortraitIds(unitId) {
        if (!unitId || (typeof unitId !== 'number' && typeof unitId !== 'string')) return [];
        const numId = Number(unitId);
        if (!Number.isInteger(numId) || numId < 100000) return [];

        // 1. NPC 角色 (>= 190000)：維持 exact unit ID，不進行 base 規整化
        if (numId >= 190000) {
            return [numId];
        }

        // 2. 已知特殊 NPC / Exact-ID 角色 (如 107411 幻境龍后、107412、107431 等)
        if (this.exactPortraitIds.has(numId)) {
            return [numId];
        }

        // 3. 特殊 Exact-ID 優先角色 (如 138331 佩可 override、139231 美穗、139331 真穗、139431 艾麗卡)
        // 保持既有 canonical/exact mapping 優先，次選 base+11
        if (this.exactFirstWithBaseFallback.has(numId)) {
            const baseId = Math.floor(numId / 100) * 100;
            return [numId, baseId + 11];
        }

        // 4. 現實專屬頭像或非標準尾數形態 (如 104532 空花、102832 咲戀、103232 秋乃、104632 珠希、100832 雪等)
        // 嚴格保留自身的 exact ID，次選 baseId + 11
        if (this.exactRealityIds.has(numId) || (numId % 100 !== 11 && numId % 100 !== 31 && numId % 100 !== 61)) {
            const baseId = Math.floor(numId / 100) * 100;
            return [numId, baseId + 11];
        }

        // 5. 普通可玩角色 (Ordinary Playable Unit) 與換裝 Variant (< 190000)
        // 嚴格保留自身換裝之百位基底 (baseId)，首選 +11 (日常基礎立繪)，次選 +31 (3★卡面立繪)
        const baseId = Math.floor(numId / 100) * 100;
        return [baseId + 11, baseId + 31];
    },

    // 核心：生成頭像 URL 陣列（依優先序）
    getUrlCandidates(unitId) {
        if (!unitId || unitId < 100000) return [];
        const portraitIds = this.resolveDialoguePortraitIds(unitId);
        if (portraitIds.length === 0) return [];

        const candidates = [];
        
        // 1. webp 格式 (優先)
        portraitIds.forEach(id => {
            candidates.push(`${this.localBase}${id}.webp`);
            this.cdnBases.forEach(cdn => candidates.push(`${cdn}${id}.webp`));
        });

        // 2. png 格式 (降級備用，特別是 NPC 資源)
        portraitIds.forEach(id => {
            candidates.push(`${this.localBase}${id}.png`);
            this.cdnBases.forEach(cdn => candidates.push(`${cdn}${id}.png`));
        });

        return candidates;
    },

    getAvatarUrl(unitId) {
        if (!unitId) return 'https://redive.estertion.win/icon/unit/100001.webp';
        const portraitIds = this.resolveDialoguePortraitIds(unitId);
        const mainId = portraitIds.length > 0 ? portraitIds[0] : unitId;
        return `icon/unit/${mainId}.png`;
    },

    getCardUrl(unitId) {
        if (!unitId) return 'https://redive.estertion.win/card/full/100131.webp';
        const baseId = Math.floor(unitId / 100) * 100;
        const mainId = (unitId < 190000) ? (baseId + 31) : unitId;
        return `https://redive.estertion.win/card/full/${mainId}.webp`;
    },

    // 公開 API：取得最佳頭像 img 元素 HTML (根據角色名稱)
    getAvatarHtml(charaName, externalAvatars = {}) {
        const cleanName = this.cleanName(charaName);
        const unitId = this.getUnitId(cleanName, externalAvatars);

        if (!unitId || unitId < 100000) {
            return this.getFallbackHtml(cleanName);
        }

        const portraitIds = this.resolveDialoguePortraitIds(unitId);
        const mainId = portraitIds.length > 0 ? portraitIds[0] : unitId;
        // 優先使用本地端的 .png 圖片
        const src = `icon/unit/${mainId}.png`;
        const safeName = this.escapeForJsString(cleanName);

        return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleError(this, '${safeName}', ${unitId})">`;
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

        const portraitIds = this.resolveDialoguePortraitIds(finalUnitId);
        const mainId = portraitIds.length > 0 ? portraitIds[0] : finalUnitId;
        // 優先使用本地端的 .png 圖片
        const src = `icon/unit/${mainId}.png`;
        const safeName = this.escapeForJsString(cleanName);

        return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleError(this, '${safeName}', ${finalUnitId})">`;
    },

    // 靜態錯誤處理函式，用於逐步降級載入圖片或顯示文字佔位符
    handleError(img, safeName, arg3, arg4) {
        const finalUnitId = (arg4 !== undefined) ? arg4 : arg3;
        if (!img.dataset.step) {
            img.dataset.step = "1";
        }
        const step = parseInt(img.dataset.step, 10);
        const portraitIds = this.resolveDialoguePortraitIds(finalUnitId);
        const primaryId = portraitIds.length > 0 ? portraitIds[0] : finalUnitId;
        const secondaryId = portraitIds.length > 1 ? portraitIds[1] : null;

        if (step === 1) {
            img.dataset.step = "2";
            // 第一步：如果本地 primaryId png 失敗，嘗試 So-net 00500012 的 primaryId .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/icon/unit/${primaryId}.png`;
            return;
        }
        if (step === 2) {
            img.dataset.step = "3";
            // 第二步：如果 So-net 00500012 失敗，嘗試 So-net 00500015 的 primaryId .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500015/Jpn/AssetBundles/Android/icon/unit/${primaryId}.png`;
            return;
        }
        if (step === 3) {
            img.dataset.step = "4";
            // 第三步：如果 So-net 皆失敗，嘗試 EsterTion 的 primaryId .webp (EsterTion 頭像最齊全的格式)
            img.src = `https://redive.estertion.win/icon/unit/${primaryId}.webp`;
            return;
        }
        if (step === 4 && secondaryId) {
            img.dataset.step = "5";
            // 第四步：若 primaryId 均失敗且有 secondaryId (例如 +31 備選)，嘗試本地 secondaryId .png
            img.src = `icon/unit/${secondaryId}.png`;
            return;
        }
        if (step === 5 && secondaryId) {
            img.dataset.step = "6";
            // 第五步：嘗試 EsterTion 的 secondaryId .webp
            img.src = `https://redive.estertion.win/icon/unit/${secondaryId}.webp`;
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
        const step = parseInt(img.dataset.step, 10);

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
        // 最後失敗：顯示 999999 佔位符（代表未知技能/裝備，這張圖在 EsterTion 上真實存在，是一張精美質感的問號圖案，比 000000 破圖好得多）
        img.src = 'https://redive.estertion.win/icon/equipment/999999.webp';
    }
};