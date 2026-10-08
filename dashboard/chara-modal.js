console.log("chara-modal.js loaded");
/**
 * PCRD Data Hub - 角色檔案彈窗模組 (CharaModalView)
 * 負責角色個人 Profile 檔案彈窗 (Modal) 之 DOM 單例管理、HTML 組裝與顯示。
 * 本模組為純視圖模組，不直接操作資料庫 SQL 查詢或應用程式導航路由。
 */

window.CharaModalView = {
    /**
     * 取得或建立角色彈窗 DOM 容器單例
     * @returns {HTMLElement} 彈窗 DOM 元素
     */
    getCharaModal() {
        let modalEl = document.getElementById('game-chara-modal');
        if (!modalEl) {
            modalEl = document.createElement('div');
            modalEl.id = 'game-chara-modal';
            modalEl.className = 'game-modal-overlay';
            modalEl.onclick = function(event) {
                if (event.target === modalEl) {
                    modalEl.classList.remove('active');
                }
            };
            // 支援 Escape 鍵關閉
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    const m = document.getElementById('game-chara-modal');
                    if (m && m.classList.contains('active')) {
                        m.classList.remove('active');
                    }
                }
            });
            document.body.appendChild(modalEl);
        }
        return modalEl;
    },

    /**
     * 從目前已載入的對白中解析角色唯一的 explicit unit_id。
     * 若同一顯示角色在本話對應到多個不同 unit_id，則視為具歧義並回傳 null，
     * 避免角色檔案視窗自行猜測換裝或 NPC 變體。
     *
     * @param {string} realCharaName - 經 QuestMapModule 正規化後的角色名稱
     * @returns {number|null} 唯一 canonical unit_id，或 null
     */
    resolveCurrentDialogueUnitId(realCharaName) {
        if (!realCharaName || !window.QuestMapModule || !Array.isArray(window.QuestMapModule.currentDialogueList)) {
            return null;
        }

        const unitIds = new Set();
        const resolver = (typeof window.QuestMapModule.getCharaRealName === 'function')
            ? window.QuestMapModule.getCharaRealName.bind(window.QuestMapModule)
            : (name) => name;

        window.QuestMapModule.currentDialogueList.forEach(item => {
            if (!item || item.type) return;
            const resolvedName = resolver(item.name || "");
            if (resolvedName !== realCharaName) return;

            const unitId = Number(item.unit_id);
            if (Number.isInteger(unitId) && unitId > 0) {
                unitIds.add(unitId);
            }
        });

        if (unitIds.size !== 1) return null;
        return unitIds.values().next().value;
    },

    _escapeAppearanceText(value, escapeHtml) {
        const text = value == null ? "" : String(value);
        if (typeof escapeHtml === 'function') return escapeHtml(text);
        return text.replace(/[&<>"']/g, ch => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[ch]));
    },

    _buildAppearanceTree(items) {
        const root = { label: '', count: 0, children: new Map(), items: [] };
        items.forEach(item => {
            root.count++;
            let node = root;
            const path = Array.isArray(item.path) && item.path.length
                ? item.path
                : ['其他／無法分類'];
            path.forEach(label => {
                if (!node.children.has(label)) {
                    node.children.set(label, { label, count: 0, children: new Map(), items: [] });
                }
                node = node.children.get(label);
                node.count++;
            });
            node.items.push(item);
        });
        return root;
    },

    _renderAppearanceTreeNode(node, depth, escapeHtml, currentPath = []) {
        const path = node.label ? [...currentPath, node.label] : currentPath;
        const groupPathStr = path.join(' / ');
        const safeGroupPath = this._escapeAppearanceText(groupPathStr, escapeHtml);
        const safeLabel = this._escapeAppearanceText(node.label, escapeHtml);
        const childGroups = [...node.children.values()]
            .sort((a, b) => a.label.localeCompare(b.label, 'zh-Hant'));
        const items = [...node.items]
            .sort((a, b) => String(a.sortKey || a.storyId).localeCompare(String(b.sortKey || b.storyId), 'zh-Hant', { numeric: true }));

        const childrenHtml = childGroups
            .map(child => this._renderAppearanceTreeNode(child, depth + 1, escapeHtml, path))
            .join('');

        const itemsHtml = items.map(item => {
            const safeLeaf = this._escapeAppearanceText(item.label || `ID: ${item.storyId}`, escapeHtml);
            const safeSearch = this._escapeAppearanceText(item.searchText || '', escapeHtml);
            const safeTitle = this._escapeAppearanceText(item.fullLabel || item.label || `ID: ${item.storyId}`, escapeHtml);
            if (item.canNavigate === false) {
                return `
                    <div class="chara-appearance-item is-unresolved"
                         data-appearance-search="${safeSearch}"
                         title="${safeTitle}">
                        <span class="chara-appearance-leaf">${safeLeaf}</span>
                    </div>
                `;
            }
            return `
                <button type="button"
                        class="chara-appearance-item"
                        data-appearance-search="${safeSearch}"
                        title="${safeTitle}"
                        onclick="QuestMapModule.jumpToStory(${Number(item.storyId)}, 'game-chara-modal')">
                    <span class="chara-appearance-leaf">${safeLeaf}</span>
                </button>
            `;
        }).join('');

        return `
            <details class="chara-appearance-group" data-appearance-depth="${depth}" data-group-path="${safeGroupPath}">
                <summary>
                    <span class="chara-appearance-group-title">${safeLabel}</span>
                    <span class="chara-appearance-count">${node.count}</span>
                </summary>
                <div class="chara-appearance-group-body">
                    ${childrenHtml}
                    ${itemsHtml}
                </div>
            </details>
        `;
    },

    /**
     * 以可搜尋的階層目錄渲染角色登場劇情。
     * resolveStoryMeta(storyId) 應回傳：
     * { storyId, path: string[], label, fullLabel, searchText, sortKey, canNavigate }
     */
    renderAppearancesHtml(appearances, resolveStoryMeta, escapeHtml, resolveStoryLabel, realCharaName) {
        if (!appearances || appearances.length === 0) {
            return `<div class="chara-appearance-empty">暫無登場話數統計數據。</div>`;
        }

        const items = appearances.map(rawStoryId => {
            const storyId = Number(rawStoryId);
            let meta = null;
            if (typeof resolveStoryMeta === 'function') {
                meta = resolveStoryMeta(storyId);
            }

            // Legacy compatibility for callers/tests that only provide a flat label resolver.
            if (!meta) {
                let label = `ID: ${storyId}`;
                if (typeof resolveStoryLabel === 'function') {
                    label = resolveStoryLabel(storyId) || label;
                }
                meta = {
                    storyId,
                    path: ['其他／無法分類'],
                    label,
                    fullLabel: label,
                    searchText: `${label} ${storyId}`,
                    sortKey: storyId,
                    canNavigate: !String(label).startsWith('ID:')
                };
            }

            return {
                storyId,
                path: Array.isArray(meta.path) && meta.path.length ? meta.path : ['其他／無法分類'],
                label: meta.label || `ID: ${storyId}`,
                fullLabel: meta.fullLabel || meta.label || `ID: ${storyId}`,
                searchText: [meta.searchText, meta.fullLabel, meta.label, ...(meta.path || []), storyId]
                    .filter(Boolean)
                    .join(' ')
                    .toLowerCase(),
                sortKey: meta.sortKey ?? storyId,
                canNavigate: meta.canNavigate !== false,
                hasFailed: meta.hasFailed || false
            };
        });

        const tree = this._buildAppearanceTree(items);
        const groupsHtml = [...tree.children.values()]
            .sort((a, b) => a.label.localeCompare(b.label, 'zh-Hant'))
            .map(node => this._renderAppearanceTreeNode(node, 0, escapeHtml))
            .join('');

        const hasFailedItems = items.some(it => it.hasFailed || (typeof it.label === 'string' && it.label.includes('名稱載入失敗')));
        const safeCharaName = realCharaName ? this._escapeAppearanceText(realCharaName, escapeHtml) : '';
        const retryBtnHtml = (hasFailedItems && safeCharaName)
            ? ` <button type="button" class="chara-appearance-retry-btn" onclick="QuestMapModule.retryCharaMetadata('${safeCharaName}')">重試載入</button>`
            : '';

        return `
            <div class="chara-appearance-directory">
                <div class="chara-appearance-toolbar">
                    <input type="search"
                           class="chara-appearance-search"
                           placeholder="搜尋劇情名稱、活動、章節或 ID..."
                           aria-label="搜尋角色登場劇情"
                           oninput="CharaModalView.filterAppearanceDirectory(this)">
                    <span class="chara-appearance-search-status" aria-live="polite">${items.length} 話${retryBtnHtml}</span>
                </div>
                <div class="chara-appearance-tree">
                    ${groupsHtml}
                </div>
            </div>
        `;
    },

    /**
     * 僅局部更新 Modal 內的登場劇情目錄 (.chara-appearance-section)，
     * 避免非同步補載官方 metadata 時重新繪製整個 Modal 破壞使用者操作狀態。
     */
    updateAppearancesSection(appearances, resolveStoryMeta, escapeHtml, resolveStoryLabel, realCharaName) {
        const modalEl = this.getCharaModal();
        if (!modalEl) return;
        const sectionEl = modalEl.querySelector('.chara-appearance-section');
        if (!sectionEl) return;

        // 記錄使用者目前的搜尋框狀態、捲動位置與展開節點
        const currentSearchInput = typeof sectionEl.querySelector === 'function'
            ? sectionEl.querySelector('.chara-appearance-search')
            : null;
        const isSearchFocused = typeof document !== 'undefined' && document.activeElement === currentSearchInput;
        const caretStart = currentSearchInput && typeof currentSearchInput.selectionStart === 'number' ? currentSearchInput.selectionStart : null;
        const caretEnd = currentSearchInput && typeof currentSearchInput.selectionEnd === 'number' ? currentSearchInput.selectionEnd : null;
        const currentQuery = currentSearchInput ? (currentSearchInput.value || '') : '';

        const currentTreeEl = typeof sectionEl.querySelector === 'function'
            ? sectionEl.querySelector('.chara-appearance-tree')
            : null;
        const treeScrollTop = currentTreeEl && typeof currentTreeEl.scrollTop === 'number' ? currentTreeEl.scrollTop : 0;

        const openGroupPaths = new Set(
            typeof sectionEl.querySelectorAll === 'function'
                ? [...sectionEl.querySelectorAll('.chara-appearance-group[open]')]
                    .map(el => (typeof el.getAttribute === 'function' ? el.getAttribute('data-group-path') : el.dataset?.groupPath))
                    .filter(Boolean)
                : []
        );

        const appListHtml = this.renderAppearancesHtml(appearances, resolveStoryMeta, escapeHtml, resolveStoryLabel, realCharaName);
        sectionEl.innerHTML = `
            <h4>📖 登場劇情目錄</h4>
            ${appListHtml}
        `;

        // 還原先前已展開的目錄階層
        if (openGroupPaths.size > 0 && !currentQuery && typeof sectionEl.querySelectorAll === 'function') {
            sectionEl.querySelectorAll('.chara-appearance-group').forEach(group => {
                const p = typeof group.getAttribute === 'function' ? group.getAttribute('data-group-path') : group.dataset?.groupPath;
                if (p && openGroupPaths.has(p)) {
                    group.open = true;
                }
            });
        }

        // 若原先有搜尋字串，重新套用過濾
        const newSearchInput = typeof sectionEl.querySelector === 'function'
            ? sectionEl.querySelector('.chara-appearance-search')
            : null;
        if (newSearchInput && currentQuery) {
            newSearchInput.value = currentQuery;
            this.filterAppearanceDirectory(newSearchInput);
        }

        // 還原捲動位置
        const newTreeEl = typeof sectionEl.querySelector === 'function'
            ? sectionEl.querySelector('.chara-appearance-tree')
            : null;
        if (newTreeEl && typeof treeScrollTop === 'number') {
            newTreeEl.scrollTop = treeScrollTop;
        }

        // 還原搜尋輸入框焦點與游標位置
        if (newSearchInput && isSearchFocused && typeof newSearchInput.focus === 'function') {
            newSearchInput.focus();
            if (caretStart !== null && caretEnd !== null && typeof newSearchInput.setSelectionRange === 'function') {
                newSearchInput.setSelectionRange(caretStart, caretEnd);
            }
        }
    },

    filterAppearanceDirectory(inputEl) {
        const directory = inputEl && inputEl.closest
            ? inputEl.closest('.chara-appearance-directory')
            : null;
        if (!directory) return;

        const query = String(inputEl.value || '').trim().toLowerCase();
        const items = [...directory.querySelectorAll('.chara-appearance-item')];
        let visibleCount = 0;

        items.forEach(item => {
            const haystack = String(item.dataset.appearanceSearch || '').toLowerCase();
            const visible = !query || haystack.includes(query);
            item.hidden = !visible;
            if (visible) visibleCount++;
        });

        const groups = [...directory.querySelectorAll('.chara-appearance-group')].reverse();
        groups.forEach(group => {
            const hasVisibleItem = [...group.querySelectorAll('.chara-appearance-item')]
                .some(item => !item.hidden);
            group.hidden = !hasVisibleItem;
            if (query && hasVisibleItem) {
                group.open = true;
            } else if (!query) {
                group.open = false;
            }
        });

        const status = directory.querySelector('.chara-appearance-search-status');
        if (status) {
            status.textContent = query ? `找到 ${visibleCount} 話` : `${items.length} 話`;
        }
    },

    /**
     * 渲染角色基本資料設定表格 HTML
     * @param {Object|null} profile - 角色 Profile 資料物件
     * @returns {string} 基本資料 HTML 字串
     */
    renderProfileDetailsHtml(profile) {
        if (!profile) {
            return `
                <div style="flex: 1; min-width: 200px; display: flex; flex-direction: column; justify-content: center;">
                    <div style="color: var(--text-secondary); font-size: 0.9rem; font-style: italic; border: 1px dashed rgba(232, 56, 117, 0.2); padding: 15px; border-radius: 8px; background: rgba(232, 56, 117, 0.03);">
                        ℹ️ 此角色為劇中登場人物或 NPC，尚無設定集數據。
                    </div>
                </div>
            `;
        }

        const guild = profile.guild || "未知";
        const race = profile.race || "未知";
        const rawAge = profile.age || "";
        const age = rawAge ? `${rawAge}歲` : "未知";
        const rawHeight = profile.height || "";
        const height = rawHeight ? `${rawHeight}cm` : "未知";
        const rawWeight = profile.weight || "";
        const weight = rawWeight ? `${rawWeight}kg` : "未知";
        const birth = (profile.birth_month) ? `${profile.birth_month}月${profile.birth_day}日` : "未知";
        const cv = profile.voice || "未知";

        return `
            <div style="flex: 1; min-width: 200px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.88rem; color: var(--text-primary);">
                    <tr>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600; width: 60px;">公會：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${guild}</td>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600; width: 60px;">種族：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${race}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">年齡：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${age}</td>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">生日：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${birth}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">身高：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${height}</td>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">體重：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${weight}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">聲優：</td>
                        <td colspan="3" style="padding: 4px 0; color: var(--accent-color); font-weight: bold;">${cv}</td>
                    </tr>
                </table>
            </div>
        `;
    },

    /**
     * 渲染角色自我介紹與標語 HTML
     * @param {Object|null} profile - 角色 Profile 資料物件
     * @param {Function} escapeHtml - HTML 轉義函式
     * @returns {string} 自我介紹 HTML 字串
     */
    renderProfileBioHtml(profile, escapeHtml) {
        if (!profile) return "";
        const catchCopy = profile.catch_copy || "";
        const selfText = escapeHtml 
            ? escapeHtml(profile.self_text || "暫無自我介紹。").replace(/\\n/g, '<br>')
            : (profile.self_text || "暫無自我介紹。").replace(/\\n/g, '<br>');

        return `
            ${catchCopy ? `<div style="font-style: italic; color: var(--accent-color); font-size: 0.9rem; margin-bottom: 10px; text-align: left;">「${catchCopy}」</div>` : ''}
            <div style="background: rgba(94, 107, 125, 0.04); padding: 12px; border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.08); font-size: 0.85rem; line-height: 1.6; color: var(--text-primary); margin-bottom: 15px; text-align: left;">
                ${selfText}
            </div>
        `;
    },

    /**
     * 渲染並開啟角色 Profile 彈窗
     * @param {Object} options - 依賴注入選項
     * @param {string} options.realCharaName - 角色真實名稱
     * @param {Object|null} options.profile - 角色 Profile 資料
     * @param {number[]} options.appearances - 登場話數 ID 陣列
     * @param {Object} options.speakerAvatars - 角色頭像映射
     * @param {Object} options.avatarService - AvatarService 實體
     * @param {Function} options.resolveStoryLabel - 話數標籤轉換函式
     * @param {Function} options.escapeHtml - HTML 轉義函式
     */
    renderModal(options) {
        const {
            realCharaName,
            explicitUnitId,
            profile,
            appearances,
            speakerAvatars,
            avatarService,
            resolveStoryMeta,
            resolveStoryLabel,
            escapeHtml
        } = options || {};

        const modalEl = this.getCharaModal();
        const appListHtml = this.renderAppearancesHtml(appearances, resolveStoryMeta, escapeHtml, resolveStoryLabel, realCharaName);
        const detailsHtml = this.renderProfileDetailsHtml(profile);
        const bioHtml = this.renderProfileBioHtml(profile, escapeHtml);
        const numericExplicitUnitId = Number(explicitUnitId);
        const resolvedUnitId = (Number.isInteger(numericExplicitUnitId) && numericExplicitUnitId > 0)
            ? numericExplicitUnitId
            : this.resolveCurrentDialogueUnitId(realCharaName);
        const avatarHtml = avatarService
            ? (resolvedUnitId && typeof avatarService.getAvatarHtmlByUnitId === 'function'
                ? avatarService.getAvatarHtmlByUnitId(resolvedUnitId, realCharaName, speakerAvatars)
                : avatarService.getAvatarHtml(realCharaName, speakerAvatars))
            : "";

        // 僅正規化 UI 顯示文字；realCharaName 仍保留原始 identity key（例如 {0}）。
        const displayCharaName = (window.DialogueView && typeof window.DialogueView.normalizePlayerName === 'function')
            ? window.DialogueView.normalizePlayerName(realCharaName)
            : realCharaName;
        const safeDisplayCharaName = escapeHtml ? escapeHtml(displayCharaName) : displayCharaName;

        modalEl.innerHTML = `
            <div class="game-modal-content" style="max-height: 85vh; overflow-y: auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(94, 107, 125, 0.1); padding-bottom: 12px; margin-bottom: 15px;">
                    <h3 style="margin: 0; color: var(--accent-color); font-size: 1.25rem;">🔍 角色檔案：${safeDisplayCharaName}</h3>
                    <span class="game-modal-close-btn" onclick="document.getElementById('game-chara-modal').classList.remove('active')" style="cursor: pointer; font-size: 1.5rem; color: var(--text-secondary); transition: transform 0.2s;"
                           onmouseover="this.style.transform='rotate(90deg)'" onmouseout="this.style.transform='none'">&times;</span>
                </div>

                <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 15px;">
                    <div style="width: 100px; height: 100px; border-radius: 12px; overflow: hidden; border: 2px solid rgba(232, 56, 117, 0.15); background: #ffffff; display: flex; align-items: center; justify-content: center; padding: 0;">
                        ${avatarHtml}
                    </div>
                    ${detailsHtml}
                </div>

                ${bioHtml}

                <div class="chara-appearance-section">
                    <h4>📖 登場劇情目錄</h4>
                    ${appListHtml}
                </div>
            </div>
        `;

        modalEl.classList.add('active');
    }
};