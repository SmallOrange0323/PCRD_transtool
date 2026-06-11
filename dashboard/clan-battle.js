console.log("clan-battle.js loaded - TW Multi-Target Fix");

window.ClanBattleModule = {
    currentBattle: null,
    bosses: [],

    async render() {
        const container = document.getElementById('clan-battle-tab');
        container.innerHTML = '<div class="loading-mini">讀取丁階段數據中...</div>';

        try {
            const battleInfo = window.PCRDatabase.runQuery(`
                SELECT clan_battle_id, release_month, start_time
                FROM clan_battle_schedule
                ORDER BY clan_battle_id DESC
                LIMIT 1
            `)[0];

            if (!battleInfo) throw new Error('找不到公會戰日程數據');
            this.currentBattle = battleInfo;

            // 台服專用 SQL：使用 enemy_m_parts 連結多目標部位
            this.bosses = window.PCRDatabase.runQuery(`
                WITH boss_ids AS (
                    SELECT wave_group_id_1 AS wg, 1 AS pos FROM clan_battle_2_map_data WHERE clan_battle_id = ? AND phase = 4
                    UNION ALL
                    SELECT wave_group_id_2 AS wg, 2 AS pos FROM clan_battle_2_map_data WHERE clan_battle_id = ? AND phase = 4
                    UNION ALL
                    SELECT wave_group_id_3 AS wg, 3 AS pos FROM clan_battle_2_map_data WHERE clan_battle_id = ? AND phase = 4
                    UNION ALL
                    SELECT wave_group_id_4 AS wg, 4 AS pos FROM clan_battle_2_map_data WHERE clan_battle_id = ? AND phase = 4
                    UNION ALL
                    SELECT wave_group_id_5 AS wg, 5 AS pos FROM clan_battle_2_map_data WHERE clan_battle_id = ? AND phase = 4
                )
                SELECT
                    b.pos,
                    e1.unit_id,
                    e1.name AS boss_name,
                    e1.hp,
                    e1.def as def1, e1.magic_def as mdef1, e1.name as n1,
                    m1.def as def2, m1.magic_def as mdef2, m1.name as n2,
                    m2.def as def3, m2.magic_def as mdef3, m2.name as n3,
                    m3.def as def4, m3.magic_def as mdef4, m3.name as n4,
                    MAX(COALESCE(e1.atk, 0), COALESCE(m1.atk, 0), COALESCE(m2.atk, 0)) as atk,
                    MAX(COALESCE(e1.magic_str, 0), COALESCE(m1.magic_str, 0), COALESCE(m2.magic_str, 0)) as magic_str,
                    f.prefab_id, f.comment,
                    (CASE WHEN emp.enemy_id IS NOT NULL THEN 1 ELSE 0 END) as is_multi
                FROM
                    boss_ids b
                    LEFT JOIN wave_group_data AS w ON w.wave_group_id = b.wg
                    LEFT JOIN enemy_parameter AS e1 ON w.enemy_id_1 = e1.enemy_id
                    LEFT JOIN unit_enemy_data AS f ON e1.unit_id = f.unit_id
                    -- 台服專用：連結 enemy_m_parts
                    LEFT JOIN enemy_m_parts AS emp ON e1.enemy_id = emp.enemy_id
                    LEFT JOIN enemy_parameter AS m1 ON emp.child_enemy_parameter_1 = m1.enemy_id
                    LEFT JOIN enemy_parameter AS m2 ON emp.child_enemy_parameter_2 = m2.enemy_id
                    LEFT JOIN enemy_parameter AS m3 ON emp.child_enemy_parameter_3 = m3.enemy_id
                WHERE
                    e1.name IS NOT NULL
                GROUP BY b.pos
                ORDER BY b.pos ASC
            `, [battleInfo.clan_battle_id, battleInfo.clan_battle_id, battleInfo.clan_battle_id, battleInfo.clan_battle_id, battleInfo.clan_battle_id]);

            this.renderContent(container);
        } catch (error) {
            console.error(error);
            container.innerHTML = `<div class="error-box">數據加載失敗: ${error.message}</div>`;
        }
    },

    renderContent(container) {
        const battleTime = this.formatBattleTime(this.currentBattle.start_time);
        
        container.innerHTML = `
            <div class="battle-header glass-card">
                <div class="battle-title">
                    <span class="month">${this.currentBattle.release_month % 100}月</span>
                    <span class="label">戰隊戰現況 (丁階段)</span>
                </div>
                <div class="battle-period">
                    <span class="time">${battleTime.start} ~ ${battleTime.end}</span>
                </div>
            </div>

            <div id="boss-container" class="boss-grid">
                ${this.bosses.map((boss, index) => {
                    const parts = [];
                    if (boss.n1) parts.push({ name: '本體', def: boss.def1, mdef: boss.mdef1 });
                    if (boss.n2) parts.push({ name: boss.n2.replace(boss.boss_name, '').trim() || '部位 1', def: boss.def2, mdef: boss.mdef2 });
                    if (boss.n3) parts.push({ name: boss.n3.replace(boss.boss_name, '').trim() || '部位 2', def: boss.def3, mdef: boss.mdef3 });
                    if (boss.n4) parts.push({ name: boss.n4.replace(boss.boss_name, '').trim() || '部位 3', def: boss.def4, mdef: boss.mdef4 });

                    return `
                        <div class="boss-card card-glass ${boss.is_multi ? 'is-multi' : ''}">
                            <!-- 左欄：頭像與基本資訊 -->
                            <div class="boss-left">
                                <div class="boss-rank">BOSS ${index + 1}</div>
                                <div class="boss-avatar" style="overflow: hidden; display: flex; align-items: center; justify-content: center; padding: 0;">
                                    ${window.AvatarService.getAvatarHtmlByUnitId(boss.unit_id, boss.boss_name)}
                                </div>
                                <div class="boss-name">${boss.boss_name}</div>
                                ${boss.is_multi ? '<div class="multi-tag" style="position:relative; top:10px; right:0;">多目標</div>' : ''}
                            </div>
                            
                            <!-- 中欄：數值數據與部位 -->
                            <div class="boss-mid">
                                <div class="stat-item">
                                    <span class="stat-label">HP (總計)</span>
                                    <span class="stat-value" style="font-size: 1.4rem; color: var(--accent-color);">${this.formatNumber(boss.hp)}</span>
                                </div>
                                
                                ${!boss.is_multi ? `
                                    <div class="stat-row">
                                        <div class="stat-item">
                                            <span class="stat-label">物防</span>
                                            <span class="stat-value">${boss.def1}</span>
                                        </div>
                                        <div class="stat-item">
                                            <span class="stat-label">魔防</span>
                                            <span class="stat-value">${boss.mdef1}</span>
                                        </div>
                                    </div>
                                ` : `
                                    <div class="parts-table">
                                        <div class="parts-header">
                                            <span>部位</span><span>物防</span><span>魔防</span>
                                        </div>
                                        ${parts.map(p => `
                                            <div class="parts-row">
                                                <span class="part-name">${p.name}</span>
                                                <span class="part-val">${p.def}</span>
                                                <span class="part-val">${p.mdef}</span>
                                            </div>
                                        `).join('')}
                                    </div>
                                `}

                                <div class="stat-row" style="margin-top: 5px;">
                                    <div class="stat-item">
                                        <span class="stat-label">物攻</span>
                                        <span class="stat-value">${this.formatNumber(boss.atk)}</span>
                                    </div>
                                    <div class="stat-item">
                                        <span class="stat-label">魔攻</span>
                                        <span class="stat-value">${this.formatNumber(boss.magic_str)}</span>
                                    </div>
                                </div>
                            </div>

                            <!-- 右欄：特性區 -->
                            <div class="boss-right">
                                <div class="boss-comment-container" style="margin-top: 0; background: transparent; padding: 0;">
                                    <div class="boss-comment-label">技能與特性：</div>
                                    <div class="boss-comment-text" style="height: auto; max-height: none; overflow: visible;">
                                        ${(boss.comment || '').replace(/\\n/g, '<br>')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    },

    formatNumber(num) {
        if (num >= 100000000) return (num / 100000000).toFixed(1) + ' 億';
        if (num >= 10000) return (num / 10000).toFixed(1) + ' 萬';
        return num;
    },

    formatBattleTime(startTime) {
        const start = new Date(startTime.replace(/\//g, '-'));
        const end = new Date(start.getTime() + (5 * 24 * 60 * 60 * 1000) - (5 * 60 * 60 * 1000) - 1000);
        const fmt = (d) => `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        return { start: fmt(start), end: fmt(end) };
    }
};
