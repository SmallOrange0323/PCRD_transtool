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
        if (unitId && avatarService) {
            const candidates = avatarService.getUrlCandidates(unitId);
            avatarHtml = `<img src="${candidates[0]}" loading="lazy" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.src='${candidates[1] || candidates[0]}'">`;
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

    /**
     * 渲染登場角色完整頁面結構 HTML
     * @param {Object} options - 依賴注入選項
     * @returns {string} 完整頁面 HTML 字串
     */
    renderSpeakerPageHtml(options) {
        const { searchQuery, sortOrder, escapeHtml } = options || {};
        const safeSearchVal = escapeHtml ? escapeHtml(searchQuery || "") : (searchQuery || "");
        const sortVal = sortOrder || "appearances-desc";
        const gridHtml = this.renderSpeakerGridHtml(options);

        return `
            <div class="floating-back-btn" onclick="QuestMapModule.handleFloatingBack()" style="position: fixed; top: 20px; left: 20px; z-index: 9998; width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #2d6bcf, #1a4a9e); color: #fff; border: 2px solid rgba(255,255,255,0.3); cursor: pointer; box-shadow: 0 4px 15px rgba(26, 74, 158, 0.5); display: flex; align-items: center; justify-content: center; font-size: 1.2rem; font-weight: bold; transition: transform 0.2s ease, box-shadow 0.2s ease;" onmouseover="this.style.transform='scale(1.15)'; this.style.boxShadow='0 6px 20px rgba(26, 74, 158, 0.7)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 15px rgba(26, 74, 158, 0.5)';">←</div>
            <div class="map-container glass-card">
                <div class="breadcrumb-container" style="margin-bottom: 15px; display: flex; align-items: center; gap: 12px; font-size: 0.95rem;">
                    <button onclick="QuestMapModule.handleBackClick()" class="back-to-menu-btn" style="
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        width: 32px;
                        height: 32px;
                        border-radius: 50%;
                        background: linear-gradient(135deg, #0984e3, #00cec9);
                        color: #fff;
                        border: none;
                        cursor: pointer;
                        box-shadow: 0 2px 6px rgba(9, 132, 227, 0.4);
                        transition: transform 0.2s ease, box-shadow 0.2s ease;
                        font-size: 1rem;
                        font-weight: bold;
                        flex-shrink: 0;
                    " onmouseover="this.style.transform='scale(1.1)'; this.style.boxShadow='0 4px 12px rgba(9, 132, 227, 0.6)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 2px 6px rgba(9, 132, 227, 0.4)';">
                        ←
                    </button>
                    <span class="breadcrumb-item linkable" onclick="QuestMapModule.goBackToMenu()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;"><span style="font-size: 1.1rem;">🏠</span> 劇情大廳</span>
                    <span class="breadcrumb-separator" style="color: rgba(255,255,255,0.3);">/</span>
                    <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">👥 登場角色</span>
                </div>
                <div class="map-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 15px; margin-bottom: 20px;">
                    <div>
                        <h2>👥 登場角色總覽</h2>
                        <p class="subtitle">統計所有登場人物的登場話數，點擊可直接查詢詳細資料與登場話數列表</p>
                    </div>
                </div>

                <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap; margin-bottom: 20px;">
                    <div style="flex: 1; min-width: 250px;">
                        <input type="text" id="speaker-search-input" placeholder="🔍 搜尋登場角色名字..." value="${safeSearchVal}"  
                               oninput="QuestMapModule.handleSpeakerSearch(this.value)" 
                               style="width: 100%; padding: 10px 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); background: rgba(0,0,0,0.2); color: #fff; font-size: 0.9rem; outline: none; transition: border 0.2s;">
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="color: rgba(255,255,255,0.7); font-size: 0.9rem;">排序方式：</span>
                        <select onchange="QuestMapModule.handleSpeakerSort(this.value)" 
                                style="padding: 10px 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); background: rgba(20,20,20,0.8); color: #fff; font-size: 0.9rem; outline: none; cursor: pointer;">
                            <option value="appearances-desc" ${sortVal === 'appearances-desc' ? 'selected' : ''}>登場話數：多 ➔ 少</option>
                            <option value="appearances-asc" ${sortVal === 'appearances-asc' ? 'selected' : ''}>登場話數：少 ➔ 多</option>
                            <option value="name-asc" ${sortVal === 'name-asc' ? 'selected' : ''}>名字排序：A ➔ Z</option>
                        </select>
                    </div>
                </div>

                <div class="speaker-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; max-height: 65vh; overflow-y: auto; padding-right: 5px;">
                    ${gridHtml}
                </div>
            </div>
        `;
    }
};
