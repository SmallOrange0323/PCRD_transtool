console.log("usage-stats.js loaded");

window.UsageStatsModule = {
    rawData: [],      // 原始資料緩存
    parsedTasks: [],  // 正規化後的資料
    availableMonths: new Set(),

    render() {
        const container = document.getElementById('stats-tab');
        container.innerHTML = `
            <div class="stats-container">
                <div class="stats-header glass-card">
                    <h2 style="margin-bottom: 15px;">作業角色使用率統計</h2>
                    
                    <!-- 全自動 API 對接區 -->
                    <div class="api-fetch-section" style="margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <label style="display:block; margin-bottom: 8px;">A. 全自動對接 API (aikurumi.cn)：</label>
                        <div style="display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;">
                            <select id="api-server" class="modern-input">
                                <option value="tw">台服 (TW)</option>
                                <option value="jp" selected>日服 (JP)</option>
                                <option value="cn">陸服 (CN)</option>
                            </select>
                            <input type="text" id="api-cb-id" class="modern-input" placeholder="期次 (例: 202604)" style="width: 150px;">
                            <select id="api-stage" class="modern-input">
                                <option value="1">1、2階段</option>
                                <option value="2">3階段 (丙)</option>
                                <option value="3">4階段 (丁)</option>
                                <option value="4" selected>5階段 (戊)</option>
                            </select>
                            <button class="action-btn" onclick="UsageStatsModule.fetchFromAPI()">自動抓取</button>
                            <button class="action-btn" style="background:#6c5ce7; color:white;" onclick="UsageStatsModule.loadLocalData('merged_bulk', '')">🚀 載入跨月大數據 (25/12~26/04)</button>
                            <button class="action-btn secondary" onclick="UsageStatsModule.loadLocalData('202604', 'jp')">載入 26/04 單月</button>
                        </div>
                        <span id="api-status" style="font-size: 0.9em; color: #ff6b6b;"></span>
                    </div>

                    <!-- 手動輸入區 (降級備案) -->
                    <div class="input-section" style="margin-bottom: 20px;">
                        <label style="display:block; margin-bottom: 8px;">B. 手動備案 (若 API 失敗請在此貼上 JSON)：</label>
                        <textarea id="stats-json-input" class="modern-textarea" placeholder="在此貼上 [ { ... }, { ... } ] 格式的 JSON 陣列" style="width: 100%; height: 100px; margin-bottom: 10px;"></textarea>
                        <button class="action-btn secondary" onclick="UsageStatsModule.parseInput()">解析手動數據</button>
                        <span id="parse-status" style="margin-left: 15px; font-size: 0.9em; color: var(--accent-color);"></span>
                    </div>

                    <!-- 控制面板 -->
                    <div class="control-panel" id="stats-controls" style="display: none; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                        <div style="display: flex; gap: 20px; align-items: flex-end;">
                            <div class="control-group" style="flex: 1;">
                                <label style="display:block; margin-bottom: 8px;">2. 篩選月份：</label>
                                <div id="month-checkboxes" style="display: flex; gap: 10px; flex-wrap: wrap;"></div>
                            </div>
                            <div class="control-group" style="flex: 2;">
                                <label style="display:flex; justify-content: space-between; margin-bottom: 8px;">
                                    <span>3. 最低傷害門檻：</span>
                                    <span id="dmg-val-display" style="color: var(--accent-color);">0 萬</span>
                                </label>
                                <input type="range" id="dmg-slider" min="0" max="10000" step="500" value="0" style="width: 100%;">
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 結果展示區 -->
                <div id="stats-result-area" style="margin-top: 20px; display: none;">
                    <h3 style="margin-bottom: 15px;">統計結果 <span id="valid-task-count" style="font-size: 0.8em; opacity: 0.7;"></span></h3>
                    <div id="leaderboard-container" class="leaderboard-grid"></div>
                </div>
            </div>
            
            <style>
                .modern-textarea, .modern-input {
                    background: rgba(0, 0, 0, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    color: white;
                    border-radius: 8px;
                    padding: 10px;
                    font-family: inherit;
                }
                .modern-textarea {
                    font-family: monospace;
                    resize: vertical;
                }
                .modern-textarea:focus, .modern-input:focus {
                    outline: none;
                    border-color: var(--accent-color);
                }
                .action-btn {
                    background: var(--accent-color);
                    color: black;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: all 0.2s;
                }
                .action-btn.secondary {
                    background: rgba(255, 255, 255, 0.1);
                    color: white;
                }
                .action-btn:hover {
                    transform: scale(1.05);
                    box-shadow: 0 0 10px var(--accent-color);
                }
                .leaderboard-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 15px;
                }
                .stat-card {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                    padding: 12px;
                    display: flex;
                    align-items: center;
                    gap: 15px;
                }
                .stat-avatar img {
                    width: 50px;
                    height: 50px;
                    border-radius: 5px;
                    border: 1px solid rgba(255,255,255,0.2);
                }
                .stat-info {
                    flex: 1;
                }
                .stat-name {
                    font-weight: bold;
                    margin-bottom: 5px;
                    display: flex;
                    justify-content: space-between;
                }
                .stat-bar-bg {
                    width: 100%;
                    height: 8px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 4px;
                    overflow: hidden;
                }
                .stat-bar-fill {
                    height: 100%;
                    background: var(--accent-color);
                    border-radius: 4px;
                    transition: width 0.5s ease-out;
                }
                .boss-dist {
                    display: flex;
                    gap: 2px;
                    margin-top: 5px;
                    height: 12px;
                }
                .boss-bar {
                    flex: 1;
                    background: rgba(255,255,255,0.1);
                    position: relative;
                    border-radius: 2px;
                }
                .boss-bar-fill {
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    width: 100%;
                    background: #ff6b6b;
                    border-radius: 2px;
                }
                .boss-label {
                    font-size: 0.6rem;
                    opacity: 0.5;
                    text-align: center;
                    margin-top: 2px;
                }
            </style>
        `;

        // 綁定拉桿事件
        document.getElementById('dmg-slider').addEventListener('input', (e) => {
            document.getElementById('dmg-val-display').innerText = e.target.value + ' 萬';
            this.updateStats(); // 即時更新
        });

        // 同步全域區域設定到 API 選項
        const apiServer = document.getElementById('api-server');
        if (apiServer) {
            apiServer.value = window.PCRDatabase.currentRegion;
        }
    },

    parseInput() {
        const input = document.getElementById('stats-json-input').value.trim();
        const statusEl = document.getElementById('parse-status');
        
        if (!input) {
            statusEl.innerText = "請先貼上資料";
            return;
        }

        try {
            let data = JSON.parse(input);
            // 嘗試解開常見的外層包裹 (如果 API 回傳 { code: 200, data: [...] })
            if (data.data && Array.isArray(data.data)) {
                data = data.data;
            } else if (data.list && Array.isArray(data.list)) {
                data = data.list;
            }
            
            if (!Array.isArray(data)) {
                throw new Error("找不到有效的陣列資料");
            }

            this.rawData = data;
            this.normalizeData();
            
            statusEl.innerText = `成功解析 ${this.parsedTasks.length} 筆作業資料！`;
            
            // 顯示控制面板並初始化月份
            document.getElementById('stats-controls').style.display = 'block';
            this.initMonthCheckboxes();
            
            // 初次計算
            this.updateStats();

        } catch (e) {
            statusEl.innerText = "解析失敗: " + e.message;
            console.error(e);
        }
    },

    async loadLocalData(month, server) {
        const statusEl = document.getElementById('api-status');
        const filename = month === 'merged_bulk' ? 'gvg_data_merged_bulk.json' : `gvg_data_${month}_${server}.json`;
        
        statusEl.innerText = `正在讀取本地預存檔案: ${filename}...`;
        statusEl.style.color = "#aaa";
        
        try {
            const response = await fetch(filename);
            if (!response.ok) throw new Error("找不到預存檔案，請確認檔案是否存在。");
            
            const data = await response.json();
            document.getElementById('stats-json-input').value = JSON.stringify(data, null, 2);
            this.parseInput();
            
            statusEl.innerText = "✅ 本地預存數據載入成功！";
            statusEl.style.color = "#4caf50";
        } catch (e) {
            statusEl.innerText = "❌ 載入失敗: " + e.message;
            statusEl.style.color = "#ff6b6b";
        }
    },

    async fetchFromAPI() {
        const server = document.getElementById('api-server').value;
        const clanBattleId = document.getElementById('api-cb-id').value.trim();
        const stage = parseInt(document.getElementById('api-stage').value);
        const statusEl = document.getElementById('api-status');

        if (!clanBattleId) {
            statusEl.innerText = "⚠️ 請輸入期次 (例如: 202604)";
            return;
        }

        statusEl.innerText = "連線中... 請稍候...";
        statusEl.style.color = "#aaa";

        try {
            const response = await fetch('https://aikurumi.cn/api/pcr/gvgTask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ server, clanBattleId, stage })
            });

            if (!response.ok) throw new Error('伺服器回應錯誤: ' + response.status);
            
            const data = await response.json();
            
            // 將抓取到的資料放到 textarea，既能當作暫存，也方便你檢查格式
            document.getElementById('stats-json-input').value = JSON.stringify(data, null, 2);
            
            // 直接調用解析邏輯
            this.parseInput();
            
            statusEl.innerText = "✅ 抓取成功！已自動完成解析與統計。";
            statusEl.style.color = "#4caf50";
        } catch (e) {
            statusEl.innerText = "❌ 抓取失敗: " + e.message + " (可能是對方阻擋跨網域請求，請改用手動貼上備案)";
            statusEl.style.color = "#ff6b6b";
            console.error(e);
        }
    },

    // 將各種格式的 API JSON 正規化為標準模型
    normalizeData() {
        this.parsedTasks = [];
        this.availableMonths.clear();

        this.rawData.forEach(item => {
            try {
                // 嘗試提取欄位 (以 aikurumi 格式為基礎，並兼容其他可能)
                let taskId = item.id || item.taskId || Math.random().toString();
                let month = item.clanBattleId || item.month || 'Unknown';
                // 有些網頁 boss 是 1-5，有些用 stage 或 phase
                let bossId = item.bossId || item.bossNum || item.enemyNum || item.stage || 1; 
                let damage = item.expectedDamage || item.damage || 0;
                
                // 提取角色
                let characters = [];
                let charList = item.charas || item.characters || item.units || [];
                
                charList.forEach(c => {
                    if (c.prefabId) characters.push({ id: c.prefabId, name: c.unitName || '未知' });
                    else if (c.id) characters.push({ id: c.id, name: c.name || '未知' });
                    else if (typeof c === 'number' || typeof c === 'string') characters.push({ id: c, name: c });
                });

                if (characters.length > 0) {
                    this.parsedTasks.push({
                        taskId: String(taskId),
                        month: String(month),
                        bossId: parseInt(bossId),
                        damage: parseInt(damage),
                        characters: characters
                    });
                    this.availableMonths.add(String(month));
                }
            } catch (e) {
                console.warn("跳過一筆無法解析的資料:", item);
            }
        });
    },

    initMonthCheckboxes() {
        const container = document.getElementById('month-checkboxes');
        container.innerHTML = '';
        
        // 排序月份 (由大到小)
        const sortedMonths = Array.from(this.availableMonths).sort().reverse();
        
        sortedMonths.forEach((m, idx) => {
            const id = 'chk-month-' + m;
            container.innerHTML += `
                <label style="display:flex; align-items:center; gap:5px; cursor:pointer; background:rgba(255,255,255,0.1); padding:5px 10px; border-radius:4px;">
                    <input type="checkbox" class="month-filter-chk" value="${m}" ${idx === 0 ? 'checked' : ''} onchange="UsageStatsModule.updateStats()">
                    ${m}
                </label>
            `;
        });
    },

    // 核心管線：過濾與聚合
    updateStats() {
        // 1. 獲取過濾條件
        const selectedMonths = Array.from(document.querySelectorAll('.month-filter-chk:checked')).map(el => el.value);
        const minDmg = parseInt(document.getElementById('dmg-slider').value) * 10000; // 萬轉回實際數值

        // 2. 執行過濾 (Filter Layer)
        const validTasks = this.parsedTasks.filter(task => {
            return selectedMonths.includes(task.month) && task.damage >= minDmg;
        });

        const totalValid = validTasks.length;
        document.getElementById('valid-task-count').innerText = `(共 ${totalValid} 筆符合條件的作業)`;
        
        if (totalValid === 0) {
            document.getElementById('leaderboard-container').innerHTML = '<div style="opacity:0.5; padding:20px;">沒有符合條件的作業</div>';
            document.getElementById('stats-result-area').style.display = 'block';
            return;
        }

        // 3. 執行聚合 (Aggregation Layer)
        const charStats = {};
        const charNames = {}; // 暫存名稱

        validTasks.forEach(task => {
            task.characters.forEach(char => {
                const cid = char.id;
                charNames[cid] = char.name; // 紀錄名稱
                
                if (!charStats[cid]) {
                    charStats[cid] = {
                        count: 0,
                        byBoss: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 }
                    };
                }
                charStats[cid].count++;
                
                // 防錯機制，確保 bossId 在 1~5 之間
                let bId = task.bossId;
                if (bId >= 1 && bId <= 5) {
                    charStats[cid].byBoss[bId]++;
                } else if (bId > 5) {
                    // 有些 API 可能是以 1-15 代表三週目的 1-5王，取餘數
                    bId = bId % 5 === 0 ? 5 : bId % 5;
                    if (charStats[cid].byBoss[bId] !== undefined) charStats[cid].byBoss[bId]++;
                }
            });
        });

        // 4. 排序並渲染
        const sortedResults = Object.entries(charStats).map(([id, data]) => ({
            id,
            name: charNames[id],
            count: data.count,
            rate: data.count / totalValid,
            byBoss: data.byBoss
        })).sort((a, b) => b.count - a.count);

        this.renderLeaderboard(sortedResults);
    },

    renderLeaderboard(results) {
        document.getElementById('stats-result-area').style.display = 'block';
        const container = document.getElementById('leaderboard-container');
        
        let html = '';
        results.slice(0, 30).forEach((res, index) => { // 顯示前 30 名
            const rateStr = (res.rate * 100).toFixed(1) + '%';
            
            // 處理頭像 URL
            let imgUrl = `https://redive.estertion.win/icon/unit/${res.id}.webp`;
            if (String(res.id).length === 6 && !String(res.id).endsWith('31')) {
                // 如果是 6 碼且結尾不是 31，可能需要替換
                imgUrl = `https://redive.estertion.win/icon/unit/${String(res.id).substring(0,4)}31.webp`;
            }

            // 處理 Boss 分佈條
            let maxBossCount = Math.max(...Object.values(res.byBoss));
            if(maxBossCount === 0) maxBossCount = 1; // 避免除以 0
            
            let bossHtml = '';
            for(let i=1; i<=5; i++) {
                const count = res.byBoss[i] || 0;
                const pct = (count / maxBossCount) * 100;
                bossHtml += `
                    <div style="flex:1; display:flex; flex-direction:column;">
                        <div class="boss-bar">
                            <div class="boss-bar-fill" style="height: ${pct}%;"></div>
                        </div>
                        <div class="boss-label">${i}王</div>
                    </div>
                `;
            }

            html += `
                <div class="stat-card">
                    <div style="font-weight:bold; width:20px; text-align:center; opacity:0.5;">${index + 1}</div>
                    <div class="stat-avatar">
                        <img src="${imgUrl}" onerror="this.src='https://redive.estertion.win/icon/unit/000000.webp'">
                    </div>
                    <div class="stat-info">
                        <div class="stat-name">
                            <span>${res.name}</span>
                            <span style="color:var(--accent-color);">${res.count} 次 (${rateStr})</span>
                        </div>
                        <div class="stat-bar-bg">
                            <div class="stat-bar-fill" style="width: ${res.rate * 100}%;"></div>
                        </div>
                        <div style="display:flex; gap:10px; margin-top:5px; height:20px;">
                            ${bossHtml}
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
};
