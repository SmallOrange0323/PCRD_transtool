console.log("diff.js loaded");

window.DatabaseDiffModule = {
    // 儲存加載好的資料庫實例
    databases: {
        tw: null,
        jp: null,
        tw_template: null
    },

    // 當前比對結果
    results: {
        characters: [],
        mainStories: [],
        events: []
    },

    // 渲染主畫面
    render() {
        const container = document.getElementById('diff-tab');
        if (!container) return;

        container.innerHTML = `
            <div class="diff-container glass-card" style="margin-top: 20px; padding: 24px;">
                <div class="diff-header" style="margin-bottom: 24px;">
                    <h2 style="font-size: 1.5rem; margin-bottom: 8px; font-family: var(--font-main); display: flex; align-items: center; gap: 10px;">
                        📊 資料庫比對工具
                    </h2>
                    <p style="color: var(--text-secondary); font-size: 0.9rem;">
                        比對不同版本的遊戲資料庫，查詢新增的角色、主線劇情與活動。
                    </p>
                </div>

                <!-- 比對控制項 -->
                <div class="diff-controls" style="display: flex; gap: 15px; align-items: center; margin-bottom: 24px; flex-wrap: wrap;">
                    <div class="control-group" style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-weight: 500; font-size: 0.95rem;">比對模式：</span>
                        <select id="diff-mode-select" class="glass-select" style="
                            padding: 8px 16px;
                            border-radius: 10px;
                            border: 1px solid var(--glass-border);
                            background: rgba(255, 255, 255, 0.7);
                            color: var(--text-primary);
                            font-weight: 600;
                            cursor: pointer;
                        ">
                            <option value="jp_vs_tw">日服最新版 🆚 台服最新版 (千里眼比對)</option>
                            <option value="tw_vs_template">台服最新版 🆚 台服舊版範本 (近期實裝)</option>
                        </select>
                    </div>

                    <button id="run-diff-btn" class="diff-btn" onclick="DatabaseDiffModule.runDiff()" style="
                        padding: 10px 24px;
                        background: var(--accent-gradient);
                        color: white;
                        border: none;
                        border-radius: 20px;
                        font-weight: 700;
                        cursor: pointer;
                        box-shadow: 0 4px 12px rgba(232, 56, 117, 0.2);
                        transition: var(--transition);
                    ">
                        開始比對
                    </button>
                </div>

                <!-- 進度條 -->
                <div id="diff-progress-container" style="display: none; margin-bottom: 24px;">
                    <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 8px;" id="diff-progress-text">準備中...</div>
                    <div class="loader-bar" style="height: 6px; background: rgba(0,0,0,0.05); border-radius: 3px; overflow: hidden;">
                        <div id="diff-progress-bar" style="width: 0%; height: 100%; background: var(--accent-gradient); transition: width 0.3s ease;"></div>
                    </div>
                </div>

                <!-- 比對結果區 -->
                <div id="diff-result-panel" style="display: none;">
                    <div class="diff-tabs" style="display: flex; gap: 10px; border-bottom: 1px solid rgba(0,0,0,0.05); padding-bottom: 12px; margin-bottom: 20px;">
                        <button class="diff-tab-btn active" onclick="DatabaseDiffModule.switchSubTab('chara')">👥 新增角色 (<span id="diff-count-chara">0</span>)</button>
                        <button class="diff-tab-btn" onclick="DatabaseDiffModule.switchSubTab('story')">⚔️ 新增主線 (<span id="diff-count-story">0</span>)</button>
                        <button class="diff-tab-btn" onclick="DatabaseDiffModule.switchSubTab('event')">🏆 新增活動 (<span id="diff-count-event">0</span>)</button>
                    </div>

                    <div id="diff-sub-chara" class="diff-sub-content active"></div>
                    <div id="diff-sub-story" class="diff-sub-content" style="display: none;"></div>
                    <div id="diff-sub-event" class="diff-sub-content" style="display: none;"></div>
                </div>
            </div>
        `;
    },

    // 切換結果子分頁
    switchSubTab(subTabId) {
        document.querySelectorAll('.diff-tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.diff-sub-content').forEach(el => el.style.display = 'none');

        const btn = document.querySelector(`[onclick="DatabaseDiffModule.switchSubTab('${subTabId}')"]`);
        if (btn) btn.classList.add('active');

        const content = document.getElementById(`diff-sub-${subTabId}`);
        if (content) content.style.display = 'block';
    },

    // 執行比對
    async runDiff() {
        const mode = document.getElementById('diff-mode-select').value;
        const progressContainer = document.getElementById('diff-progress-container');
        const progressText = document.getElementById('diff-progress-text');
        const progressBar = document.getElementById('diff-progress-bar');
        const resultPanel = document.getElementById('diff-result-panel');
        const runBtn = document.getElementById('run-diff-btn');

        runBtn.disabled = true;
        progressContainer.style.display = 'block';
        resultPanel.style.display = 'none';

        try {
            let dbA = null; // 基準庫
            let dbB = null; // 目標庫 (較新的版本)

            if (mode === 'jp_vs_tw') {
                // 基準庫為台服最新版 (A)
                progressText.innerText = '正在加載台服資料庫...';
                progressBar.style.width = '15%';
                // 優先使用已加載的 PCRDatabase.db
                if (!window.PCRDatabase.db) {
                    await window.PCRDatabase.initDatabase((msg, pct) => {
                        progressText.innerText = `加載台服: ${msg}`;
                        progressBar.style.width = `${pct * 0.3}%`;
                    });
                }
                dbA = window.PCRDatabase.db;

                // 目標庫為日服最新版 (B)
                progressText.innerText = '正在加載日服資料庫...';
                progressBar.style.width = '45%';
                if (!this.databases.jp) {
                    this.databases.jp = await window.PCRDatabase.loadSpecificDatabase('jp', (msg, pct) => {
                        progressText.innerText = `加載日服: ${msg}`;
                        progressBar.style.width = `${30 + pct * 0.6}%`;
                    });
                }
                dbB = this.databases.jp;

            } else if (mode === 'tw_vs_template') {
                // 基準庫為台服舊版範本 (A)
                progressText.innerText = '正在加載台服舊版範本...';
                progressBar.style.width = '20%';
                if (!this.databases.tw_template) {
                    this.databases.tw_template = await window.PCRDatabase.loadSpecificDatabase('tw_template', (msg, pct) => {
                        progressText.innerText = `加載範本: ${msg}`;
                        progressBar.style.width = `${pct * 0.4}%`;
                    });
                }
                dbA = this.databases.tw_template;

                // 目標庫為台服最新版 (B)
                progressText.innerText = '正在加載台服最新版...';
                progressBar.style.width = '60%';
                if (!window.PCRDatabase.db) {
                    await window.PCRDatabase.initDatabase((msg, pct) => {
                        progressText.innerText = `加載台服: ${msg}`;
                        progressBar.style.width = `${40 + pct * 0.4}%`;
                    });
                }
                dbB = window.PCRDatabase.db;
            }

            progressBar.style.width = '90%';
            progressText.innerText = '正在比對資料結構中...';

            // 進行比對
            this.compareDatabases(dbA, dbB);

            progressBar.style.width = '100%';
            progressText.innerText = '比對完成！';
            
            setTimeout(() => {
                progressContainer.style.display = 'none';
                resultPanel.style.display = 'block';
                runBtn.disabled = false;
                this.renderResults();
            }, 500);

        } catch (e) {
            console.error(e);
            progressText.innerHTML = `<span style="color: #ff6b6b;">錯誤: ${e.message}</span>`;
            runBtn.disabled = false;
        }
    },

    // 透過 SQL.js 執行比對
    compareDatabases(dbA, dbB) {
        // 輔助查詢函式
        const query = (db, sql) => {
            try {
                const stmt = db.prepare(sql);
                const results = [];
                while (stmt.step()) {
                    results.push(stmt.getAsObject());
                }
                stmt.free();
                return results;
            } catch (e) {
                console.error("SQL query error:", e, sql);
                return [];
            }
        };

        // 1. 比對角色
        const hasProfileA = query(dbA, "SELECT name FROM sqlite_master WHERE type='table' AND name='unit_profile'").length > 0;
        const hasProfileB = query(dbB, "SELECT name FROM sqlite_master WHERE type='table' AND name='unit_profile'").length > 0;

        let sqlA, sqlB;
        if (hasProfileA) {
            sqlA = "SELECT u.unit_id, u.unit_name, u.comment FROM unit_data u JOIN unit_profile p ON u.unit_id = p.unit_id WHERE u.unit_id >= 100000 AND u.unit_id < 200000";
        } else {
            sqlA = "SELECT unit_id, unit_name, comment FROM unit_data WHERE unit_id >= 100000 AND unit_id < 200000 AND rarity >= 1 AND rarity <= 3";
        }

        if (hasProfileB) {
            sqlB = "SELECT u.unit_id, u.unit_name, u.comment FROM unit_data u JOIN unit_profile p ON u.unit_id = p.unit_id WHERE u.unit_id >= 100000 AND u.unit_id < 200000";
        } else {
            sqlB = "SELECT unit_id, unit_name, comment FROM unit_data WHERE unit_id >= 100000 AND unit_id < 200000 AND rarity >= 1 AND rarity <= 3";
        }

        const charsA = query(dbA, sqlA);
        const charsB = query(dbB, sqlB);

        const mapA = new Map(charsA.map(c => [c.unit_id, c]));
        this.results.characters = charsB.filter(c => !mapA.has(c.unit_id));

        // 2. 比對主線章節
        const mainA = query(dbA, "SELECT DISTINCT story_group_id, title FROM story_detail WHERE story_group_id BETWEEN 2000 AND 2999");
        const mainB = query(dbB, "SELECT DISTINCT story_group_id, title FROM story_detail WHERE story_group_id BETWEEN 2000 AND 2999");

        const mainMapA = new Set(mainA.map(s => s.story_group_id));
        this.results.mainStories = mainB.filter(s => !mainMapA.has(s.story_group_id));

        // 3. 比對活動劇情
        const getEvents = (db) => {
            const list = [];
            try {
                const rows = query(db, "SELECT DISTINCT story_group_id as id, title FROM event_story_data WHERE story_group_id >= 5000");
                list.push(...rows);
            } catch(e){}

            const hasSeven = query(db, "SELECT name FROM sqlite_master WHERE type='table' AND name='seven_event_setting'").length > 0;
            if (hasSeven) {
                try {
                    const rows = query(db, "SELECT event_id as id, title FROM seven_event_setting WHERE event_id >= 10000");
                    list.push(...rows);
                } catch(e){}
            }
            return list;
        };

        const eventsA = getEvents(dbA);
        const eventsB = getEvents(dbB);

        const eventMapA = new Set(eventsA.map(e => e.id));
        this.results.events = eventsB.filter(e => !eventMapA.has(e.id));
    },

    // 渲染比對結果
    renderResults() {
        document.getElementById('diff-count-chara').innerText = this.results.characters.length;
        document.getElementById('diff-count-story').innerText = this.results.mainStories.length;
        document.getElementById('diff-count-event').innerText = this.results.events.length;

        // 1. 角色面板
        const charPanel = document.getElementById('diff-sub-chara');
        if (this.results.characters.length === 0) {
            charPanel.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 40px;">無新增角色資料。</div>';
        } else {
            let html = '<div class="chara-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px;">';
            this.results.characters.forEach(c => {
                const avatarUrl = window.AvatarService.getAvatarUrl(c.unit_id);
                const cleanComment = (c.comment || '').replace(/\n/g, ' ').trim();
                html += `
                    <div class="glass-card chara-card" style="display: flex; gap: 15px; align-items: center; padding: 15px; transition: var(--transition); border-radius: 16px;">
                        <img src="${avatarUrl}" onerror="this.src='https://redive.estertion.win/icon/unit/100001.webp';" style="width: 70px; height: 70px; border-radius: 12px; object-fit: cover; box-shadow: 0 4px 10px rgba(0,0,0,0.1); border: 2px solid rgba(255,255,255,0.8);" />
                        <div style="flex: 1; min-width: 0;">
                            <h3 style="font-size: 1.05rem; margin-bottom: 4px; font-weight: 700; color: var(--text-primary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                                ${c.unit_name}
                            </h3>
                            <div style="font-size: 0.75rem; color: var(--text-secondary); font-family: monospace; margin-bottom: 6px;">ID: ${c.unit_id}</div>
                            <p style="font-size: 0.8rem; color: var(--text-secondary); text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.4;">
                                ${cleanComment || '暫無說明'}
                            </p>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            charPanel.innerHTML = html;
        }

        // 2. 主線面板
        const storyPanel = document.getElementById('diff-sub-story');
        if (this.results.mainStories.length === 0) {
            storyPanel.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 40px;">無新增主線章節。</div>';
        } else {
            let html = '<div style="display: flex; flex-direction: column; gap: 12px;">';
            this.results.mainStories.forEach(s => {
                html += `
                    <div class="glass-card" style="display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-radius: 12px;">
                        <div style="font-weight: 600; font-size: 1.05rem;">${s.title}</div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary); font-family: monospace; background: rgba(0,0,0,0.03); padding: 4px 10px; border-radius: 8px;">章節 ID: ${s.story_group_id}</div>
                    </div>
                `;
            });
            html += '</div>';
            storyPanel.innerHTML = html;
        }

        // 3. 活動面板
        const eventPanel = document.getElementById('diff-sub-event');
        if (this.results.events.length === 0) {
            eventPanel.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 40px;">無新增活動劇情。</div>';
        } else {
            let html = '<div style="display: flex; flex-direction: column; gap: 12px;">';
            this.results.events.forEach(e => {
                html += `
                    <div class="glass-card" style="display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-radius: 12px;">
                        <div style="font-weight: 600; font-size: 1.05rem;">${e.title}</div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary); font-family: monospace; background: rgba(0,0,0,0.03); padding: 4px 10px; border-radius: 8px;">活動 ID: ${e.id}</div>
                    </div>
                `;
            });
            html += '</div>';
            eventPanel.innerHTML = html;
        }
    }
};
