console.log("characters.js loaded");

window.CharactersModule = {
    allCharacters: [],
    viewMode: 'grid',
    realNameMap: null,
    activeUnitId: null,
    _searchDebounceTimer: null,
    excludedUnitIds: (() => {
        try {
            const saved = JSON.parse(localStorage.getItem('excluded_unit_ids') || '[]');
            return new Set(Array.isArray(saved) ? saved.map(String) : []);
        } catch (_) { return new Set(); }
    })(),
    
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

            this.allCharacters = (data || []).map(c => ({
                ...c,
                unit_id: String(c.unit_id)
            }));
            this.allCharacters.sort((a, b) => Number(b.unit_id) - Number(a.unit_id));
            
            this.renderLayout(container);
        } catch (error) {
            console.error("Data Cleanup Error:", error);
            container.innerHTML = `<div class="error-box">數據清洗失敗: ${error.message}</div>`;
        }
    },

    renderLayout(container) {
        container.innerHTML = `
            <div class="gallery-header glass-card" style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                    <div style="display: flex; align-items: center; gap: 20px;">
                        <h2 style="margin: 0;">角色圖鑑 (${window.PCRDatabase.currentRegion.toUpperCase()})</h2>
                        <select id="char-sort" class="region-select" style="background-image: none; padding-right: 12px;">
                            <option value="id-desc" selected>ID 排序（大→小）</option>
                            <option value="id-asc">ID 排序（小→大）</option>
                            <option value="pos-asc">角色站位 (前→後)</option>
                        </select>
                    </div>
                    <div class="search-box" style="display: flex; align-items: center; gap: 10px;">
                        <input type="text" id="char-search" placeholder="搜尋角色名稱..." class="region-select" style="width: 250px; background-image: none; padding-right: 12px;">
                        <div class="view-toggle-group">
                            <button id="view-btn-grid" class="view-btn ${this.viewMode === 'grid' ? 'active' : ''}" title="卡片視圖">🎴 卡片</button>
                            <button id="view-btn-list" class="view-btn ${this.viewMode === 'list' ? 'active' : ''}" title="列表視圖">📋 列表</button>
                            <button id="view-btn-guild" class="view-btn ${this.viewMode === 'guild' ? 'active' : ''}" title="世界公會">🏰 公會</button>
                        </div>
                    </div>
                </div>
            </div>
            <div id="char-grid" class="char-grid"></div>
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
            } else if (this.viewMode === 'list') {
                displayContainer.className = 'char-table-container';
                displayContainer.innerHTML = this.renderTable(filtered);
            } else {
                displayContainer.className = 'char-guild-container';
                displayContainer.innerHTML = this.renderGuildView(filtered);
            }
        };

        const updateView = this.updateView;
        const searchInput = document.getElementById('char-search');

        if (this._searchDebounceTimer) {
            clearTimeout(this._searchDebounceTimer);
            this._searchDebounceTimer = null;
        }

        searchInput.addEventListener('input', () => {
            if (this._searchDebounceTimer) clearTimeout(this._searchDebounceTimer);
            this._searchDebounceTimer = setTimeout(() => {
                this._searchDebounceTimer = null;
                updateView();
            }, 150);
        });
        document.getElementById('char-sort').addEventListener('change', updateView);

        document.getElementById('view-btn-grid').addEventListener('click', () => {
            this.viewMode = 'grid';
            document.getElementById('view-btn-grid').classList.add('active');
            document.getElementById('view-btn-list').classList.remove('active');
            document.getElementById('view-btn-guild').classList.remove('active');
            updateView();
        });
        document.getElementById('view-btn-list').addEventListener('click', () => {
            this.viewMode = 'list';
            document.getElementById('view-btn-grid').classList.remove('active');
            document.getElementById('view-btn-list').classList.add('active');
            document.getElementById('view-btn-guild').classList.remove('active');
            updateView();
        });
        document.getElementById('view-btn-guild').addEventListener('click', () => {
            this.viewMode = 'guild';
            document.getElementById('view-btn-grid').classList.remove('active');
            document.getElementById('view-btn-list').classList.remove('active');
            document.getElementById('view-btn-guild').classList.add('active');
            updateView();
        });

        updateView();
    },

    renderGrid(characters) {
        if (characters.length === 0) return '<div class="empty-msg">找不到符合條件的角色</div>';
        
        return characters.map(c => {
            const avatarHtml = window.AvatarService.getCharacterCardAvatarHtml(c.unit_id, c.unit_name);

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
                        const avatarHtml = window.AvatarService.getCharacterCardAvatarHtml(c.unit_id, c.unit_name);
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
        this.activeUnitId = String(unitId);
        const modal = document.getElementById('char-detail-modal');
        const body = document.getElementById('modal-body');
        modal.classList.add('active');
        body.innerHTML = '<div class="loading-mini">讀取角色詳情中...</div>';

        try {
            // 1. 取得詳細數值與成長值 (僅來自 unit_rarity，嚴禁以 unit_data 作為 fallback)
            const stats = window.PCRDatabase.runQuery(`
                SELECT * FROM unit_rarity WHERE unit_id = ? ORDER BY rarity DESC LIMIT 1
            `, [unitId])[0] || null;

            const unitData = window.PCRDatabase.runQuery(`
                SELECT search_area_width FROM unit_data WHERE unit_id = ?
            `, [unitId])[0] || null;

            // 2. 取得技能 ID
            const skillIds = window.PCRDatabase.runQuery(`
                SELECT * FROM unit_skill_data WHERE unit_id = ?
            `, [unitId])[0];

            // 3. 取得所有動作循環 (依 pattern_id 升冪排序)
            const attackPatterns = window.PCRDatabase.runQuery(`
                SELECT * FROM unit_attack_pattern WHERE unit_id = ? ORDER BY pattern_id ASC
            `, [unitId]) || [];

            // 3.1 取得平衡調整對照資料
            const rfRows = window.PCRDatabase.runQuery(`
                SELECT skill_id, rf_skill_id FROM unit_skill_data_rf
            `) || [];
            const rfSkillMap = new Map();
            for (const r of rfRows) {
                rfSkillMap.set(Number(r.skill_id), Number(r.rf_skill_id));
            }

            // 3.2 取得專屬裝備 (專1 / 專2)
            const uniqueEquips = window.PCRDatabase.runQuery(`
                SELECT u.equip_slot, e.* 
                FROM unit_unique_equipment u 
                JOIN unique_equipment_data e ON u.equip_id = e.equipment_id 
                WHERE u.unit_id = ? 
                ORDER BY u.equip_slot ASC
            `, [unitId]) || [];

            // 4. 取得技能詳情與形態變體
            const skillSlots = [];
            const skillMap = {}; 

            const fetchSkillMeta = (sId) => {
                if (!sId || Number(sId) === 0) return null;
                const r = window.PCRDatabase.runQuery(
                    `SELECT skill_id, name, description, icon_type FROM skill_data WHERE skill_id = ?`,
                    [sId]
                )[0];
                return r || null;
            };

            if (skillIds) {
                const rawSlots = [
                    {
                        key: 'ub',
                        label: '必殺技 (UB)',
                        patternKey: null,
                        candidateVariants: [
                            { id: skillIds.union_burst, tag: '基礎' },
                            { id: skillIds.union_burst_evolution, tag: '★6 UB' }
                        ]
                    },
                    {
                        key: '1001',
                        label: '技能 1',
                        patternKey: '1001',
                        candidateVariants: [
                            { id: skillIds.main_skill_1, tag: '基礎' },
                            { id: skillIds.main_skill_evolution_1, tag: '專武 1+' },
                            { id: skillIds.main_skill_evolution_1_pro, tag: '專武 1+ Pro' }
                        ]
                    },
                    {
                        key: '1002',
                        label: '技能 2',
                        patternKey: '1002',
                        candidateVariants: [
                            { id: skillIds.main_skill_2, tag: '基礎' },
                            { id: skillIds.main_skill_evolution_2, tag: '專武 2+' }
                        ]
                    },
                    {
                        key: 'ex',
                        label: 'EX 技能',
                        patternKey: null,
                        candidateVariants: [
                            { id: skillIds.ex_skill_1, tag: '基礎' },
                            { id: skillIds.ex_skill_evolution_1, tag: '★5 EX+' }
                        ]
                    }
                ];

                // 檢查是否具有 SP 形態技能 (例如變身或特定技能組)
                if (skillIds.sp_union_burst || skillIds.sp_skill_1) {
                    if (skillIds.sp_union_burst) {
                        rawSlots.push({
                            key: 'sp_ub',
                            label: 'SP 必殺技 (UB)',
                            patternKey: null,
                            candidateVariants: [{ id: skillIds.sp_union_burst, tag: 'SP' }]
                        });
                    }
                    if (skillIds.sp_skill_1) {
                        rawSlots.push({
                            key: '2001',
                            label: 'SP 技能 1',
                            patternKey: '2001',
                            candidateVariants: [
                                { id: skillIds.sp_skill_1, tag: 'SP' },
                                { id: skillIds.sp_skill_evolution_1, tag: 'SP 專武 1+' },
                                { id: skillIds.sp_skill_evolution_1_pro, tag: 'SP 專武 1+ Pro' }
                            ]
                        });
                    }
                    if (skillIds.sp_skill_2) {
                        rawSlots.push({
                            key: '2002',
                            label: 'SP 技能 2',
                            patternKey: '2002',
                            candidateVariants: [{ id: skillIds.sp_skill_2, tag: 'SP' }]
                        });
                    }
                    if (skillIds.sp_skill_3) {
                        rawSlots.push({
                            key: '2003',
                            label: 'SP 技能 3',
                            patternKey: '2003',
                            candidateVariants: [{ id: skillIds.sp_skill_3, tag: 'SP' }]
                        });
                    }
                }

                // 展開各槽位形態與平衡調整
                for (const raw of rawSlots) {
                    const resolvedVariants = [];
                    for (const cand of raw.candidateVariants) {
                        if (!cand.id || Number(cand.id) === 0) continue;
                        const meta = fetchSkillMeta(cand.id);
                        if (!meta) continue;

                        resolvedVariants.push({
                            id: cand.id,
                            tag: cand.tag,
                            isRf: false,
                            name: meta.name,
                            description: meta.description,
                            icon_type: meta.icon_type
                        });

                        // 檢查是否有平衡調整版本
                        const rfId = rfSkillMap.get(Number(cand.id));
                        if (rfId) {
                            const rfMeta = fetchSkillMeta(rfId);
                            if (rfMeta) {
                                resolvedVariants.push({
                                    id: rfId,
                                    tag: `${cand.tag} 平衡調整`,
                                    isRf: true,
                                    name: rfMeta.name,
                                    description: rfMeta.description,
                                    icon_type: rfMeta.icon_type
                                });
                            }
                        }
                    }

                    if (resolvedVariants.length > 0) {
                        // 預設選中最後一個形態 (最新/最高強化階層)
                        const activeIndex = resolvedVariants.length - 1;
                        const slotObj = {
                            key: raw.key,
                            label: raw.label,
                            patternKey: raw.patternKey,
                            variants: resolvedVariants,
                            activeIndex: activeIndex
                        };
                        skillSlots.push(slotObj);

                        // 填入動作循環對照表
                        if (raw.patternKey) {
                            skillMap[raw.patternKey] = resolvedVariants[activeIndex];
                        }
                    }
                }

                // 載入所有 main_skill_X (1~10) 供動作循環對照
                for (let i = 1; i <= 10; i++) {
                    const skillId = skillIds[`main_skill_${i}`];
                    if (skillId && !skillMap[String(1000 + i)]) {
                        const sInfo = fetchSkillMeta(skillId);
                        if (sInfo) {
                            skillMap[String(1000 + i)] = sInfo;
                        }
                    }
                }

                // 載入所有 sp_skill_X (1~5) 供動作循環對照
                for (let i = 1; i <= 5; i++) {
                    const skillId = skillIds[`sp_skill_${i}`];
                    if (skillId && !skillMap[String(2000 + i)]) {
                        const sInfo = fetchSkillMeta(skillId);
                        if (sInfo) {
                            skillMap[String(2000 + i)] = sInfo;
                        }
                    }
                }
            }

            this.currentSkillSlots = skillSlots;
            this.currentAttackPatterns = attackPatterns;
            this.currentSkillMap = skillMap;
            this.activePatternIndex = 0;

            // 5. 渲染詳情
            const baseId = Math.floor(Number(unitId) / 100) * 100;
            const profile = this.allCharacters.find(c => c.unit_id === String(unitId));
            
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

            // 輔助函式：渲染技能卡片
            const renderSkillSlotsHtml = (slots) => {
                if (!slots || slots.length === 0) {
                    return '<div style="color: var(--text-secondary); font-size: 0.85rem; padding: 10px 0;">暫無技能數據</div>';
                }
                return slots.map(slot => {
                    const activeVariant = slot.variants[slot.activeIndex];
                    const hasMultiple = slot.variants.length > 1;
                    return `
                        <div class="skill-item" id="skill-slot-${slot.key}">
                            <div class="skill-icon" id="skill-slot-icon-${slot.key}" style="width: 50px; height: 50px; border-radius: 8px; overflow: hidden; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                                ${window.AvatarService.getSkillIconHtml(activeVariant.icon_type)}
                            </div>
                            <div class="skill-info">
                                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;">
                                    <div class="skill-label" style="font-size: 0.72rem; color: var(--accent-color); font-weight: bold; display: flex; align-items: center;">
                                        ${slot.label}
                                        <span id="skill-slot-rf-badge-${slot.key}">${activeVariant.isRf ? '<span class="skill-rf-tag">⚖️ 平衡調整</span>' : ''}</span>
                                    </div>
                                    ${hasMultiple ? `
                                        <div class="skill-variant-group">
                                            ${slot.variants.map((v, vIdx) => `
                                                <button type="button" class="skill-pill-btn ${vIdx === slot.activeIndex ? 'active' : ''}" 
                                                        onclick="CharactersModule.selectSkillVariant('${slot.key}', ${vIdx})">
                                                    ${v.tag}
                                                </button>
                                            `).join('')}
                                        </div>
                                    ` : ''}
                                </div>
                                <div class="skill-name" id="skill-slot-name-${slot.key}">${activeVariant.name}</div>
                                <div class="skill-desc" id="skill-slot-desc-${slot.key}">${(activeVariant.description || '').replace(/\\n/g, '<br>')}</div>
                            </div>
                        </div>
                    `;
                }).join('');
            };

            // 輔助函式：渲染專屬裝備卡片
            const renderUniqueEquipHtml = (equips) => {
                if (!equips || equips.length === 0) return '';
                const STAT_NAMES = {
                    hp: 'HP',
                    atk: '物理攻擊力',
                    magic_str: '魔法攻擊力',
                    def: '物理防禦力',
                    magic_def: '魔法防禦力',
                    physical_critical: '物理暴擊',
                    magic_critical: '魔法暴擊',
                    dodge: '迴避',
                    life_steal: 'HP 吸收',
                    wave_hp_recovery: 'HP 回復',
                    energy_recovery_rate: 'TP 上升',
                    hp_recovery_rate: '回復量上升',
                    accuracy: '命中'
                };
                return `
                    <div class="unique-equip-section" style="margin-top: 30px;">
                        <h3 style="border-left: 4px solid #ffd43b; padding-left: 15px; margin: 25px 0 15px; color: #ffd43b;">專屬武器 (專屬裝備)</h3>
                        ${equips.map(eq => {
                            const slotName = Number(eq.equip_slot) === 2 ? '專屬裝備 2' : '專屬裝備 1';
                            const statBadges = [];
                            for (const [key, label] of Object.entries(STAT_NAMES)) {
                                const val = parseFloat(eq[key]);
                                if (val && val > 0) {
                                    statBadges.push(`<span class="unique-equip-stat-badge">${label} +${val}</span>`);
                                }
                            }
                            return `
                                <div class="unique-equip-card">
                                    <div class="unique-equip-icon">
                                        ${window.AvatarService.getEquipmentIconHtml(eq.equipment_id)}
                                    </div>
                                    <div class="unique-equip-info">
                                        <div class="unique-equip-title">
                                            <span class="unique-equip-slot-tag">【${slotName}】</span>
                                            <span>${eq.equipment_name}</span>
                                        </div>
                                        ${statBadges.length > 0 ? `<div class="unique-equip-stats">${statBadges.join('')}</div>` : ''}
                                        <div class="unique-equip-desc">${(eq.description || '').replace(/\\n/g, '<br>')}</div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `;
            };

            body.innerHTML = `
                <div class="detail-header">
                    <div class="detail-avatar" style="overflow: hidden; display: flex; align-items: center; justify-content: center; padding: 0;">
                        ${window.AvatarService.getCharacterCardAvatarHtml(unitId, gameName)}
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
                            <span>站位: ${(unitData && unitData.search_area_width) || (profile && profile.pos) || '??'}</span>
                            <span>${profile ? profile.race : ''}</span>
                            <span>${profile ? profile.guild : ''}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-tabs" style="display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid var(--glass-border);">
                    <button id="modal-tab-stats" class="tab-btn active" onclick="CharactersModule.switchModalTab('stats')">核心數值與技能</button>
                    <button id="modal-tab-pattern" class="tab-btn" onclick="CharactersModule.switchModalTab('pattern')">動作循環</button>
                    <button id="modal-tab-story" class="tab-btn" onclick="CharactersModule.switchModalTab('story')">個人劇情 (官方繁中)</button>
                </div>

                <div id="modal-content-stats">
                    ${stats ? `
                        <h3>核心數值 (計算結果)</h3>
                        <div id="stats-display-grid" class="stats-grid"></div>
                    ` : `
                        <div class="glass-card" style="padding: 20px; text-align: center; border-radius: 12px; margin-bottom: 20px; border: 1px dashed rgba(255,255,255,0.15);">
                            <div style="color: var(--accent-color); font-weight: 600; margin-bottom: 6px;">🎮 官方 CDN 先行預載角色</div>
                            <div style="font-size: 0.85rem; color: var(--text-secondary);">官方尚未開放此角色的戰鬥數據表，請點擊上方「個人劇情」標籤頁搶先閱讀 1～4 話完整繁中劇情與專屬 CG！</div>
                        </div>
                    `}

                    <div class="skill-section">
                        <h3>技能介紹</h3>
                        ${renderSkillSlotsHtml(skillSlots)}
                    </div>

                    ${renderUniqueEquipHtml(uniqueEquips)}
                </div>
 
                <div id="modal-content-pattern" style="display: none;">
                    <h3>動作循環模式</h3>
                    ${this.renderAttackPatternsView(attackPatterns, skillMap)}
                </div>

                <div id="modal-content-story" style="display: none;">
                    <!-- 個人劇情故事清單 -->
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
        document.getElementById('modal-content-story').style.display = tab === 'story' ? 'block' : 'none';
        
        document.getElementById('modal-tab-stats').classList.toggle('active', tab === 'stats');
        document.getElementById('modal-tab-pattern').classList.toggle('active', tab === 'pattern');
        document.getElementById('modal-tab-story').classList.toggle('active', tab === 'story');
        
        if (tab === 'story') {
            this.renderStoryList();
        }
    },

    selectSkillVariant(slotKey, variantIndex) {
        if (!this.currentSkillSlots) return;
        const slot = this.currentSkillSlots.find(s => s.key === slotKey);
        if (!slot || !slot.variants[variantIndex]) return;
        slot.activeIndex = variantIndex;
        const v = slot.variants[variantIndex];

        const iconEl = document.getElementById(`skill-slot-icon-${slotKey}`);
        const nameEl = document.getElementById(`skill-slot-name-${slotKey}`);
        const descEl = document.getElementById(`skill-slot-desc-${slotKey}`);
        const badgeEl = document.getElementById(`skill-slot-rf-badge-${slotKey}`);

        if (iconEl) iconEl.innerHTML = window.AvatarService.getSkillIconHtml(v.icon_type);
        if (nameEl) nameEl.textContent = v.name;
        if (descEl) descEl.innerHTML = (v.description || '').replace(/\n/g, '<br>');
        if (badgeEl) badgeEl.innerHTML = v.isRf ? '<span class="skill-rf-tag">⚖️ 平衡調整</span>' : '';

        const slotEl = document.getElementById(`skill-slot-${slotKey}`);
        if (slotEl) {
            const btns = slotEl.querySelectorAll('.skill-pill-btn');
            btns.forEach((b, idx) => {
                b.classList.toggle('active', idx === variantIndex);
            });
        }
    },

    selectPatternTab(patternIdx) {
        if (!this.currentAttackPatterns) return;
        this.currentAttackPatterns.forEach((_, idx) => {
            const btn = document.getElementById(`pattern-mode-btn-${idx}`);
            const panel = document.getElementById(`pattern-panel-${idx}`);
            if (btn) btn.classList.toggle('active', idx === patternIdx);
            if (panel) panel.style.display = idx === patternIdx ? '' : 'none';
        });
    },

    renderAttackPattern(pattern, skillMap) {
        return this.renderAttackPatternsView(pattern ? [pattern] : [], skillMap);
    },

    renderAttackPatternsView(patterns, skillMap) {
        if (!patterns || patterns.length === 0) return '<div class="empty-msg">找不到動作循環數據</div>';

        const tabsHtml = patterns.length > 1 ? `
            <div class="pattern-mode-tabs">
                ${patterns.map((p, idx) => `
                    <button type="button" class="pattern-mode-btn ${idx === 0 ? 'active' : ''}" 
                            id="pattern-mode-btn-${idx}"
                            onclick="CharactersModule.selectPatternTab(${idx})">
                        ${idx === 0 ? '常態模式 (循環 1)' : (idx === 1 ? '型態切換 / 變身 (循環 2)' : `特殊模式 (循環 ${idx + 1})`)}
                    </button>
                `).join('')}
            </div>
        ` : '';

        const panelsHtml = patterns.map((pattern, pIdx) => {
            const items = [];
            for (let i = 1; i <= 20; i++) {
                const act = pattern[`atk_pattern_${i}`];
                if (act === undefined || act === null || act === 0) break;
                items.push({ id: act, index: i });
            }

            const loopStart = pattern.loop_start;
            const loopEnd = pattern.loop_end;

            return `
                <div class="pattern-panel" id="pattern-panel-${pIdx}" style="${pIdx === 0 ? '' : 'display: none;'}">
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
                </div>
            `;
        }).join('');

        return `
            ${tabsHtml}
            ${panelsHtml}
        `;
    },

    toFiniteStat(value) {
        if (value === null || value === undefined || value === '') {
            return null;
        }
        const n = Number(value);
        return Number.isFinite(n) ? n : null;
    },

    calcStat(base, growth, level) {
        const b = this.toFiniteStat(base);
        const g = this.toFiniteStat(growth);
        if (b === null || g === null) {
            return null;
        }
        const lv = parseInt(level, 10);
        const validLv = Number.isFinite(lv) && lv >= 1 ? lv : 1;
        const result = Math.floor(b + (validLv - 1) * g);
        return Number.isFinite(result) ? result : null;
    },

    updateCalculatedStats(level) {
        const stats = this.currentStats;
        if (!stats) return;

        const grid = document.getElementById('stats-display-grid');
        const calc = (base, growth) => this.calcStat(base, growth, level);

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
        const safeValue = (value !== null && value !== undefined && Number.isFinite(Number(value)))
            ? value
            : '—';
        return `
            <div class="stat-box">
                <span class="label">${label}</span>
                <span class="value">${safeValue}</span>
            </div>
        `;
    },

    closeDetail() {
        document.getElementById('char-detail-modal').classList.remove('active');
    },

    toggleExclude(unitId, event) {
        if (event) event.stopPropagation();
        const canonicalId = String(unitId);
        if (this.excludedUnitIds.has(canonicalId)) {
            this.excludedUnitIds.delete(canonicalId);
        } else {
            this.excludedUnitIds.add(canonicalId);
        }
        try {
            localStorage.setItem('excluded_unit_ids', JSON.stringify([...this.excludedUnitIds]));
        } catch (_) {
            console.warn('[CharactersModule] 本次篩選仍有效，但無法保存設定。');
        }
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
    },

    categorizeCharacters(characters) {
        const worlds = {
            'Astraea': { name: '阿斯特萊亞', desc: '阿斯特萊亞大陸，冒險的起點與主舞台', bg: 'linear-gradient(135deg, rgba(255, 107, 157, 0.08) 0%, rgba(255, 230, 235, 0.03) 100%)', guilds: {} },
            'GeoTheogonia': { name: '吉歐‧提格尼亞', desc: '芭菲與糖果的和平地底世界', bg: 'linear-gradient(135deg, rgba(255, 192, 203, 0.08) 0%, rgba(255, 240, 245, 0.03) 100%)', guilds: {} },
            'GeoGehenna': { name: '吉歐‧格黑納', desc: '弱肉強食的魔能與妖魔人煉獄世界', bg: 'linear-gradient(135deg, rgba(149, 117, 205, 0.08) 0%, rgba(237, 231, 246, 0.03) 100%)', guilds: {} },
            'GeoNibelheim': { name: '吉歐‧尼布爾黑爾', desc: '永無天日的幽暗永夜共治世界', bg: 'linear-gradient(135deg, rgba(79, 195, 247, 0.08) 0%, rgba(225, 245, 254, 0.03) 100%)', guilds: {} },
            'Other': { name: '其他世界', desc: '來自異世界的聯動旅行者與其他合作角色', bg: 'linear-gradient(135deg, rgba(77, 182, 172, 0.08) 0%, rgba(224, 242, 241, 0.03) 100%)', guilds: {} }
        };

        // 常規公會到世界的映射
        const guildToWorld = {
            '美食殿堂': 'Astraea',
            '破曉之星': 'Astraea',
            '小小甜心': 'Astraea',
            '王宮騎士團': 'Astraea',
            '惡魔偽王國軍': 'Astraea',
            '純白之翼 蘭德索爾分部': 'Astraea',
            '暮光流星群': 'Astraea',
            '哞哞自衛隊': 'Astraea',
            '拉比林斯': 'Astraea',
            '森林守衛': 'Astraea',
            '月光學院': 'Astraea',
            '咲戀育幼院': 'Astraea',
            '伊麗莎白牧場': 'Astraea',
            '慈樂之音': 'Astraea',
            '墨丘利財團': 'Astraea',
            '龍族巢穴': 'Astraea',
            '聖德蕾莎女子學院（好朋友社）': 'Astraea',
            '里士滿工商會': 'Astraea',
            '憤怒‧軍團': 'Astraea',
            '蠻賊三姊妹': 'Astraea',
            '阿爾克絲鍊金堂': 'Astraea',
            '森林守衛、伊麗莎白牧場': 'Astraea',
            '墨丘利財團、咲戀育幼院': 'Astraea',
            
            '吉歐‧提格尼亞': 'GeoTheogonia',
            '幻變少女': 'GeoTheogonia',
            
            'new generations': 'Other'
        };

        // 手動指定角色到特定的世界/公會 (模糊匹配名字，去掉括號)
        const charWorldOverrides = {
            // 吉歐‧提格尼亞
            '萊拉耶爾': { world: 'GeoTheogonia', guild: '吉歐‧提格尼亞' },
            '庫露露': { world: 'GeoTheogonia', guild: '吉歐‧提格尼亞' },
            '莉莉': { world: 'GeoTheogonia', guild: '幻變少女' },
            '克羅榭': { world: 'GeoTheogonia', guild: '幻變少女' },
            '普蕾希亞': { world: 'GeoTheogonia', guild: '幻變少女' },
            '普蕾西亞': { world: 'GeoTheogonia', guild: '幻變少女' },
            '可璃亞': { world: 'GeoTheogonia', guild: '幻變少女' },
            
            // 吉歐‧格黑納
            '涅妃＝涅羅': { world: 'GeoGehenna', guild: '無公會' },
            '涅妃': { world: 'GeoGehenna', guild: '無公會' },
            '華音': { world: 'GeoGehenna', guild: '無公會' },
            '鳳凰': { world: 'GeoGehenna', guild: '無公會' },
            '阿剌克涅': { world: 'GeoGehenna', guild: '無公會' },
            '拿娜': { world: 'GeoGehenna', guild: '無公會' },
            
            // 吉歐‧尼布爾黑爾
            '薇歐莉特': { world: 'GeoNibelheim', guild: '無公會' },
            '雪野': { world: 'GeoNibelheim', guild: '無公會' },
            '剎鬼': { world: 'GeoNibelheim', guild: '無公會' },
            '格蕾斯': { world: 'GeoNibelheim', guild: '無公會' },

            // 阿斯特萊亞
            '志那都': { world: 'Astraea', guild: '無公會' },
            '埃拉': { world: 'Astraea', guild: '無公會' },

            // 其他世界 (聯動)
            '吉塔': { world: 'Other', guild: '碧藍幻想' },
            '亞里莎': { world: 'Other', guild: '影之詩' },
            '露娜': { world: 'Other', guild: '影之詩' },
            '班比': { world: 'Other', guild: '巴哈姆特之怒' },
            '梅杜莎': { world: 'Other', guild: '巴哈姆特之怒' },
            '安': { world: 'Other', guild: '馬納歷亞魔法學院' },
            '古蕾婭': { world: 'Other', guild: '馬納歷亞魔法學院' },
            '露': { world: 'Other', guild: '馬納歷亞魔法學院' },
            '雷姆': { world: 'Other', guild: 'Re:從零開始的異世界生活' },
            '拉姆': { world: 'Other', guild: 'Re:從零開始的異世界生活' },
            '愛蜜莉雅': { world: 'Other', guild: 'Re:從零開始的異世界生活' },
            '艾姬多娜': { world: 'Other', guild: 'Re:從零開始的異世界生活' },
            '拉芙塔莉雅': { world: 'Other', guild: '盾之勇者成名錄' },
            '菲洛': { world: 'Other', guild: '盾之勇者成名錄' },
            '櫻': { world: 'Other', guild: '佐賀偶像是傳奇' }
        };

        characters.forEach(c => {
            let worldKey = 'Astraea';
            let guildName = c.guild || '無公會';

            // 去掉名字中括號的後綴（例如「萊拉耶爾（聖誕節）」 -> 「萊拉耶爾」）
            const baseName = c.unit_name.replace(/[\uff08(\uff09)].*$/g, '').trim();

            // 檢查手動指定
            const override = charWorldOverrides[baseName] || charWorldOverrides[c.unit_name];
            if (override) {
                worldKey = override.world;
                guildName = override.guild;
            } else if (guildToWorld[c.guild]) {
                worldKey = guildToWorld[c.guild];
                guildName = c.guild;
            } else {
                if (c.guild === '？？？') {
                    guildName = '無公會';
                    worldKey = 'Astraea';
                }
            }

            if (!worlds[worldKey].guilds[guildName]) {
                worlds[worldKey].guilds[guildName] = [];
            }
            worlds[worldKey].guilds[guildName].push(c);
        });

        return worlds;
    },

    renderGuildView(characters) {
        const worlds = this.categorizeCharacters(characters);
        
        let html = '<div class="worlds-wrapper" style="display: flex; flex-direction: column; gap: 20px; width: 100%;">';
        
        for (const [key, w] of Object.entries(worlds)) {
            const guildCount = Object.keys(w.guilds).length;
            const totalChars = Object.values(w.guilds).reduce((sum, list) => sum + list.length, 0);
            if (totalChars === 0) continue;

            html += `
                <div class="world-card glass-card" style="background: ${w.bg}; border-radius: 20px; overflow: hidden; border: 1px solid var(--glass-border); box-shadow: var(--card-shadow); transition: all 0.3s ease;">
                    <div class="world-header" onclick="const content = document.getElementById('world-content-${key}'); content.classList.toggle('collapsed'); this.classList.toggle('expanded')" 
                         style="padding: 20px 24px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none; border-bottom: 1px solid rgba(255,255,255,0.03);">
                        <div>
                            <h3 style="margin: 0; font-size: 1.25rem; color: var(--accent-color); font-weight: 700; letter-spacing: 0.5px;">${w.name}</h3>
                            <div style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 5px; opacity: 0.85;">${w.desc}</div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 15px;">
                            <span style="font-size: 0.8rem; background: rgba(255, 255, 255, 0.05); padding: 5px 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.06); color: var(--text-primary); font-weight: 500;">
                                ${guildCount} 個分組 / ${totalChars} 名成員
                            </span>
                            <span class="chevron" style="transition: transform 0.3s ease; font-size: 1rem; color: var(--text-secondary); display: inline-block;">▼</span>
                        </div>
                    </div>
                    
                    <div id="world-content-${key}" class="world-content" style="padding: 0 24px 24px; max-height: 5000px; transition: max-height 0.4s ease-in-out; overflow: hidden;">
                        <div class="guilds-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-top: 20px;">
                            ${Object.entries(w.guilds).map(([guildName, list]) => {
                                return `
                                    <div class="guild-box glass-card" style="padding: 16px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.015); display: flex; flex-direction: column; gap: 12px; transition: var(--transition);">
                                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 10px;">
                                            <h4 style="margin: 0; font-size: 0.95rem; color: var(--text-primary); font-weight: 600;">${guildName}</h4>
                                            <span style="font-size: 0.75rem; color: var(--text-secondary); font-weight: 500; background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 8px;">${list.length} 人</span>
                                        </div>
                                        <div class="guild-members" style="display: flex; flex-wrap: wrap; gap: 8px;">
                                            ${list.map(c => {
                                                const avatarHtml = window.AvatarService.getCharacterCardAvatarHtml(c.unit_id, c.unit_name);
                                                return `
                                                    <div class="member-avatar-wrapper" onclick="CharactersModule.showDetail(${c.unit_id})" 
                                                         title="${c.unit_name} (ID: ${c.unit_id})" 
                                                         style="cursor: pointer; transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275); position: relative;">
                                                        <div class="guild-member-avatar" style="width: 44px; height: 44px; border-radius: 10px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 2px 6px rgba(0,0,0,0.15);">
                                                            ${avatarHtml}
                                                        </div>
                                                    </div>
                                                `;
                                            }).join('')}
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        return html;
    },

    currentAudio: null,

    async renderStoryList() {
        const container = document.getElementById('modal-content-story');
        if (!container) return;
        
        container.innerHTML = '<div class="loading-mini" style="text-align: center; padding: 20px;">載入劇情清單中...</div>';
        
        const unitId = this.activeUnitId;
        // 取得前四位數作為個人劇情的字首，例如 105801 -> 1058%
        const storyPrefix = String(unitId).substring(0, 4);
        
        try {
            let stories = window.PCRDatabase.runQuery(`
                SELECT story_id, title, sub_title 
                FROM story_detail 
                WHERE CAST(story_id AS TEXT) LIKE ? 
                ORDER BY story_id ASC
            `, [storyPrefix + "%"]);
            
            // 若資料庫尚未收錄新角色個人劇情，自動從本地對白目錄構建 1~4 話
            if (!stories || stories.length === 0) {
                const charObj = this.allCharacters.find(c => c.unit_id === unitId);
                const charName = charObj ? charObj.unit_name : "角色";
                stories = [1, 2, 3, 4].map(ep => ({
                    story_id: parseInt(`${storyPrefix}00${ep}`),
                    title: `${charName} 第${ep}話`,
                    sub_title: `第 ${ep} 話`
                }));
            }
            
            container.innerHTML = `
                <div class="story-list" style="display: flex; flex-direction: column; gap: 10px; margin-top: 10px;">
                    ${stories.map(s => `
                        <div class="story-item glass-card" style="border: 1px solid var(--glass-border); border-radius: 12px; overflow: hidden; transition: var(--transition);">
                            <div class="story-header" onclick="CharactersModule.toggleStoryDialogue(${s.story_id})" 
                                 style="padding: 15px 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none; background: rgba(255,255,255,0.015);">
                                <div>
                                    <h4 style="margin: 0; font-size: 0.95rem; color: var(--text-primary); font-weight: 600;">${s.title}</h4>
                                    <div style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 4px;">${s.sub_title}</div>
                                </div>
                                <div style="display: flex; align-items: center;">
                                    <button class="play-story-btn active-hover-effect" onclick="event.stopPropagation(); CharactersModule.jumpToStoryPlayer(${s.story_id})" 
                                            style="border: none; background: linear-gradient(135deg, var(--accent-color), #f75c8d); color: white; border-radius: 20px; padding: 6px 14px; font-size: 0.78rem; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(232,56,117,0.25); margin-right: 15px; transition: all 0.2s ease;">
                                        🎬 觀看
                                    </button>
                                    <span class="chevron-${s.story_id}" style="transition: transform 0.3s ease; font-size: 0.85rem; color: var(--text-secondary);">▼</span>
                                </div>
                            </div>
                            <div id="story-dialogue-${s.story_id}" class="story-dialogue-content" style="display: none; padding: 15px 20px; border-top: 1px solid rgba(255,255,255,0.05); background: rgba(0,0,0,0.15);">
                                <div class="loading-mini" style="text-align: center; padding: 10px; color: var(--text-secondary);">正在讀取原生繁中台詞與語音...</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } catch (e) {
            console.error("載入劇情清單失敗:", e);
            container.innerHTML = `<div class="error-box" style="color: #ff6b6b; padding: 15px; text-align: center;">無法讀取個人劇情: ${e.message}</div>`;
        }
    },

    async toggleStoryDialogue(storyId) {
        const contentDiv = document.getElementById(`story-dialogue-${storyId}`);
        const chevron = document.querySelector(`.chevron-${storyId}`);
        if (!contentDiv || !chevron) return;
        
        const isCollapsed = contentDiv.style.display === 'none';
        if (isCollapsed) {
            contentDiv.style.display = 'block';
            chevron.style.transform = 'rotate(180deg)';
            
            // 載入對白
            if (contentDiv.innerHTML.includes('正在讀取')) {
                try {
                    const resp = await fetch(`story/${storyId}.json?v=${Date.now()}`);
                    if (!resp.ok) throw new Error("HTTP " + resp.status);
                    
                    const dialogues = await resp.json();
                    if (!dialogues || dialogues.length === 0) {
                        contentDiv.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem; text-align: center; padding: 10px;">此話無對白數據</div>';
                        return;
                    }
                    
                    contentDiv.innerHTML = `
                        <div class="dialogue-flow" style="display: flex; flex-direction: column; gap: 12px; max-height: 400px; overflow-y: auto; padding-right: 5px;">
                            <!-- 播放模式控制條 -->
                            <div class="play-banner active-hover-effect" onclick="CharactersModule.jumpToStoryPlayer(${storyId})" style="
                                background: linear-gradient(135deg, rgba(232, 56, 117, 0.15) 0%, rgba(247, 92, 141, 0.05) 100%);
                                border: 1px dashed var(--accent-color);
                                padding: 10px 15px;
                                border-radius: 8px;
                                margin-bottom: 8px;
                                cursor: pointer;
                                display: flex;
                                justify-content: space-between;
                                align-items: center;
                                font-size: 0.82rem;
                                color: var(--text-primary);
                                font-weight: 500;
                                transition: all 0.2s ease;
                            ">
                                <span>🎬 進入劇情放映模式 (觀看精美劇照與配音)</span>
                                <span style="color: var(--accent-color); font-weight: bold;">觀看 ➔</span>
                            </div>
                            ${dialogues.map(d => {
                                const hasVoice = !!d.voice;
                                const playBtn = hasVoice ? `
                                    <button class="voice-play-btn" onclick="CharactersModule.playCharaVoice(${storyId}, '${d.voice}')"
                                            style="border: none; background: var(--accent-color); color: white; border-radius: 50%; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; box-shadow: 0 2px 6px rgba(232,56,117,0.3); transition: all 0.2s; font-size: 0.7rem;">
                                        ▶
                                    </button>
                                ` : '';
                                
                                return `
                                    <div class="dialogue-row" style="display: flex; gap: 10px; align-items: flex-start; justify-content: ${d.name ? 'flex-start' : 'center'};">
                                        ${playBtn}
                                        <div class="dialogue-balloon" style="
                                            background: ${d.name ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)'};
                                            border: 1px solid ${d.name ? 'rgba(255,255,255,0.06)' : 'transparent'};
                                            padding: 10px 14px;
                                            border-radius: 12px;
                                            max-width: 80%;
                                            font-size: 0.85rem;
                                            line-height: 1.5;
                                            font-style: ${d.name ? 'normal' : 'italic'};
                                            color: ${d.name ? 'var(--text-primary)' : 'var(--text-secondary)'};
                                        ">
                                            ${d.name ? `<strong style="color: var(--accent-color); display: block; margin-bottom: 4px; font-size: 0.8rem;">${d.name}</strong>` : ''}
                                            <div>${d.words.replace(/\\n|\n/g, '<br>')}</div>
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    `;
                } catch (err) {
                    console.error("載入對白失敗:", err);
                    contentDiv.innerHTML = `<div style="color: #ff6b6b; font-size: 0.82rem; text-align: center; padding: 10px;">尚未實裝或讀取官方對白失敗。</div>`;
                }
            }
        } else {
            contentDiv.style.display = 'none';
            chevron.style.transform = 'rotate(0deg)';
        }
    },

    playCharaVoice(storyId, voiceId) {
        if (!voiceId) return;
        if (this.currentAudio) {
            this.currentAudio.pause();
        }
        
        // 優先讀取本地，再 fallback 至 EsterTion 伺服器
        const localUrl = `sound/story_vo/${voiceId}.m4a`;
        const remoteUrl = `https://prcn-sound.estertion.win/story_vo/${storyId}/${voiceId}.m4a`;
        
        const audio = new Audio(localUrl);
        audio.play().catch(err => {
            console.warn("本地語音播放失敗，Fallback 至遠端鏡像伺服器...", err);
            audio.src = remoteUrl;
            audio.play().catch(e => console.error("遠端語音播放也失敗:", e));
        });
        
        this.currentAudio = audio;
    },

    jumpToStoryPlayer(storyId) {
        // 1. 關閉角色詳細 modal
        this.closeDetail();
        
        // 2. 切換大 tab 到劇情地圖
        if (typeof window.switchTab === 'function') {
            window.switchTab('map');
        }
        
        // 3. 呼叫核心控制器載入放映
        if (window.QuestMapModule && typeof window.QuestMapModule.jumpToStory === 'function') {
            window.QuestMapModule.jumpToStory(storyId);
        }
    }
};
