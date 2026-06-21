console.log("characters.js loaded");

window.CharactersModule = {
    allCharacters: [],
    viewMode: 'grid',
    realNameMap: null,
    activeUnitId: null,
    excludedUnitIds: new Set(JSON.parse(localStorage.getItem('excluded_unit_ids') || '[]')),
    
    async render() {
        const container = document.getElementById('characters-tab');
        container.innerHTML = '<div class="loading-mini">清洗角色數據中...</div>';

        if (!this.realNameMap) {
            try {
                const resp = await fetch('data/real_name_mapping.json');
                if (resp.ok) {
                    this.realNameMap = await resp.json();
                }
            } catch (e) {
                console.error("載入真名對照失敗:", e);
            }
        }

        try {
            // 放寬限制並簡化過濾，確保資料能正常顯示
            const data = window.PCRDatabase.runQuery(`
                SELECT 
                    t.max_id as unit_id,
                    u.unit_name,
                    u.rarity,
                    u.search_area_width as pos,
                    p.race,
                    p.guild
                FROM (
                    SELECT MAX(unit_id) as max_id, unit_name 
                    FROM unit_data 
                    WHERE unit_id < 200000 AND unit_id > 100000
                    AND unit_name NOT LIKE '%怪物%'
                    AND unit_id IN (SELECT DISTINCT unit_id FROM unit_rarity)
                    GROUP BY unit_name
                ) as t
                JOIN unit_data as u ON u.unit_id = t.max_id
                LEFT JOIN unit_profile as p ON u.unit_id = p.unit_id
                ORDER BY unit_id DESC
            `);

            this.allCharacters = data;
            this.renderLayout(container, data);
        } catch (error) {
            console.error("Data Cleanup Error:", error);
            container.innerHTML = `<div class="error-box">數據清洗失敗: ${error.message}</div>`;
        }
    },

    renderLayout(container, characters) {
        container.innerHTML = `
            <div class="gallery-header glass-card" style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                    <div style="display: flex; align-items: center; gap: 20px;">
                        <h2 style="margin: 0;">角色圖鑑 (${window.PCRDatabase.currentRegion.toUpperCase()})</h2>
                        <select id="char-sort" class="region-select" style="background-image: none; padding-right: 12px;">
                            <option value="id-desc" selected>登場時間 (新→舊)</option>
                            <option value="id-asc">登場時間 (舊→新)</option>
                            <option value="pos-asc">角色站位 (前→後)</option>
                        </select>
                    </div>
                    <div class="search-box" style="display: flex; align-items: center; gap: 10px;">
                        <input type="text" id="char-search" placeholder="搜尋角色名稱..." class="region-select" style="width: 250px; background-image: none; padding-right: 12px;">
                        <div class="view-toggle-group">
                            <button id="view-btn-grid" class="view-btn ${this.viewMode === 'grid' ? 'active' : ''}" title="卡片視圖">🎴</button>
                            <button id="view-btn-list" class="view-btn ${this.viewMode === 'list' ? 'active' : ''}" title="列表視圖">📋</button>
                        </div>
                    </div>
                </div>
            </div>
            <div id="char-grid" class="char-grid">
                ${this.viewMode === 'grid' ? this.renderGrid(characters) : this.renderTable(characters)}
            </div>
        `;

        this.updateView = () => {
            const term = document.getElementById('char-search').value.toLowerCase();
            const sortBy = document.getElementById('char-sort').value;
            
            let filtered = this.allCharacters.filter(c => 
                c.unit_name.toLowerCase().includes(term) || 
                (c.race && c.race.toLowerCase().includes(term)) ||
                (c.guild && c.guild.toLowerCase().includes(term))
            );

            if (sortBy === 'id-desc') filtered.sort((a, b) => b.unit_id - a.unit_id);
            else if (sortBy === 'id-asc') filtered.sort((a, b) => a.unit_id - b.unit_id);
            else if (sortBy === 'pos-asc') filtered.sort((a, b) => (a.pos || 999) - (b.pos || 999));

            const displayContainer = document.getElementById('char-grid');
            if (this.viewMode === 'grid') {
                displayContainer.className = 'char-grid';
                const gridFiltered = filtered.filter(c => !this.excludedUnitIds.has(c.unit_id));
                displayContainer.innerHTML = this.renderGrid(gridFiltered);
            } else {
                displayContainer.className = 'char-table-container';
                displayContainer.innerHTML = this.renderTable(filtered);
            }
        };

        const updateView = this.updateView;

        document.getElementById('char-search').addEventListener('input', updateView);
        document.getElementById('char-sort').addEventListener('change', updateView);

        document.getElementById('view-btn-grid').addEventListener('click', () => {
            this.viewMode = 'grid';
            document.getElementById('view-btn-grid').classList.add('active');
            document.getElementById('view-btn-list').classList.remove('active');
            updateView();
        });
        document.getElementById('view-btn-list').addEventListener('click', () => {
            this.viewMode = 'list';
            document.getElementById('view-btn-grid').classList.remove('active');
            document.getElementById('view-btn-list').classList.add('active');
            updateView();
        });

        updateView();
    },

    renderGrid(characters) {
        if (characters.length === 0) return '<div class="empty-msg">找不到符合條件的角色</div>';
        
        return characters.map(c => {
            const avatarHtml = window.AvatarService.getAvatarHtmlByUnitId(c.unit_id, c.unit_name);

            return `
                <div class="char-card glass-card" onclick="CharactersModule.showDetail(${c.unit_id})">
                    <div class="char-avatar">
                        ${avatarHtml}
                    </div>
                    <div class="char-info">
                        <div class="char-name">${c.unit_name}</div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 5px;">ID: ${c.unit_id}</div>
                        <div class="char-meta">
                            <span>站位: ${c.pos || '??'}</span>
                            <span>${c.race || ''}</span>
                        </div>
                        <div class="char-guild">${c.guild || '無所屬'}</div>
                    </div>
                </div>
            `;
        }).join('');
    },

    renderTable(characters) {
        if (characters.length === 0) return '<div class="empty-msg">找不到符合條件的角色</div>';

        return `
            <table class="char-table">
                <thead>
                    <tr>
                        <th style="width: 80px;">頭像</th>
                        <th style="width: 120px;">Unit ID</th>
                        <th>角色名稱</th>
                        <th>站位</th>
                        <th>種族</th>
                        <th>公會</th>
                        <th style="width: 120px; text-align: center;">隱藏卡片 🚫</th>
                    </tr>
                </thead>
                <tbody>
                    ${characters.map(c => {
                        const avatarHtml = window.AvatarService.getAvatarHtmlByUnitId(c.unit_id, c.unit_name);
                        const isExcluded = this.excludedUnitIds.has(c.unit_id);

                        return `
                            <tr onclick="CharactersModule.showDetail(${c.unit_id})">
                                <td class="cell-avatar">
                                    <div class="char-table-avatar">
                                        ${avatarHtml}
                                    </div>
                                </td>
                                <td class="cell-id">${c.unit_id}</td>
                                <td class="cell-name">${c.unit_name}</td>
                                <td class="cell-pos">${c.pos || '??'}</td>
                                <td>${c.race || ''}</td>
                                <td class="cell-guild">${c.guild || '無所屬'}</td>
                                <td style="text-align: center;" onclick="event.stopPropagation()">
                                    <input type="checkbox" style="width: 18px; height: 18px; cursor: pointer;" ${isExcluded ? 'checked' : ''} onchange="CharactersModule.toggleExclude(${c.unit_id}, event)">
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    },

    async showDetail(unitId) {
        this.activeUnitId = unitId;
        const modal = document.getElementById('char-detail-modal');
        const body = document.getElementById('modal-body');
        modal.classList.add('active');
        body.innerHTML = '<div class="loading-mini">讀取角色詳情中...</div>';

        try {
            // 1. 取得詳細數值與成長值
            const stats = window.PCRDatabase.runQuery(`
                SELECT * FROM unit_rarity WHERE unit_id = ? ORDER BY rarity DESC LIMIT 1
            `, [unitId])[0] || window.PCRDatabase.runQuery(`
                SELECT * FROM unit_data WHERE unit_id = ?
            `, [unitId])[0];

            const unitData = window.PCRDatabase.runQuery(`
                SELECT search_area_width FROM unit_data WHERE unit_id = ?
            `, [unitId])[0];

            // 2. 取得技能 ID
            const skillIds = window.PCRDatabase.runQuery(`
                SELECT * FROM unit_skill_data WHERE unit_id = ?
            `, [unitId])[0];

            // 3. 取得動作循環
            const attackPattern = window.PCRDatabase.runQuery(`
                SELECT * FROM unit_attack_pattern WHERE unit_id = ?
            `, [unitId])[0];

            // 4. 取得技能詳情
            const skills = [];
            const skillMap = {}; 
            if (skillIds) {
                const sids = [
                    { id: skillIds.union_burst, label: '必殺技 (UB)', key: 'ub' },
                    { id: skillIds.main_skill_1, label: '技能 1', key: '1001' },
                    { id: skillIds.main_skill_2, label: '技能 2', key: '1002' },
                    { id: skillIds.ex_skill_1, label: 'EX 技能', key: 'ex' }
                ];
                
                for (const s of sids) {
                    if (s.id) {
                        const sInfo = window.PCRDatabase.runQuery(`SELECT name, description, icon_type FROM skill_data WHERE skill_id = ?`, [s.id])[0];
                        if (sInfo) {
                            const fullSkill = { ...sInfo, label: s.label };
                            skills.push(fullSkill);
                            skillMap[s.key] = fullSkill;
                        }
                    }
                }

                // 載入所有 main_skill_X (1~10) 供動作循環對照
                for (let i = 1; i <= 10; i++) {
                    const skillId = skillIds[`main_skill_${i}`];
                    if (skillId && !skillMap[String(1000 + i)]) {
                        const sInfo = window.PCRDatabase.runQuery(`SELECT name, description, icon_type FROM skill_data WHERE skill_id = ?`, [skillId])[0];
                        if (sInfo) {
                            skillMap[String(1000 + i)] = sInfo;
                        }
                    }
                }

                // 載入所有 sp_skill_X (1~5) 供動作循環對照
                for (let i = 1; i <= 5; i++) {
                    const skillId = skillIds[`sp_skill_${i}`];
                    if (skillId && !skillMap[String(2000 + i)]) {
                        const sInfo = window.PCRDatabase.runQuery(`SELECT name, description, icon_type FROM skill_data WHERE skill_id = ?`, [skillId])[0];
                        if (sInfo) {
                            skillMap[String(2000 + i)] = sInfo;
                        }
                    }
                }
            }

            // 5. 渲染詳情
            const baseId = Math.floor(unitId / 100) * 100;
            const profile = this.allCharacters.find(c => c.unit_id === unitId);
            
            this.currentStats = stats;
            const maxLevel = window.PCRDatabase.currentRegion === 'jp' ? 305 : 280;

            const gameName = profile ? profile.unit_name : '角色詳情';
            
            // 輔助函數：解析角色名字的括號後綴
            const parseCharaName = (fullName) => {
                const match = fullName.match(/^(.+?)([(\uff08].+?[)\uff09])$/);
                if (match) {
                    return { baseName: match[1].trim(), suffix: match[2].trim() };
                }
                return { baseName: fullName.trim(), suffix: "" };
            };

            const parsed = parseCharaName(gameName);
            let realName = "";
            if (this.realNameMap) {
                const found = Object.entries(this.realNameMap).find(([real, game]) => game === parsed.baseName);
                if (found) {
                    realName = found[0] + parsed.suffix;
                }
            }

            const toggleBtn = realName ? `
                <button id="char-name-toggle-btn" class="part-btn" 
                        style="font-size: 0.75rem; padding: 4px 10px; border-radius: 6px; background: rgba(232,56,117,0.1); border: 1px solid rgba(232,56,117,0.3); color: var(--accent-color); cursor: pointer; transition: all 0.2s;"
                        onclick="CharactersModule.toggleNameDisplay('${gameName.replace(/'/g, "\\'")}', '${realName.replace(/'/g, "\\'")}')">
                    🔍 顯示真名
                </button>
            ` : '';

            body.innerHTML = `
                <div class="detail-header">
                    <div class="detail-avatar" style="overflow: hidden; display: flex; align-items: center; justify-content: center; padding: 0;">
                        ${window.AvatarService.getAvatarHtmlByUnitId(unitId, gameName)}
                    </div>
                    <div class="detail-main-info">
                        <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;">
                            <h2 style="margin: 0; display: flex; align-items: center; gap: 8px;">${gameName} <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: normal;">(ID: ${unitId})</span></h2>
                            ${toggleBtn}
                            <div class="level-input-group">
                                <span>Lv.</span>
                                <input type="number" id="detail-level" value="${maxLevel}" min="1" max="400" 
                                       oninput="CharactersModule.updateCalculatedStats(this.value)">
                            </div>
                        </div>
                        <div class="char-meta">
                            <span>站位: ${unitData ? unitData.search_area_width : '??'}</span>
                            <span>${profile ? profile.race : ''}</span>
                            <span>${profile ? profile.guild : ''}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-tabs" style="display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid var(--glass-border);">
                    <button id="modal-tab-stats" class="tab-btn active" onclick="CharactersModule.switchModalTab('stats')">核心數值與技能</button>
                    <button id="modal-tab-pattern" class="tab-btn" onclick="CharactersModule.switchModalTab('pattern')">動作循環</button>
                </div>

                <div id="modal-content-stats">
                    <h3>核心數值 (計算結果)</h3>
                    <div id="stats-display-grid" class="stats-grid"></div>

                    <div class="skill-section">
                        <h3>技能介紹</h3>
                        ${skills.map(s => `
                            <div class="skill-item">
                                <div class="skill-icon" style="width: 50px; height: 50px; border-radius: 8px; overflow: hidden; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                                    ${window.AvatarService.getSkillIconHtml(s.icon_type)}
                                </div>
                                <div class="skill-info">
                                    <div class="skill-label" style="font-size: 0.7rem; color: var(--accent-color); font-weight: bold;">${s.label}</div>
                                    <div class="skill-name">${s.name}</div>
                                    <div class="skill-desc">${s.description.replace(/\\n/g, '<br>')}</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div id="modal-content-pattern" style="display: none;">
                    <h3>動作循環模式</h3>
                    ${this.renderAttackPattern(attackPattern, skillMap)}
                </div>
            `;

            this.updateCalculatedStats(maxLevel);

        } catch (error) {
            console.error(error);
            body.innerHTML = `<div class="error-box">詳情載入失敗: ${error.message}</div>`;
        }
    },

    switchModalTab(tab) {
        document.getElementById('modal-content-stats').style.display = tab === 'stats' ? 'block' : 'none';
        document.getElementById('modal-content-pattern').style.display = tab === 'pattern' ? 'block' : 'none';
        document.getElementById('modal-tab-stats').classList.toggle('active', tab === 'stats');
        document.getElementById('modal-tab-pattern').classList.toggle('active', tab === 'pattern');
    },

    renderAttackPattern(pattern, skillMap) {
        if (!pattern) return '<div class="empty-msg">找不到動作循環數據</div>';

        const items = [];
        for (let i = 1; i <= 20; i++) {
            const act = pattern[`atk_pattern_${i}`];
            if (act === undefined || act === null || act === 0) break;
            items.push({ id: act, index: i });
        }

        const loopStart = pattern.loop_start;
        const loopEnd = pattern.loop_end;

        return `
            <div class="pattern-container">
                ${items.map(item => {
                    const isLoop = item.index >= loopStart && item.index <= loopEnd;
                    let iconHtml = '';
                    let name = '';
                    
                    if (item.id === 1) {
                        name = '普通攻擊';
                        // 漂亮且具質感的單手劍 SVG 作為普通攻擊圖示
                        iconHtml = `
                            <div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, rgba(73, 80, 87, 0.4), rgba(52, 58, 64, 0.6));">
                                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="rgba(255,255,255,0.7)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                    <line x1="18" y1="2" x2="22" y2="6"></line>
                                    <path d="M7.5 20.5 2 22l1.5-5.5L17 3.5 20.5 7z"></path>
                                </svg>
                            </div>
                        `;
                    } else {
                        const skillKey = String(item.id);
                        if (skillMap[skillKey]) {
                            iconHtml = window.AvatarService.getSkillIconHtml(skillMap[skillKey].icon_type);
                            name = skillMap[skillKey].name;
                        } else {
                            // 當在 skillMap 找不到時（例如 1003, 1004, 2001），先當作 icon_type 去嘗試載入（它會自動嘗試本地、So-net、最後去日版 EsterTion 下載！）
                            iconHtml = window.AvatarService.getSkillIconHtml(item.id);
                            name = `技能 ${item.id}`;
                        }
                    }

                    return `
                        <div class="pattern-item" style="${isLoop ? 'border: 2px solid var(--accent-color); background: rgba(255,107,157,0.1);' : 'border: 1px solid rgba(255,255,255,0.05);'}">
                            <div style="width: 40px; height: 40px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden; display: flex; align-items: center; justify-content: center;">
                                ${iconHtml}
                            </div>
                            <div style="font-size: 0.7rem; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: ${item.id > 1 ? '#ffa94d' : 'inherit'}">${name}</div>
                            <div style="font-size: 0.6rem; color: var(--text-secondary); margin-top: 2px;">${item.index}</div>
                        </div>
                    `;
                }).join('')}
            </div>
            <div style="margin-top: 15px; font-size: 0.85rem; color: var(--accent-color);">
                💡 框線部分為循環區間 (Step ${loopStart} ~ ${loopEnd})
            </div>
        `;
    },

    updateCalculatedStats(level) {
        const lv = parseInt(level) || 1;
        const stats = this.currentStats;
        if (!stats) return;

        const grid = document.getElementById('stats-display-grid');
        const calc = (base, growth) => Math.floor((base || 0) + (lv - 1) * (growth || 0));

        grid.innerHTML = `
            ${this.renderStat('HP', calc(stats.hp, stats.hp_growth))}
            ${this.renderStat('物理攻擊', calc(stats.atk, stats.atk_growth))}
            ${this.renderStat('魔法攻擊', calc(stats.magic_str, stats.magic_str_growth))}
            ${this.renderStat('物理防禦', calc(stats.def, stats.def_growth))}
            ${this.renderStat('魔法防禦', calc(stats.magic_def, stats.magic_def_growth))}
            ${this.renderStat('物理暴擊', calc(stats.physical_critical, stats.physical_critical_growth))}
            ${this.renderStat('魔法暴擊', calc(stats.magic_critical, stats.magic_critical_growth))}
            ${this.renderStat('吸血', calc(stats.life_steal, stats.life_steal_growth))}
        `;
    },

    renderStat(label, value) {
        return `
            <div class="stat-box">
                <span class="label">${label}</span>
                <span class="value">${value}</span>
            </div>
        `;
    },

    closeDetail() {
        document.getElementById('char-detail-modal').classList.remove('active');
    },

    toggleExclude(unitId, event) {
        if (event) event.stopPropagation();
        if (this.excludedUnitIds.has(unitId)) {
            this.excludedUnitIds.delete(unitId);
        } else {
            this.excludedUnitIds.add(unitId);
        }
        localStorage.setItem('excluded_unit_ids', JSON.stringify([...this.excludedUnitIds]));
        if (typeof this.updateView === 'function') {
            this.updateView();
        }
    },

    toggleNameDisplay(gameName, realName) {
        const titleEl = document.querySelector('.detail-main-info h2');
        const btn = document.getElementById('char-name-toggle-btn');
        if (!titleEl || !btn) return;
        
        const isShowingReal = btn.innerText.includes('遊戲名');
        if (isShowingReal) {
            titleEl.innerHTML = `${gameName} <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: normal;">(ID: ${this.activeUnitId})</span>`;
            btn.innerText = `🔍 顯示真名`;
        } else {
            titleEl.innerHTML = `${realName} <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: normal;">(ID: ${this.activeUnitId})</span>`;
            btn.innerText = `🎮 顯示遊戲名`;
        }
    }
};
