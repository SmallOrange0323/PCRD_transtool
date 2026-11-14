console.log("speaker-view.js loaded");
/**
 * PCRD Data Hub - 登場人物總覽模組 (SpeakerView)
 * 負責登場角色列表之過濾、排序、卡片渲染與網格 HTML 生成。
 * 本模組為純視圖與輔助模組，不直接持有應用程式狀態或全域路由。
 */

window.SpeakerView = {
    /**
     * 過濾登場角色名稱清單（排除非實體角色如旁白、系統、店員等，並套用搜尋關鍵字）
     * @param {string[]} speakers - 登場角色名稱陣列
     * @param {string} searchQuery - 搜尋關鍵字
     * @returns {string[]} 過濾後的角色名稱陣列
     */
    filterSpeakers(speakers, searchQuery) {
        const nonRealSpeakers = ["旁白", "【系統】", "？？？", "店員", "店長", "選擇肢", "選擇"];
        let list = (speakers || []).filter(name => {
            const clean = (name || "").trim();
            return !nonRealSpeakers.some(nonReal => clean.includes(nonReal));
        });
        if (searchQuery && searchQuery.trim()) {
            const query = searchQuery.trim().toLowerCase();
            list = list.filter(name => name.toLowerCase().includes(query));
        }
        return list;
    },

    /**
     * 排序登場角色名稱清單
     * @param {string[]} speakers - 待排序角色名稱陣列
     * @param {Object} appearanceMap - 角色登場話數映射表 { [name: string]: number[] }
     * @param {string} sortOrder - 排序規則 ('appearances-desc' | 'appearances-asc' | 'name-asc')
     * @returns {string[]} 排序後的角色名稱陣列
     */
    sortSpeakers(speakers, appearanceMap, sortOrder) {
        const sorted = [...(speakers || [])];
        const map = appearanceMap || {};
        sorted.sort((a, b) => {
            const countA = (map[a] || []).length;
            const countB = (map[b] || []).length;
            if (sortOrder === 'appearances-desc') {
                return countB - countA || a.localeCompare(b, 'zh-Hant-TW');
            } else if (sortOrder === 'appearances-asc') {
                return countA - countB || a.localeCompare(b, 'zh-Hant-TW');
            } else {
                return a.localeCompare(b, 'zh-Hant-TW');
            }
        });
        return sorted;
    },

    /**
     * 渲染單一登場角色卡片 HTML
     * @param {string} name - 角色名稱
     * @param {Object} options - 依賴注入選項
     * @returns {string} 卡片 HTML 字串
     */
    renderSpeakerCard(name, options) {
        const { appearanceMap, speakerAvatars, avatarService, resolveRealName, escapeHtml } = options || {};
        const count = ((appearanceMap && appearanceMap[name]) || []).length;
        const realName = resolveRealName ? resolveRealName(name) : name;
        const safeName = escapeHtml ? escapeHtml(name) : name;
        const safeRealName = escapeHtml ? escapeHtml(realName) : realName;
        const unitId = avatarService ? avatarService.getUnitId(realName, speakerAvatars) : null;

        let avatarHtml = "";
        if (avatarService && typeof avatarService.getAvatarHtml === "function") {
            avatarHtml = avatarService.getAvatarHtml(realName, speakerAvatars);
        } else if (unitId && avatarService && typeof avatarService.getUrlCandidates === "function") {
            const candidates = avatarService.getUrlCandidates(unitId);
            const firstSrc = candidates.find(c => c.endsWith('.png')) || candidates[0];
            const fallbackSrc = candidates.find(c => c !== firstSrc) || firstSrc;
            avatarHtml = `<img src="${firstSrc}" loading="lazy" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.onerror=null; this.src='${fallbackSrc}';">`;
        } else {
            avatarHtml = `<div class="npc-avatar-placeholder" style="font-size: 1.2rem; font-weight: bold; color: var(--primary-dark);">${safeRealName.substring(0, 2)}</div>`;
        }

        return `
            <div class="speaker-card glass-card" onclick="QuestMapModule.showCharaModal(${JSON.stringify(name).replace(/"/g, '&quot;')})"
                 style="background: rgba(255,255,255,0.03); border: 1px solid rgba(232,56,117,0.1); border-radius: 12px; padding: 15px 10px; text-align: center; cursor: pointer; transition: all 0.2s ease-in-out; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;"
                 onmouseover="this.style.transform='translateY(-3px)'; this.style.borderColor='rgba(232,56,117,0.25)'; this.style.background='rgba(232,56,117,0.04)';"
                 onmouseout="this.style.transform='none'; this.style.borderColor='rgba(232,56,117,0.1)'; this.style.background='rgba(255,255,255,0.03)';">
                <div style="width: 70px; height: 70px; border-radius: 50%; overflow: hidden; border: 2px solid rgba(232,56,117,0.15); background: rgba(0,0,0,0.05); display: flex; align-items: center; justify-content: center;">
                    ${avatarHtml}
                </div>
                <div style="font-weight: bold; font-size: 0.9rem; color: var(--text-primary); text-overflow: ellipsis; white-space: nowrap; overflow: hidden; width: 100%;" title="${safeName}">${safeName}</div>
                <div style="font-size: 0.78rem; color: var(--accent-color);">🎬 登場 ${count} 話</div>
            </div>
        `;
    },

    /**
     * 渲染登場角色網格內容（包含過濾、排序、卡片陣列與查無結果之空狀態提示）
     * @param {Object} options - 依賴注入選項
     * @returns {string} 網格內部 HTML 字串
     */
    renderSpeakerGridHtml(options) {
        const { appearanceMap, searchQuery, sortOrder } = options || {};
        const allNames = Object.keys(appearanceMap || {});
        const filtered = this.filterSpeakers(allNames, searchQuery);
        const sorted = this.sortSpeakers(filtered, appearanceMap, sortOrder);

        if (sorted.length === 0) {
            return `<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 50px 0;">查無符合條件的登場角色 🔍</div>`;
        }
        return sorted.map(name => this.renderSpeakerCard(name, options)).join('');
    },

    _SEARCH_CHAR_MAP: {
        "祕": "秘", "书": "書", "图": "圖", "丽": "麗", "娅": "婭", "菈": "拉",
        "兰": "蘭", "风": "風", "龙": "龍", "剑": "劍", "圣": "聖", "诞": "誕",
        "灵": "靈", "泽": "澤", "玛": "瑪", "丝": "絲", "贝": "貝", "罗": "羅",
        "乐": "樂", "欢": "歡", "梦": "夢", "爱": "愛", "华": "華", "长": "長",
        "导": "導", "军": "軍", "师": "師", "卫": "衛", "团": "團", "战": "戰",
        "园": "園", "医": "醫", "药": "藥", "猫": "貓", "鱼": "魚", "鸟": "鳥",
        "兽": "獸", "亚": "亞", "弥": "彌", "尔": "爾", "诺": "諾", "苏": "蘇",
        "凯": "凱", "赛": "賽", "费": "費", "维": "維", "达": "達", "乌": "烏",
        "卢": "盧", "鲁": "魯", "西": "西", "东": "東", "门": "門", "间": "間",
        "时": "時", "机": "機", "电": "電", "话": "話", "员": "員", "会": "會",
        "议": "議", "学": "學", "发": "發", "头": "頭", "体": "體", "声": "聲",
        "听": "聽", "说": "說", "读": "讀", "见": "見", "观": "觀", "现": "現",
        "实": "實", "伪": "偽", "变": "變", "过": "過", "进": "進", "来": "來",
        "开": "開", "关": "關", "问": "問", "选": "選", "决": "決", "计": "計",
        "统": "統", "总": "總", "结": "結", "为": "為", "与": "與", "对": "對",
        "将": "將", "让": "讓", "给": "給", "帮": "幫", "讨": "討", "厌": "厭",
        "惊": "驚", "飞": "飛", "游": "遊", "装": "裝", "饰": "飾", "枪": "槍",
        "铠": "鎧", "术": "術", "强": "強", "坏": "壞", "丑": "醜", "旧": "舊",
        "儿": "兒", "敌": "敵", "仆": "僕", "众": "眾", "群": "群", "队": "隊",
        "帅": "帥", "农": "農", "经": "經", "乔": "喬", "冲": "衝",
        "鲨": "鯊", "骷": "骷", "髅": "髏", "狱": "獄", "恶": "惡", "绅": "紳"
    },

    /**
     * 簡繁/異體容錯正規化（用於搜尋比對）
     * @param {string} str - 待正規化文字
     * @returns {string} 小寫且正規化後的文字
     */
    _normalizeSearchText(str) {
        if (!str) return "";
        const map = this._SEARCH_CHAR_MAP;
        return String(str).trim().toLowerCase().split('').map(ch => map[ch] || ch).join('');
    },

    /**
     * 取得 NPC 在指定劇情分類下的話數統計
     * @param {Object} npc - NPC 圖鑑項目
     * @param {string} scope - 'all' | 'main' | 'event'
     * @returns {number} 對應話數
     */
    getNpcScopeCount(npc, scope = 'all') {
        if (!npc) return 0;
        if (scope === 'main') return Number(npc.main_count) || 0;
        if (scope === 'event') return Number(npc.event_count) || 0;
        return Number(npc.appearance_count) || 0;
    },

    /**
     * 過濾 NPC 圖鑑項目（支援分類、女角限定與名稱/別名關鍵字搜尋）
     * @param {Array<Object>} npcs - NPC 項目陣列
     * @param {Object} options - 過濾條件 { npcScopeFilter, npcFemaleOnly, searchQuery }
     * @returns {Array<Object>} 過濾後的 NPC 陣列
     */
    filterNpcCatalog(npcs, options = {}) {
        const { npcScopeFilter = 'all', npcFemaleOnly = false, searchQuery = '' } = options || {};
        const query = this._normalizeSearchText(searchQuery);

        return (npcs || []).filter(npc => {
            if (!npc || typeof npc !== 'object') return false;

            if (npcScopeFilter === 'main') {
                const inMain = (Array.isArray(npc.story_scopes) && npc.story_scopes.includes('main')) || (Number(npc.main_count) > 0);
                if (!inMain) return false;
            } else if (npcScopeFilter === 'event') {
                const inEvent = (Array.isArray(npc.story_scopes) && npc.story_scopes.includes('event')) || (Number(npc.event_count) > 0);
                if (!inEvent) return false;
            }

            if (npcFemaleOnly && npc.gender !== 'female') {
                return false;
            }

            if (query) {
                const searchTargets = [
                    npc.name,
                    npc.special_label,
                    ...(Array.isArray(npc.aliases) ? npc.aliases : [])
                ].filter(Boolean);
                const matched = searchTargets.some(target => this._normalizeSearchText(target).includes(query));
                if (!matched) return false;
            }

            return true;
        });
    },

    /**
     * 排序 NPC 圖鑑項目
     * @param {Array<Object>} npcs - 待排序 NPC 陣列
     * @param {string} sortOrder - 'appearances-desc' | 'appearances-asc' | 'name-asc'
     * @param {string} scope - 'all' | 'main' | 'event'
     * @returns {Array<Object>} 排序後的 NPC 陣列
     */
    sortNpcCatalog(npcs, sortOrder = 'appearances-desc', scope = 'all') {
        const sorted = [...(npcs || [])];
        sorted.sort((a, b) => {
            const nameA = String(a && a.name || '');
            const nameB = String(b && b.name || '');
            const countA = this.getNpcScopeCount(a, scope);
            const countB = this.getNpcScopeCount(b, scope);
            if (sortOrder === 'appearances-desc') {
                return countB - countA || nameA.localeCompare(nameB, 'zh-Hant-TW');
            }
            if (sortOrder === 'appearances-asc') {
                return countA - countB || nameA.localeCompare(nameB, 'zh-Hant-TW');
            }
            return nameA.localeCompare(nameB, 'zh-Hant-TW');
        });
        return sorted;
    },

    /**
     * 渲染 NPC 頭像 HTML（優先使用 active 登錄表與可靠本地 6 碼 PNG 路徑）
     */
    _renderNpcAvatarHtml(unitId, displayName, avatarService, escapeHtml) {
        const esc = escapeHtml ? escapeHtml : (s) => String(s || '');
        const numId = Number(unitId);
        const safeLabel = esc(displayName || 'NPC');
        const safeInitials = esc(String(displayName || '??').substring(0, 2));

        if (avatarService && typeof avatarService.getAvatarHtmlByUnitId === 'function' &&
            avatarService.manifestLoaded && !avatarService.manifestUnavailable && Number.isInteger(numId) && numId > 0) {
            const resolvedHtml = avatarService.getAvatarHtmlByUnitId(numId, displayName);
            if (resolvedHtml && resolvedHtml.includes('<img')) {
                return resolvedHtml;
            }
        }

        if (Number.isInteger(numId) && numId > 0) {
            const paddedId = String(numId).padStart(6, '0');
            return `<img src="icon/unit/${paddedId}.png" alt="${safeLabel}" loading="lazy" decoding="async" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.onerror=null; this.style.display='none'; if (this.parentNode) { this.parentNode.innerHTML = '<div class=&quot;npc-avatar-placeholder&quot;>${safeInitials}</div>'; }">`;
        }

        return `<div class="npc-avatar-placeholder">${safeInitials}</div>`;
    },

    /**
     * 渲染特殊立繪 NPC 獨立區塊（例如 秘書（秘書子）常服 / 泳裝雙立繪）
     */
    renderSpecialNpcSectionHtml(specialNpcs, options = {}) {
        if (!specialNpcs || specialNpcs.length === 0) return '';
        const { avatarService, escapeHtml } = options || {};
        const esc = escapeHtml ? escapeHtml : (s) => String(s || '');

        return specialNpcs.map(npc => {
            const displayTitle = npc.special_label ? `${npc.name}（${npc.special_label}）` : npc.name;
            const safeTitle = esc(displayTitle);
            const jsNameArg = JSON.stringify(npc.name).replace(/"/g, '&quot;');
            const variants = (Array.isArray(npc.variants) && npc.variants.length > 0)
                ? npc.variants
                : [{ unit_id: npc.unit_id, label: '預設' }];

            const variantsHtml = variants.map(variant => {
                const vUid = Number(variant.unit_id);
                const vLabel = esc(variant.label || '立繪');
                const avatarHtml = this._renderNpcAvatarHtml(vUid, npc.name, avatarService, escapeHtml);
                return `
                    <button type="button" class="npc-variant-btn"
                            onclick="QuestMapModule.showCharaModal(${jsNameArg}, ${vUid})"
                            title="點擊查看 ${safeTitle}（${vLabel}）登場話數">
                        <div class="npc-variant-avatar">${avatarHtml}</div>
                        <span class="npc-variant-label">${vLabel}</span>
                    </button>
                `;
            }).join('');

            return `
                <div class="npc-special-section glass-card">
                    <div class="npc-special-header">
                        <div class="npc-special-title-wrap">
                            <span class="npc-special-title">⭐ 特殊立繪 NPC — ${safeTitle}</span>
                            <span class="npc-special-stats">總計 ${Number(npc.appearance_count) || 0} 話 ・ 主線 ${Number(npc.main_count) || 0} 話 ・ 活動 ${Number(npc.event_count) || 0} 話</span>
                        </div>
                    </div>
                    <div class="npc-variant-list">
                        ${variantsHtml}
                    </div>
                </div>
            `;
        }).join('');
    },

    /**
     * 渲染一般具名 NPC 圖鑑單張卡片
     */
    renderNpcCard(npc, options = {}) {
        const { npcScopeFilter = 'all', avatarService, escapeHtml } = options || {};
        const esc = escapeHtml ? escapeHtml : (s) => String(s || '');
        const safeName = esc(npc.name);
        const jsNameArg = JSON.stringify(npc.name).replace(/"/g, '&quot;');
        const uid = Number(npc.unit_id);
        const count = this.getNpcScopeCount(npc, npcScopeFilter);
        const scopeLabel = npcScopeFilter === 'main' ? '主線' : (npcScopeFilter === 'event' ? '活動' : '登場');
        const avatarHtml = this._renderNpcAvatarHtml(uid, npc.name, avatarService, escapeHtml);
        const genderTag = npc.gender === 'female' ? '<span class="npc-gender-badge" title="女性角色">♀</span>' : '';

        return `
            <button type="button" class="speaker-card npc-catalog-card glass-card"
                    onclick="QuestMapModule.showCharaModal(${jsNameArg}, ${uid})"
                    title="${safeName}（${scopeLabel} ${count} 話）">
                <div class="npc-catalog-avatar">
                    ${avatarHtml}
                    ${genderTag}
                </div>
                <div class="npc-catalog-name" title="${safeName}">${safeName}</div>
                <div class="npc-catalog-count">🎬 ${scopeLabel} ${count} 話</div>
            </button>
        `;
    },

    /**
     * 渲染 NPC 圖鑑內容區域（含特殊立繪獨立區塊與一般具名 NPC 網格）
     */
    renderNpcCatalogContentHtml(options = {}) {
        const { npcCatalog, npcScopeFilter = 'all', sortOrder = 'appearances-desc' } = options || {};
        if (!npcCatalog || !Array.isArray(npcCatalog.npcs)) {
            return `<div class="npc-catalog-empty">目前暫無法載入 NPC 頭像圖鑑資料。</div>`;
        }

        const filtered = this.filterNpcCatalog(npcCatalog.npcs, options);
        if (filtered.length === 0) {
            return `<div class="npc-catalog-empty">查無符合條件的 NPC 角色 🔍</div>`;
        }

        const specialNpcs = this.sortNpcCatalog(filtered.filter(npc => npc.is_special), sortOrder, npcScopeFilter);
        const regularNpcs = this.sortNpcCatalog(filtered.filter(npc => !npc.is_special), sortOrder, npcScopeFilter);

        const specialHtml = this.renderSpecialNpcSectionHtml(specialNpcs, options);
        const regularGridHtml = regularNpcs.length > 0
            ? `<div class="npc-catalog-grid">${regularNpcs.map(npc => this.renderNpcCard(npc, options)).join('')}</div>`
            : '';

        return `${specialHtml}${regularGridHtml}`;
    },

    /**
     * 渲染登場角色完整頁面結構 HTML
     * @param {Object} options - 依賴注入選項
     * @returns {string} 完整頁面 HTML 字串
     */
    renderSpeakerPageHtml(options) {
        const {
            searchQuery,
            sortOrder,
            escapeHtml,
            speakerSubTab = 'all',
            npcScopeFilter = 'all',
            npcFemaleOnly = false,
            npcCatalog = null
        } = options || {};
        const safeSearchVal = escapeHtml ? escapeHtml(searchQuery || "") : (searchQuery || "");
        const sortVal = sortOrder || "appearances-desc";
        const activeSubTab = speakerSubTab === 'npc' ? 'npc' : 'all';
        const allNpcs = (npcCatalog && Array.isArray(npcCatalog.npcs)) ? npcCatalog.npcs : [];
        const npcTabCountLabel = allNpcs.length > 0 ? ` (${allNpcs.length})` : '';

        const subTabsHtml = `
            <div class="speaker-subtabs" style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px;">
                <button type="button" class="part-btn ${activeSubTab === 'all' ? 'active' : ''}" data-subtab="all" onclick="QuestMapModule.handleSpeakerSubTab('all')">👥 全部登場角色</button>
                <button type="button" class="part-btn ${activeSubTab === 'npc' ? 'active' : ''}" data-subtab="npc" onclick="QuestMapModule.handleSpeakerSubTab('npc')">🖼️ NPC 頭像圖鑑${npcTabCountLabel}</button>
            </div>
        `;

        let bodyHtml = '';
        if (activeSubTab === 'npc') {
            const mainTotal = this.filterNpcCatalog(allNpcs, { npcScopeFilter: 'main' }).length;
            const eventTotal = this.filterNpcCatalog(allNpcs, { npcScopeFilter: 'event' }).length;
            const femaleTotal = this.filterNpcCatalog(allNpcs, { npcFemaleOnly: true }).length;
            const contentHtml = this.renderNpcCatalogContentHtml(options);

            bodyHtml = `
                <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap; margin-bottom: 12px;">
                    <div style="flex: 1; min-width: 250px;">
                        <input type="text" id="speaker-search-input" placeholder="🔍 搜尋 NPC 名稱或別名（例如：秘書子）..." value="${safeSearchVal}"
                               oninput="QuestMapModule.handleSpeakerSearch(this.value)"
                               style="width: 100%; padding: 10px 15px; border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.25); background: rgba(255, 255, 255, 0.85); color: var(--text-primary); font-size: 0.9rem; outline: none; transition: border 0.2s;">
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="color: var(--text-secondary); font-size: 0.9rem;">排序方式：</span>
                        <select id="speaker-sort-select" onchange="QuestMapModule.handleSpeakerSort(this.value)"
                                style="padding: 10px 15px; border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.25); background: rgba(255, 255, 255, 0.85); color: var(--text-primary); font-size: 0.9rem; outline: none; cursor: pointer;">
                            <option value="appearances-desc" ${sortVal === 'appearances-desc' ? 'selected' : ''}>登場話數：多 ➔ 少</option>
                            <option value="appearances-asc" ${sortVal === 'appearances-asc' ? 'selected' : ''}>登場話數：少 ➔ 多</option>
                            <option value="name-asc" ${sortVal === 'name-asc' ? 'selected' : ''}>名字排序：A ➔ Z</option>
                        </select>
                    </div>
                </div>

                <div class="npc-filter-bar">
                    <div class="npc-scope-pills">
                        <button type="button" class="part-btn secondary-pill ${npcScopeFilter === 'all' ? 'active' : ''}" data-npc-scope="all" onclick="QuestMapModule.handleNpcScopeFilter('all')">全部 (${allNpcs.length})</button>
                        <button type="button" class="part-btn secondary-pill ${npcScopeFilter === 'main' ? 'active' : ''}" data-npc-scope="main" onclick="QuestMapModule.handleNpcScopeFilter('main')">主線登場 (${mainTotal})</button>
                        <button type="button" class="part-btn secondary-pill ${npcScopeFilter === 'event' ? 'active' : ''}" data-npc-scope="event" onclick="QuestMapModule.handleNpcScopeFilter('event')">活動登場 (${eventTotal})</button>
                    </div>
                    <button type="button" id="speaker-npc-female-btn" class="part-btn secondary-pill npc-female-toggle ${npcFemaleOnly ? 'active' : ''}" onclick="QuestMapModule.handleNpcFemaleToggle()">♀ 只看女角 (${femaleTotal})</button>
                </div>

                <div id="speaker-npc-container" class="speaker-npc-container">
                    ${contentHtml}
                </div>
            `;
        } else {
            const gridHtml = this.renderSpeakerGridHtml(options);
            bodyHtml = `
                <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap; margin-bottom: 20px;">
                    <div style="flex: 1; min-width: 250px;">
                        <input type="text" id="speaker-search-input" placeholder="🔍 搜尋登場角色名字..." value="${safeSearchVal}"  
                               oninput="QuestMapModule.handleSpeakerSearch(this.value)" 
                               style="width: 100%; padding: 10px 15px; border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.25); background: rgba(255, 255, 255, 0.85); color: var(--text-primary); font-size: 0.9rem; outline: none; transition: border 0.2s;">
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="color: var(--text-secondary); font-size: 0.9rem;">排序方式：</span>
                        <select onchange="QuestMapModule.handleSpeakerSort(this.value)" 
                                style="padding: 10px 15px; border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.25); background: rgba(255, 255, 255, 0.85); color: var(--text-primary); font-size: 0.9rem; outline: none; cursor: pointer;">
                            <option value="appearances-desc" ${sortVal === 'appearances-desc' ? 'selected' : ''}>登場話數：多 ➔ 少</option>
                            <option value="appearances-asc" ${sortVal === 'appearances-asc' ? 'selected' : ''}>登場話數：少 ➔ 多</option>
                            <option value="name-asc" ${sortVal === 'name-asc' ? 'selected' : ''}>名字排序：A ➔ Z</option>
                        </select>
                    </div>
                </div>

                <div class="speaker-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; max-height: 65vh; overflow-y: auto; padding-right: 5px;">
                    ${gridHtml}
                </div>
            `;
        }

        return `
            <div class="map-container glass-card">
                <div class="breadcrumb-container" style="display: flex; align-items: center; gap: 12px; font-size: 0.95rem;">
                    <span class="breadcrumb-item linkable" onclick="QuestMapModule.goBackToMenu()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;"><span style="font-size: 1.1rem;">🏠</span> 劇情大廳</span>
                    <span class="breadcrumb-separator" style="color: var(--text-muted, #9e7a8f);">/</span>
                    <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">👥 登場角色</span>
                </div>
                <div class="map-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 15px; margin-bottom: 20px;">
                    <div>
                        <h2>👥 登場角色總覽</h2>
                        <p class="subtitle">統計所有登場人物的登場話數，點擊可直接查詢詳細資料與登場話數列表</p>
                    </div>
                </div>

                ${subTabsHtml}
                ${bodyHtml}
            </div>
        `;
    }
};
