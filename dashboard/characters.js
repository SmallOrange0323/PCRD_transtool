console.log("characters.js loaded");

window.CharactersModule = {
    allCharacters: [],
    
    async render() {
        const container = document.getElementById('characters-tab');
        container.innerHTML = '<div class="loading-mini">清洗角色數據中...</div>';

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
                    <div class="search-box">
                        <input type="text" id="char-search" placeholder="搜尋角色名稱..." class="region-select" style="width: 250px; background-image: none; padding-right: 12px;">
                    </div>
                </div>
            </div>
            <div id="char-grid" class="char-grid">
                ${this.renderGrid(characters)}
            </div>
        `;

        const updateView = () => {
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

            document.getElementById('char-grid').innerHTML = this.renderGrid(filtered);
        };

        document.getElementById('char-search').addEventListener('input', updateView);
        document.getElementById('char-sort').addEventListener('change', updateView);
        updateView();
    },

    renderGrid(characters) {
        if (characters.length === 0) return '<div class="empty-msg">找不到符合條件的角色</div>';
        
        return characters.map(c => {
            const baseId = Math.floor(c.unit_id / 100) * 100;
            const img31 = `https://redive.estertion.win/icon/unit/${baseId + 31}.webp`;
            const img11 = `https://redive.estertion.win/icon/unit/${baseId + 11}.webp`;

            return `
                <div class="char-card glass-card" onclick="CharactersModule.showDetail(${c.unit_id})">
                    <div class="char-avatar">
                        <img src="${img31}" onerror="this.src='${img11}'; this.onerror=function(){this.src='https://redive.estertion.win/icon/unit/000000.webp';}">
                    </div>
                    <div class="char-info">
                        <div class="char-name">${c.unit_name}</div>
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

    async showDetail(unitId) {
        const modal = document.getElementById('char-detail-modal');
        const body = document.getElementById('modal-body');
        modal.style.display = 'flex';
        body.innerHTML = '<div class="loading-mini">讀取角色詳情中...</div>';

        try {
            // 1. 取得詳細數值與成長值
            const stats = window.PCRDatabase.runQuery(`
                SELECT * FROM unit_rarity WHERE unit_id = ? ORDER BY rarity DESC LIMIT 1
            `, [unitId])[0] || window.PCRDatabase.runQuery(`
                SELECT * FROM unit_data WHERE unit_id = ?
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
            }

            // 5. 渲染詳情
            const baseId = Math.floor(unitId / 100) * 100;
            const profile = this.allCharacters.find(c => c.unit_id === unitId);
            
            this.currentStats = stats;
            const maxLevel = window.PCRDatabase.currentRegion === 'jp' ? 305 : 280;

            body.innerHTML = `
                <div class="detail-header">
                    <img src="https://redive.estertion.win/icon/unit/${baseId + 31}.webp" class="detail-avatar" onerror="this.src='https://redive.estertion.win/icon/unit/${baseId + 11}.webp'">
                    <div class="detail-main-info">
                        <div style="display: flex; align-items: center; gap: 15px;">
                            <h2 style="margin: 0;">${profile ? profile.unit_name : '角色詳情'}</h2>
                            <div class="level-input-group">
                                <span style="font-size: 0.8rem; color: var(--text-secondary);">Lv.</span>
                                <input type="number" id="detail-level" value="${maxLevel}" min="1" max="400" 
                                       class="region-select" style="width: 70px; padding: 2px 8px; background-image: none;"
                                       oninput="CharactersModule.updateCalculatedStats(this.value)">
                            </div>
                        </div>
                        <div class="char-meta">
                            <span>站位: ${stats ? stats.search_area_width : '??'}</span>
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
                                <img src="https://redive.estertion.win/icon/skill/${s.icon_type}.webp" class="skill-icon" 
                                     onerror="this.src='https://redive.estertion.win/icon/skill/${s.icon_type}.png'; this.onerror=function(){this.src='https://redive.estertion.win/icon/unit/000000.webp';}">
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
            if (!act) break;
            items.push({ id: act, index: i });
        }

        const loopStart = pattern.loop_start;
        const loopEnd = pattern.loop_end;

        return `
            <div class="pattern-container" style="display: flex; flex-wrap: wrap; gap: 10px; padding: 20px; background: rgba(0,0,0,0.2); border-radius: 15px;">
                ${items.map(item => {
                    const isLoop = item.index >= loopStart && item.index <= loopEnd;
                    let icon = 'https://redive.estertion.win/icon/skill/1.png'; 
                    let name = '普通攻擊';
                    
                    if (item.id === 1001 && skillMap['1001']) {
                        icon = `https://redive.estertion.win/icon/skill/${skillMap['1001'].icon_type}.webp`;
                        name = skillMap['1001'].name;
                    } else if (item.id === 1002 && skillMap['1002']) {
                        icon = `https://redive.estertion.win/icon/skill/${skillMap['1002'].icon_type}.webp`;
                        name = skillMap['1002'].name;
                    } else if (item.id > 1) {
                        name = `技能 ${item.id}`;
                    }

                    return `
                        <div class="pattern-item" style="text-align: center; width: 70px; padding: 8px 5px; border-radius: 10px; ${isLoop ? 'border: 2px solid var(--accent-color); background: rgba(255,107,157,0.1);' : 'border: 1px solid rgba(255,255,255,0.05);'}">
                            <img src="${icon}" style="width: 40px; height: 40px; border-radius: 5px;" onerror="this.src='https://redive.estertion.win/icon/skill/1.png'">
                            <div style="font-size: 0.6rem; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: ${item.id > 1 ? '#ffa94d' : 'inherit'}">${name}</div>
                            <div style="font-size: 0.5rem; color: var(--text-secondary);">${item.index}</div>
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
        document.getElementById('char-detail-modal').style.display = 'none';
    }
};
