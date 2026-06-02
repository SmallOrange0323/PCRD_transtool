/**
 * PCRD Data Hub - 劇情地圖模組 (QuestMapModule)
 * 負責從 SQLite 載入主線劇情列表，並提供精美的 SVG 世界地圖互動與劇情章節檢視。
 */

const QuestMapModule = {
    stories: [],
    currentPart: 1, // 1: 第一部, 2: 第二部, 3: 第三部
    activeStoryId: null,

    // 地標座標定義 (X%, Y% 用於在地圖上的相對定位)
    landmarks: {
        "序章": { x: 50, y: 50, name: "阿斯特萊亞大陸", desc: "冒險故事的起點，主角在此與美食殿堂的夥伴們相遇。" },
        "第1章": { x: 45, y: 52, name: "蘭德索爾平原", desc: "包圍在蘭德索爾城外的廣闊綠地，也是美食殿堂首次討伐野怪的場所。" },
        "第2章": { x: 48, y: 46, name: "蘭德索爾城外街道", desc: "通往繁華蘭德索爾的街道，許多公會在此活動。" },
        "第3章": { x: 52, y: 44, name: "真步真步王國境界", desc: "充滿童話色彩的區域，野獸與妖精的居住地。" },
        "第4章": { x: 55, y: 48, name: "咲戀救濟院", desc: "咲戀打理的溫馨福利機構，也是美食殿堂時常造訪的地方。" },
        "第5章": { x: 42, y: 42, name: "密林防線", desc: "地處偏遠且充滿危險的森林，隱藏著強大的魔物。" },
        "第6章": { x: 38, y: 50, name: "維修沙灘", desc: "夏日消暑勝地，也是在此迎擊了大量魔物的大海戰戰場。" },
        "第7章": { x: 58, y: 55, name: "索爾之塔腳下", desc: "直通天際的傳說之塔，被神聖光輝環繞。" },
        "第8章": { x: 50, y: 35, name: "牧場 (伊莉莎白牧場)", desc: "牛羊成群的肥沃牧場，曾在此爆發過嚴重的魔物襲擊。" },
        "第9章": { x: 47, y: 62, name: "地下城地下深淵", desc: "封印在城底的黑暗迷宮，藏有古代世界科技的遺骸。" },
        "第10章": { x: 62, y: 40, name: "暮光流星駐地", desc: "流星公會成員們研究未知學問與世界奧秘的隱密據點。" },
        "第11章": { x: 32, y: 45, name: "露娜塔", desc: "每逢月圓之夜便會顯現的奇異高塔，考驗著冒險者的實力。" },
        "第12章": { x: 52, y: 25, name: "艾爾皮斯山脈腳下", desc: "白雪皚皚的巍峨大山，通往神殿的必經之路。" },
        "第13章": { x: 52, y: 20, name: "艾爾皮斯山頂雪原", desc: "寒風凜冽的巔峰雪原，主角群與霸瞳天星爆發決戰的地點之一。" },
        "第14章": { x: 50, y: 48, name: "蘭德索爾皇宮外圍", desc: "權力頂端的宏偉城堡，決戰前夕防線崩塌的血戰之地。" },
        "第15章": { x: 50, y: 48, name: "王都皇宮覲見之間", desc: "最終決戰舞台！主角群在此與霸瞳天星展開了阿斯特萊亞命運之戰。" },
        // 第二部/第三部 地標
        "第2部": { x: 68, y: 30, name: "索爾神殿 (Sol Palace)", desc: "第二部關鍵舞台，世界底層機制的核心中樞。" },
        "第3部": { x: 75, y: 65, name: "厄莉絲的虛無世界", desc: "充滿毀滅與重塑危機的崩壞大陸，新的命運在此交錯。" }
    },

    // 取得地標配置的輔助函式
    getLandmarkForChapter(chapterName) {
        if (chapterName.includes("第3部")) return this.landmarks["第3部"];
        if (chapterName.includes("第2部")) return this.landmarks["第2部"];
        
        for (let key in this.landmarks) {
            if (chapterName.includes(key)) {
                return this.landmarks[key];
            }
        }
        return this.landmarks["序章"]; // 預設
    },

    // 取得 YouTube 劇情播放清單 (提供一鍵跳轉)
    getYouTubePlaylist(part) {
        if (part === 1) {
            return "https://www.youtube.com/embed/videoseries?list=PLyq2B7I_N8v_39rN0n4zB7J28VwVz0c_N"; // 美食殿堂第一部主線
        } else if (part === 2) {
            return "https://www.youtube.com/embed/videoseries?list=PLyq2B7I_N8v_RkZtO54N66jK5uH6bXW9o"; // 第二部
        }
        return "https://www.youtube.com/embed/videoseries?list=PLyq2B7I_N8v_aM-1xMvS7z8z_wM75pE_E"; // 第三部
    },

    // 取得官方遊戲大地圖原畫
    getMapBackgroundImage(part) {
        if (part === 1) {
            // 第一部官方原版地圖：蘭德索爾平原與遠方的索爾之塔 (官方美術大圖 105431)
            return "https://redive.estertion.win/card/full/105431.webp";
        } else if (part === 2) {
            // 第二部官方原版地圖：索爾神殿之頂 (官方美術大圖 109431)
            return "https://redive.estertion.win/card/full/109431.webp";
        }
        // 第三部官方原版地圖：異世界崩壞場景 (官方美術大圖 106031)
        return "https://redive.estertion.win/card/full/106031.webp";
    },

    async loadData() {
        if (this.stories.length > 0) return;
        
        const sql = `
            SELECT story_id, title, sub_title, story_group_id 
            FROM story_detail 
            WHERE story_id >= 2000000 AND story_id < 3000000
            ORDER BY story_id ASC
        `;
        
        try {
            const rawData = await window.PCRDatabase.runQuery(sql);
            
            // 由於 JS 讀取 utf-8 text 正常，我們可以直接處理
            this.stories = rawData.map(row => ({
                id: row.story_id,
                chapter: row.title || "",
                title: row.sub_title || "",
                groupId: row.story_group_id
            }));
            
            console.log(`[QuestMapModule] 成功載入 ${this.stories.length} 筆主線劇情資訊`);
        } catch (err) {
            console.error("[QuestMapModule] 載入劇情數據失敗:", err);
        }
    },

    getFilteredStories() {
        return this.stories.filter(s => {
            const isPart3 = s.chapter.includes("第3部");
            const isPart2 = s.chapter.includes("第2部") && !isPart3;
            const isPart1 = !isPart2 && !isPart3;
            
            if (this.currentPart === 1) return isPart1;
            if (this.currentPart === 2) return isPart2;
            return isPart3;
        });
    },

    async render() {
        await this.loadData();
        const tab = document.getElementById('map-tab');
        
        const filtered = this.getFilteredStories();
        const firstStory = filtered[0] || {};
        const mapBg = this.getMapBackgroundImage(this.currentPart);
        
        tab.innerHTML = `
            <div class="map-container glass-card">
                <div class="map-header">
                    <h2>🗺️ 阿斯特萊亞大陸劇情編年史地圖</h2>
                    <p class="subtitle">追隨美食殿堂與各公會，在冒險地圖上回顧壯麗的主線故事與台詞</p>
                </div>
                
                <!-- 部別切換器 -->
                <div class="part-selector">
                    <button class="part-btn ${this.currentPart === 1 ? 'active' : ''}" onclick="QuestMapModule.switchPart(1)">第一部：霸瞳天星篇</button>
                    <button class="part-btn ${this.currentPart === 2 ? 'active' : ''}" onclick="QuestMapModule.switchPart(2)">第二部：厄莉絲與救贖篇</button>
                    <button class="part-btn ${this.currentPart === 3 ? 'active' : ''}" onclick="QuestMapModule.switchPart(3)">第三部：全新世界篇</button>
                </div>
                
                <div class="map-layout">
                    <!-- 地圖視覺區 -->
                    <div class="map-visual-area">
                        <!-- 載入實際的遊戲大地圖美術原畫 -->
                        <div class="world-map" id="world-map-canvas" style="background-image: url('${mapBg}'); background-size: cover; background-position: center;">
                            <!-- 帶有網格線與神秘背景的 SVG 地圖 -->
                            <svg class="map-grid" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
                                <defs>
                                    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                                        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255, 255, 255, 0.03)" stroke-width="1"/>
                                    </pattern>
                                </defs>
                                <rect width="100%" height="100%" fill="url(#grid)" />
                                <!-- 連線路徑 -->
                                <path id="story-trajectory" d="" fill="none" stroke="rgba(255, 107, 157, 0.4)" stroke-width="3" stroke-dasharray="8 4" />
                            </svg>
                            
                            <!-- 動態生成的互動地標 -->
                            <div id="map-landmarks-container"></div>
                        </div>
                    </div>
                    
                    <!-- 劇情控制台與列表 -->
                    <div class="map-control-panel glass-card">
                        <div class="panel-section-title">📖 劇情章節清單</div>
                        <div class="story-list-scrollbar">
                            <div class="story-list">
                                ${filtered.map(s => `
                                    <div class="story-item ${this.activeStoryId === s.id ? 'active' : ''}" 
                                         id="story-item-${s.id}"
                                         onclick="QuestMapModule.selectStory(${s.id})">
                                        <div class="story-ch-badge">${s.chapter.split(' ')[0]}</div>
                                        <div class="story-item-content">
                                            <div class="story-item-ch">${s.chapter.replace(/^第\d+部\s*/, '')}</div>
                                            <div class="story-item-title">${s.title}</div>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 底部詳細劇情抽屜面板 -->
                <div class="story-detail-drawer glass-card" id="story-detail-drawer" style="display: none;">
                    <div class="drawer-header">
                        <div class="drawer-title-row">
                            <span id="drawer-chapter-name" class="ch-tag">第 1 章</span>
                            <h3 id="drawer-story-title" style="margin: 0; color: #fff;">話標題</h3>
                        </div>
                        <button class="btn-close-drawer" onclick="QuestMapModule.closeDrawer()">關閉詳情 ×</button>
                    </div>
                    
                    <div class="drawer-body">
                        <div class="drawer-info-col">
                            <div class="landmark-info-card glass-card">
                                <div class="landmark-title">📍 冒險地點：<span id="drawer-loc-name">索爾之塔</span></div>
                                <p id="drawer-loc-desc" class="landmark-desc">地點描述...</p>
                            </div>
                            
                            <!-- 經典台詞區 -->
                            <div class="classic-dialogue glass-card">
                                <div class="dialogue-header">📜 經典場景節錄</div>
                                <div id="drawer-dialogue-content" class="dialogue-text">
                                    正在讀取本章節的經典台詞...
                                </div>
                            </div>
                        </div>
                        
                        <!-- 劇情影片播放器區 -->
                        <div class="drawer-video-col glass-card">
                            <div class="video-container">
                                <iframe id="drawer-video-frame" 
                                        src="" 
                                        title="PCRD Story Video" 
                                        frameborder="0" 
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                                        allowfullscreen>
                                </iframe>
                            </div>
                            <div class="video-tip">📺 點擊觀看社群精心整理的本章節繁中劇情影片</div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 預設渲染地圖地標與軌跡
        this.renderMapElements();
        
        // 預設選擇第一話
        if (filtered.length > 0) {
            this.selectStory(filtered[0].id);
        }
    },

    switchPart(part) {
        this.currentPart = part;
        this.activeStoryId = null;
        this.render();
    },

    // 渲染地圖上的地標點與畫出推進線
    renderMapElements() {
        const container = document.getElementById('map-landmarks-container');
        const pathElement = document.getElementById('story-trajectory');
        const filtered = this.getFilteredStories();
        
        if (!container) return;
        container.innerHTML = "";

        // 收集所有在當前部別中獨特的地標坐標，用來繪製前進路徑
        const uniquePoints = [];
        const addedLandmarks = new Set();

        filtered.forEach(s => {
            const loc = this.getLandmarkForChapter(s.chapter);
            const landmarkKey = loc.name;
            
            if (!addedLandmarks.has(landmarkKey)) {
                addedLandmarks.add(landmarkKey);
                uniquePoints.push(loc);
                
                // 渲染地標 HTML
                const marker = document.createElement('div');
                marker.className = `map-landmark-node ${this.activeStoryId && this.getLandmarkForChapter(this.stories.find(x => x.id === this.activeStoryId)?.chapter).name === landmarkKey ? 'focused' : ''}`;
                marker.style.left = `${loc.x}%`;
                marker.style.top = `${loc.y}%`;
                marker.setAttribute('title', loc.name);
                marker.innerHTML = `
                    <div class="landmark-pulse"></div>
                    <div class="landmark-dot"></div>
                    <div class="landmark-label">${loc.name}</div>
                `;
                
                container.appendChild(marker);
            }
        });

        // 繪製軌跡 SVG Path
        const mapCanvas = document.getElementById('world-map-canvas');
        if (mapCanvas && pathElement && uniquePoints.length > 1) {
            const width = mapCanvas.clientWidth;
            const height = mapCanvas.clientHeight;
            
            let pathD = "";
            uniquePoints.forEach((pt, index) => {
                const px = (pt.x / 100) * width;
                const py = (pt.y / 100) * height;
                if (index === 0) {
                    pathD += `M ${px} ${py}`;
                } else {
                    // 使用二次貝茲曲線使線條更平滑柔和
                    const prevPt = uniquePoints[index - 1];
                    const pprevX = (prevPt.x / 100) * width;
                    const pprevY = (prevPt.y / 100) * height;
                    const controlX = (pprevX + px) / 2;
                    const controlY = pprevY - 30; // 向上微彎
                    pathD += ` Q ${controlX} ${controlY}, ${px} ${py}`;
                }
            });
            
            pathElement.setAttribute('d', pathD);
        }
    },

    // 選擇特定章節
    async selectStory(storyId) {
        this.activeStoryId = storyId;
        
        // 移除所有列表選中狀態並為當前項加上 active
        document.querySelectorAll('.story-item').forEach(el => el.classList.remove('active'));
        const activeItem = document.getElementById(`story-item-${storyId}`);
        if (activeItem) activeItem.classList.add('active');

        const story = this.stories.find(s => s.id === storyId);
        if (!story) return;

        // 地標高亮聚焦
        const loc = this.getLandmarkForChapter(story.chapter);
        this.renderMapElements(); // 重新渲染以更新地標高亮狀態

        // 取得經典對話與大綱
        const drawer = document.getElementById('story-detail-drawer');
        const chNameEl = document.getElementById('drawer-chapter-name');
        const titleEl = document.getElementById('drawer-story-title');
        const locNameEl = document.getElementById('drawer-loc-name');
        const locDescEl = document.getElementById('drawer-loc-desc');
        const videoFrame = document.getElementById('drawer-video-frame');
        const dialogueEl = document.getElementById('drawer-dialogue-content');

        if (drawer) {
            drawer.style.display = 'block';
            
            // 設定標題與描述
            chNameEl.innerText = story.chapter.split(' ')[0] || "主線";
            titleEl.innerText = story.title || "話名稱";
            locNameEl.innerText = loc.name;
            locDescEl.innerText = loc.desc;

            // 載入 YouTube 播放清單嵌入連結 (依照當前部別)
            const videoUrl = this.getYouTubePlaylist(this.currentPart);
            if (videoFrame.getAttribute('src') !== videoUrl) {
                videoFrame.setAttribute('src', videoUrl);
            }

            // 本地載入 So-net 官方繁中逐字劇情文本對白
            dialogueEl.innerHTML = `<div class="dialogue-line"><span class="speaker">【系統】</span><span class="speech-text" style="color: #ffa94d;">正在從硬碟載入本地 So-net 官方劇情對白...</span></div>`;
            
            fetch(`./story/${storyId}.json`)
                .then(res => {
                    if (!res.ok) throw new Error("檔案不存在");
                    return res.json();
                })
                .then(dialogueList => {
                    if (dialogueList && dialogueList.length > 0) {
                        let html = "";
                        dialogueList.forEach(line => {
                            let speakerColor = "#4dadff"; // 預設藍色
                            if (line.name === "佩可莉姆") speakerColor = "#ff6b9d"; // 櫻花粉
                            if (line.name === "凱留") speakerColor = "#cc5cff"; // 貓咪紫
                            if (line.name === "可可蘿") speakerColor = "#4dfa7b"; // 嫩芽綠
                            if (line.name === "旁白" || line.name === "【系統】") speakerColor = "#ffa94d"; // 系統橘
                            
                            html += `
                                <div class="dialogue-line" style="margin-bottom: 12px; line-height: 1.6;">
                                    <span class="speaker" style="color: ${speakerColor}; font-weight: 700; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 2px;">
                                        【${line.name}】
                                    </span>
                                    <span class="speech-text" style="color: #fff; margin-left: 6px; word-break: break-all;">
                                        ${line.words}
                                    </span>
                                </div>
                            `;
                        });
                        dialogueEl.innerHTML = html;
                    } else {
                        throw new Error("格式空白");
                    }
                })
                .catch(err => {
                    console.warn("[QuestMapModule] 無法讀取本地對白檔案, 啟用備用大綱描述:", err);
                    dialogueEl.innerHTML = `
                        <div class="dialogue-line">
                            <span class="speaker">【系統大綱】</span>
                            <span class="speech-text">「${story.chapter} - ${story.title}」故事正式拉開序幕！玩家可透過右側影片嵌入視窗直接觀看該話的繁體中文完整配音與劇情演出。</span>
                        </div>
                        <div class="dialogue-line" style="margin-top: 12px; border-top: 1px dashed rgba(255, 255, 255, 0.1); padding-top: 8px;">
                            <span class="speaker">⚖️ 冒險手札：</span>
                            <span class="speech-text" style="color: #ffa94d;">主角在此處獲得了力量的指引，美食殿堂的羈絆得到了進一步的昇華。請先執行 download_stories.py 下載官方繁中文本。</span>
                        </div>
                    `;
                });
        }
    },

    closeDrawer() {
        const drawer = document.getElementById('story-detail-drawer');
        if (drawer) drawer.style.display = 'none';
    }
};
