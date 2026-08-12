console.log("characters.js loaded");

window.CharactersModule = {
    allCharacters: [],
    viewMode: 'grid',
    realNameMap: null,
    activeUnitId: null,
    excludedUnitIds: new Set(JSON.parse(localStorage.getItem('excluded_unit_ids') || '[]')),
    
    fallbackCharacters: [
    {
        "unit_id": 139001,
        "unit_name": "鏡華（哥德）",
        "rarity": 3,
        "pos": 816,
        "race": "精靈族",
        "guild": "小小甜心",
        "element": "-",
        "atk_type": "魔法攻擊",
        "description": "【魔法】位於後衛，反抗毀滅命運的千金小姐？優等生。以魔力滿溢的【詛咒之鎖】進行魔防減益，或ＴＰ及速度支援，但迎來極限時，將會陷入永久瘋狂。",
        "ub": "【淑女花環】對面前的１名敵人造成２次特大幅度的魔法傷害，大幅度降低其物理、魔法攻擊力，中幅度降低其魔法防禦力，並且小幅度提升其受到暴擊時的傷害。此技能造成暴擊時的傷害將從２倍變成３倍。",
        "skill1": "【反派千金的微笑】對面前的１名敵人造成２次大幅度的魔法傷害，並且小幅度降低其魔法防禦力。此技能造成暴擊時的傷害將從２倍變成３倍。若自身ＨＰ沒有全滿，大幅度恢復自身的ＨＰ，但會消耗１個【詛咒之鎖】。若自身未被施加【詛咒之鎖】，自身會陷入長時間的混亂狀態，ＴＰ無法因此技能造成的傷害恢復。",
        "skill2": "【陽傘演出】特大幅度提升我方全體的魔法攻擊力，大幅度提升魔法暴擊率，小幅度提升魔法攻擊暴擊時的傷害，大幅度提升行動速度，並且小幅度恢復ＴＰ。戰鬥開始後，第一次使用此技能時，對自身施加３個【詛咒之鎖】，並且中幅度降低ＨＰ恢復量。"
    },
    {
        "unit_id": 139101,
        "unit_name": "凱留（霸瞳天星）",
        "rarity": 3,
        "pos": 720,
        "race": "獸人",
        "guild": "美食殿堂",
        "element": "闇屬性",
        "atk_type": "魔法攻擊",
        "description": "後排魔法傷害兼破防角色。繼承霸瞳天星的權能魔力，能大幅削弱敵方魔法防禦力並進行大範圍闇屬性魔法攻擊。",
        "ub": "【霸瞳天星・極光魔彈】對敵方全體造成大範圍闇屬性魔法傷害，並強制降低敵方全體魔法防禦力與行動速度。",
        "skill1": "【霸瞳魔焰】對前方一名敵人造成大闇屬性魔法傷害，並特大降低其魔法防禦力。",
        "skill2": "【天星詠唱】使自身的魔法攻擊力與魔法暴擊傷害特大提升，並回復自身TP。"
    },
    {
        "unit_id": 138901,
        "unit_name": "格蕾斯（兔女郎）",
        "rarity": 3,
        "pos": 155,
        "race": "人類",
        "guild": "無所屬",
        "element": "光屬性",
        "atk_type": "物理攻擊",
        "description": "前排物理攻擊角色。化身為兔女郎穿梭戰場，具備高額物理暴擊率與傷害增益。",
        "ub": "【兔女郎星光衝擊】對前方單體敵人造成特大物理傷害，並提高自身物理暴擊傷害。",
        "skill1": "【兔耳跳躍】跳躍至前方造成範圍物理傷害，並提升自身行動速度。",
        "skill2": "【兔女郎幸運】提升全體夥伴的物理攻擊力與物理暴擊率。"
    },
    {
        "unit_id": 138801,
        "unit_name": "栞（冬日）",
        "rarity": 3,
        "pos": 745,
        "race": "獸人",
        "guild": "自警團（王都獵犬）"
    },
    {
        "unit_id": 138701,
        "unit_name": "若菜（冬日）",
        "rarity": 3,
        "pos": 210,
        "race": "人類",
        "guild": "無所屬"
    },
    {
        "unit_id": 138301,
        "unit_name": "貪吃佩可（阿斯特萊亞）",
        "rarity": 3,
        "pos": 155,
        "race": "人類",
        "guild": "美食殿堂"
    },
    {
        "unit_id": 100101,
        "unit_name": "貪吃佩可",
        "rarity": 1,
        "pos": 155,
        "race": "人類",
        "guild": "美食殿堂"
    },
    {
        "unit_id": 100201,
        "unit_name": "可可蘿",
        "rarity": 1,
        "pos": 545,
        "race": "精靈",
        "guild": "美食殿堂"
    },
    {
        "unit_id": 100301,
        "unit_name": "凱留",
        "rarity": 1,
        "pos": 720,
        "race": "獸人",
        "guild": "美食殿堂"
    },
    {
        "unit_id": 100401,
        "unit_name": "唯",
        "rarity": 1,
        "pos": 790,
        "race": "人類",
        "guild": "破曉之星"
    },
    {
        "unit_id": 100501,
        "unit_name": "日和",
        "rarity": 1,
        "pos": 140,
        "race": "獸人",
        "guild": "破曉之星"
    },
    {
        "unit_id": 100601,
        "unit_name": "怜",
        "rarity": 1,
        "pos": 215,
        "race": "魔族",
        "guild": "破曉之星"
    },
    {
        "unit_id": 101701,
        "unit_name": "鏡華",
        "rarity": 3,
        "pos": 755,
        "race": "精靈",
        "guild": "小小甜心"
    },
    {
        "unit_id": 105001,
        "unit_name": "似似花",
        "rarity": 3,
        "pos": 710,
        "race": "魔族",
        "guild": "七冠"
    },
    {
        "unit_id": 105401,
        "unit_name": "雪菲",
        "rarity": 3,
        "pos": 210,
        "race": "龍族",
        "guild": "美食殿堂"
    },
    {
        "unit_id": 105501,
        "unit_name": "萊拉耶爾",
        "rarity": 3,
        "pos": 740,
        "race": "天使族",
        "guild": "阿斯特萊亞"
    }
],

    async render() {
        const container = document.getElementById('characters-tab');
        container.innerHTML = '<div class="loading-mini">載入最新角色數據與技能中...</div>';

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
            let data = [];
            try {
                data = window.PCRDatabase.runQuery(`
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
                        WHERE unit_id < 180000 AND unit_id > 100000
                        AND unit_name NOT LIKE '%怪物%'
                        AND unit_id IN (SELECT DISTINCT unit_id FROM unit_rarity)
                        GROUP BY unit_name
                    ) as t
                    JOIN unit_data as u ON u.unit_id = t.max_id
                    LEFT JOIN unit_profile as p ON u.unit_id = p.unit_id
                    ORDER BY unit_id DESC
                `);
            } catch (e) {
                console.warn("[CharactersModule] 混淆資料庫使用相容角色清單:", e);
            }

            if (!data || data.length === 0) {
                data = [...this.fallbackCharacters];
            }

            // 確保按登場時間 (unit_id DESC) 排序
            data.sort((a, b) => b.unit_id - a.unit_id);
            this.allCharacters = data;

            this.renderLayout(container, this.allCharacters);
        } catch (error) {
            console.error("Data Cleanup Error:", error);
            container.innerHTML = `<div class="error-box">角色數據加載失敗: ${error.message}</div>`;
        }
    },

    renderLayout(container, characters) {
        container.innerHTML = `
            <div class="gallery-header glass-card" style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                    <div style="display: flex; align-items: center; gap: 20px;">
                        <h2 style="margin: 0;">角色圖鑑 (TW - 2026/08/11 最新開池)</h2>
                        <select id="char-sort" class="region-select" style="background-image: none; padding-right: 12px;">
                            <option value="id-desc" selected>登場時間 (新→舊)</option>
                            <option value="id-asc">登場時間 (舊→新)</option>
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
            <div id="char-grid" class="char-grid">
                ${this.viewMode === 'grid' ? this.renderGrid(characters) : (this.viewMode === 'list' ? this.renderTable(characters) : this.renderGuildView(characters))}
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
            } else if (this.viewMode === 'list') {
                displayContainer.className = 'char-table-container';
                displayContainer.innerHTML = this.renderTable(filtered);
            } else {
                displayContainer.className = 'char-guild-container';
                displayContainer.innerHTML = this.renderGuildView(filtered);
            }
        };

        const updateView = this.updateView;
        document.getElementById('char-search').addEventListener('input', updateView);
        document.getElementById('char-sort').addEventListener('change', updateView);
        document.getElementById('view-btn-grid').addEventListener('click', () => { this.viewMode = 'grid'; updateView(); });
        document.getElementById('view-btn-list').addEventListener('click', () => { this.viewMode = 'list'; updateView(); });
        document.getElementById('view-btn-guild').addEventListener('click', () => { this.viewMode = 'guild'; updateView(); });
    },

    renderGrid(characters) {
        if (!characters || characters.length === 0) return '<div class="no-data">尚無角色資料</div>';
        return characters.map(c => {
            const iconId = c.unit_id;
            const avatarUrl = window.AvatarService ? window.AvatarService.getAvatarUrl(iconId) : `https://redive.estertion.win/icon/unit/${iconId + 30}.webp`;
            return `
                <div class="char-card glass-card" onclick="CharactersModule.openDetail(${c.unit_id})">
                    <div class="char-icon-wrapper">
                        <img src="${avatarUrl}" 
                             onerror="this.onerror=null; this.src='https://redive.estertion.win/icon/unit/${iconId}.webp';" 
                             alt="${c.unit_name}" class="char-icon">
                        <span class="char-rarity">${'★'.repeat(c.rarity || 3)}</span>
                    </div>
                    <div class="char-name">${c.unit_name}</div>
                    <div class="char-sub">${c.guild || '無公會'}</div>
                </div>
            `;
        }).join('');
    },

    renderTable(characters) {
        return `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>頭像</th>
                        <th>ID</th>
                        <th>角色名稱</th>
                        <th>屬性</th>
                        <th>公會</th>
                        <th>種族</th>
                        <th>站位</th>
                    </tr>
                </thead>
                <tbody>
                    ${characters.map(c => {
                        const avatarUrl = window.AvatarService ? window.AvatarService.getAvatarUrl(c.unit_id) : `https://redive.estertion.win/icon/unit/${c.unit_id + 30}.webp`;
                        return `
                        <tr onclick="CharactersModule.openDetail(${c.unit_id})">
                            <td><img src="${avatarUrl}" onerror="this.src='https://redive.estertion.win/icon/unit/${c.unit_id}.webp'" style="width: 40px; height: 40px; border-radius: 8px;"></td>
                            <td>${c.unit_id}</td>
                            <td><strong>${c.unit_name}</strong></td>
                            <td><span class="badge" style="background: rgba(255,117,140,0.2); color: #ff758c; padding: 2px 6px; border-radius: 4px;">${c.element || '水屬性'}</span></td>
                            <td>${c.guild || '-'}</td>
                            <td>${c.race || '-'}</td>
                            <td>${c.pos || '-'}</td>
                        </tr>
                    `;
                    }).join('')}
                </tbody>
            </table>
        `;
    },

    renderGuildView(characters) {
        const grouped = {};
        characters.forEach(c => {
            const g = c.guild || '其他 / 無公會';
            if (!grouped[g]) grouped[g] = [];
            grouped[g].push(c);
        });

        return Object.entries(grouped).map(([guild, members]) => `
            <div class="guild-group glass-card" style="margin-bottom: 20px; padding: 15px;">
                <h3 style="margin-top: 0; color: #ff758c; border-bottom: 1px solid rgba(255,117,140,0.3); padding-bottom: 8px;">🏰 ${guild} (${members.length}位)</h3>
                <div class="char-grid" style="grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));">
                    ${this.renderGrid(members)}
                </div>
            </div>
        `).join('');
    },

    openDetail(unitId) {
        const char = this.allCharacters.find(c => c.unit_id === unitId);
        if (!char) return;
        
        const modalEl = document.getElementById('char-detail-modal') || document.getElementById('detail-modal');
        if (!modalEl) return;

        let body = document.getElementById('modal-body');
        if (!body) {
            body = modalEl.querySelector('.modal-content') || modalEl;
        }

        const cardImg = window.AvatarService ? window.AvatarService.getCardUrl(unitId) : `https://redive.estertion.win/card/full/${unitId + 30}.webp`;
        const iconFallback = window.AvatarService ? window.AvatarService.getAvatarUrl(unitId) : `https://redive.estertion.win/icon/unit/${unitId + 30}.webp`;

        body.innerHTML = `
            <div style="text-align: center; color: #fff; padding: 10px;">
                <div style="position: relative; margin-bottom: 15px;">
                    <img src="${cardImg}" 
                         onerror="this.onerror=null; this.src='${iconFallback}';" 
                         style="max-width: 100%; max-height: 380px; object-fit: contain; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);">
                    <span style="position: absolute; bottom: 10px; right: 15px; background: rgba(0,0,0,0.75); color: #ffd700; padding: 4px 12px; border-radius: 20px; font-weight: bold; backdrop-filter: blur(6px);">
                        ★3 戰鬥登場
                    </span>
                </div>
                <h2 style="color: #ff758c; margin-bottom: 5px;">${char.unit_name}</h2>
                <div style="display: flex; justify-content: center; gap: 10px; margin-bottom: 15px; flex-wrap: wrap;">
                    <span class="badge" style="background: rgba(255,215,0,0.2); color: #ffd700; padding: 3px 10px; border-radius: 12px; border: 1px solid rgba(255,215,0,0.4);">ID: ${char.unit_id}</span>
                    <span class="badge" style="background: rgba(100,200,255,0.2); color: #64c8ff; padding: 3px 10px; border-radius: 12px; border: 1px solid rgba(100,200,255,0.4);">${char.element || '魔法類型'}</span>
                    <span class="badge" style="background: rgba(255,100,200,0.2); color: #ff64c8; padding: 3px 10px; border-radius: 12px; border: 1px solid rgba(255,100,200,0.4);">站位: ${char.pos || '後排'}</span>
                    <span class="badge" style="background: rgba(200,100,255,0.2); color: #c864ff; padding: 3px 10px; border-radius: 12px; border: 1px solid rgba(200,100,255,0.4);">公會: ${char.guild || '無'}</span>
                </div>
                <p style="text-align: left; background: rgba(255,255,255,0.08); padding: 12px; border-radius: 8px; line-height: 1.6;">${char.description || '前排/中排/後排戰鬥角色，具備獨特戰術支援機制。'}</p>
                
                ${char.ub ? `
                    <div style="text-align: left; margin-top: 15px; background: rgba(255,117,140,0.15); border-left: 4px solid #ff758c; padding: 10px 15px; border-radius: 0 8px 8px 0;">
                        <h4 style="margin: 0 0 5px 0; color: #ff758c;">💥 必殺技 (UB)</h4>
                        <p style="margin: 0; font-size: 0.95em; line-height: 1.5;">${char.ub}</p>
                    </div>
                ` : ''}
                
                ${char.skill1 ? `
                    <div style="text-align: left; margin-top: 10px; background: rgba(100,200,255,0.15); border-left: 4px solid #64c8ff; padding: 10px 15px; border-radius: 0 8px 8px 0;">
                        <h4 style="margin: 0 0 5px 0; color: #64c8ff;">🔮 技能 1</h4>
                        <p style="margin: 0; font-size: 0.95em; line-height: 1.5;">${char.skill1}</p>
                    </div>
                ` : ''}

                ${char.skill2 ? `
                    <div style="text-align: left; margin-top: 10px; background: rgba(200,100,255,0.15); border-left: 4px solid #c864ff; padding: 10px 15px; border-radius: 0 8px 8px 0;">
                        <h4 style="margin: 0 0 5px 0; color: #c864ff;">✨ 技能 2</h4>
                        <p style="margin: 0; font-size: 0.95em; line-height: 1.5;">${char.skill2}</p>
                    </div>
                ` : ''}
            </div>
        `;
        modalEl.style.display = 'flex';
    },

    closeDetail() {
        const modalEl = document.getElementById('char-detail-modal') || document.getElementById('detail-modal');
        if (modalEl) modalEl.style.display = 'none';
    }
};
