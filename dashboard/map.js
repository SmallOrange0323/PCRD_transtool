/**
 * PCRD Data Hub - 主線劇情放映與編年史模組 (QuestMapModule)
 * 負責從 SQLite 載入主線劇情列表，將其重構為階層式的「章 ➔ 話」摺疊選單，
 * 並提供 So-net 官方主線影片與官方文本大綱的精確對接。
 */

const QuestMapModule = {
    stories: [],
    events: [],
    eventStories: [],
    chapters: {}, // 按「章」分組的劇情字典
    currentPart: 1, // 1: 第一部, 2: 第二部, 3: 第三部
    activeTabType: 'main', // 'main' | 'event'
    isDialogueExpanded: true,
    activeStoryId: null,
    expandedChapter: null, // 當前展開的章節名稱 (例如: "第1章")
    speakerAvatars: {}, // 快取角色名稱與頭像 ID 映射表
    appearanceMap: null, // 登場角色快取
    charaDetailCache: {}, // 角色 profile 快取
    activeSummaryTab: 'episode', // 'episode' (單話大綱) | 'chapter' (整章摘要)
    speakerSearchQuery: "", // 搜尋登場角色的關鍵字
    speakerSortOrder: "appearances-desc", // 登場角色排序方式



    // 每一章的官方標題/地標標題對照表 (完全對齊 So-net 台版繁中官方翻譯)
    chapterTitles: {
        1: {
            "序章": "阿斯特萊亞大陸",
            "第1章": "蘭德索爾平原",
            "第2章": "蘭德索爾城外街道",
            "第3章": "真步真步王國境界",
            "第4章": "咲戀救濟院",
            "第5章": "密林防線",
            "第6章": "維修斯海灘",
            "第7章": "索爾之塔腳下",
            "第8章": "伊莉莎白牧場",
            "第9章": "地下城地下深淵",
            "第10章": "暮光流星群駐地",
            "第11章": "露娜的塔",
            "第12章": "埃爾皮斯山脈腳下",
            "第13章": "埃爾皮斯山頂雪原",
            "第14章": "蘭德索爾皇宮外圍",
            "第15章": "王都皇宮謁見之間"
        },
        2: {
            "第1章": "憤怒軍團篇",
            "第2章": "翡翠的墓碑",
            "第3章": "萬能人偶",
            "第4章": "玩偶圓舞曲",
            "第5章": "跨越詛咒的束縛",
            "第6章": "大江戶奇聞",
            "第7章": "王應有的姿態",
            "第8章": "七冠救出作戰",
            "第9章": "厄莉絲",
            "第10章": "珊托魯斯迎擊戰",
            "第11章": "遊戲結束",
            "第12章": "伊麗莎白牧場",
            "第13章": "毀滅的序曲",
            "第14章": "漆黑薔薇城",
            "第15章": "死鬥的序幕",
            "第16章": "在即將終結的世界裡"
        },
        3: {
            "第1章": "幻變少女篇",
            "第2章": "FUN FUN農場",
            "第3章": "大夢想樂園",
            "第4章": "前往另一個背面世界",
            "第5章": "吉歐‧格黑納",
            "第6章": "繚繞的水霧之中",
            "第7章": "熔鐵公主",
            "第8章": "四位公主",
            "第9章": "救出雪菲",
            "第10章": "死者們的迎接",
            "第11章": "美食殿堂vs三魔姬屬",
            "第12章": "攻略黑曜宮",
            "第13章": "第二次公主會議",
            "第14章": "龍之浮島",
            "第15章": "幻境的下午茶時間"
        }
    },

    // 整章大綱摘要簡介
    chapterSummaries: {
        1: {
            "序章": "描述主角祐樹自天而降，失去所有記憶，與引導者可可蘿相遇的起點。",
            "第1章": "貪吃佩可、可可蘿與祐樹成立「美食殿堂」，並與凱留相遇，展開在蘭德索爾的日常與美味冒險。",
            "第2章": "介紹蘭德索爾的日常運作，各公會紛紛登場，同時神秘的魔物陰影開始顯現。",
            "第3章": "美食殿堂與真步真步王國接觸，逐漸揭開蘭德索爾背後的不安定要素與暗影襲擊。",
            "第4章": "咲戀救濟院在日常中提供救濟，然而霸瞳皇帝的陰謀魔爪也開始向外延伸。",
            "第5章": "美食殿堂前往密林調查異變，發現了時空裂縫與古怪的暗影魔物。",
            "第6章": "眾人在沙灘享受短暫的維修與度假時光，但更強大的黑影悄然逼近。",
            "第7章": "索爾之塔的傳說引導眾人前去探索，世界的真實與謎團逐漸浮現。",
            "第8章": "在伊莉莎白牧場與夥伴們防守魔物的狂潮，加深了彼此之間的羈絆。",
            "第9章": "深入探索地下城底部的巨大深淵，並首次直面霸瞳皇帝的恐怖壓迫感。",
            "第10章": "與暮光流星群等強大公會合作，為阻止霸瞳皇帝的野心進行全面戰備。",
            "第11章": "露娜的塔異變引發各路公會聯手攀登，揭示更多世界之謎與前作暗示。",
            "第12章": "在埃爾皮斯山脈下進行慘烈的遭遇戰，各方勢力命運交織在一起。",
            "第13章": "山頂雪原的決戰，直面世界的真相與犧牲的抉擇，主角群身陷絕境。",
            "第14章": "大軍兵臨蘭德索爾皇宮外圍，美食殿堂與反抗軍展開總攻擊。",
            "第15章": "在皇宮謁見之間與霸瞳皇帝展開宿命決戰，誓言奪回被篡改的未來與日常。"
        },
        2: {
            "第1章": "決戰後世界重置，全新敵人與謎之少女厄莉絲的陰影籠罩，冒險再度啟程。",
            "第2章": "圍繞世界之卵展開新爭奪，美食殿堂與新的同盟攜手防禦神秘勢力。",
            "第3章": "救贖之火在廢墟中點燃，透過大家的微笑與支持，尋找擊碎絕望的方法。",
            "第4章": "命運的鐘聲急促敲響，厄莉絲的滅世計劃逐漸明朗，絕望的暗黑籠罩蘭德索爾。",
            "第5章": "在深淵的呼喚中找尋光芒指引，同伴們不屈不撓，踏上反擊的第一步。",
            "第6章": "成功突破中央終端，破壞神之防線，最後的終焉之門已在眼前。",
            "第7章": "約定之時已到，所有的羈絆在最後的舞台交織，向命運發起總挑戰。",
            "第8章": "為了守護彼此生存的世界與信念，所有人燃盡力量展開最終之戰。",
            "第9章": "在奇蹟中迎來重逢，希望之歌響徹蘭德索爾，世界的輪廓重新清晰。",
            "第10章": "終焉的光輝散去，迎來全新的黎明，少年與少女們向著明天再度邁開腳步。",
            "第11章": "【惡魔偽王國軍】等公會參戰，展開激烈的跳躍遊戲，蘭德索爾的命運再度受到多方牽制。",
            "第12章": "前往伊麗莎白牧場，眾人在溫馨與逃亡的日常中，逐步揭開彌勒暗中操弄的巨大秘密。",
            "第13章": "彌勒的陰謀逐漸明朗，以人質要脅各方，【森林守衛】等公會為了守護蘭德索爾全力奮戰。",
            "第14章": "冰龍與魁首龍等強大災厄降臨，眾人在絕境中展現出真摯的羈絆，勇於直面黑暗的考驗。",
            "第15章": "各路勇士齊聚一堂，做好最後的決意與備戰，誓言守護與同伴們共同擁有的珍貴回憶。",
            "第16章": "七冠史無前例地攜手共鬥，展開奪回索爾魔珠的最後決戰，將第二部的宿命帶向終焉的解答。"
        },
        3: {
            "第1章": "來到全新的陌生世界，開始了不可思議的校園與日常生活，但未知的謎團依然存在。",
            "第2章": "幕後黑手在暗中窺伺，黑白兩股對立勢力逐漸浮上檯面，虛無世界的世界觀展現。",
            "第3章": "追尋失去的關鍵記憶與交錯的世界軌跡，為守護這份新日常而再度執劍。",
            "第4章": "在全新的世界中，深夜的密會伴隨著突然的宣戰，【好朋友社】等公會再次被捲入動盪的漩渦。",
            "第5章": "妖魔人與煉獄的公主現身，眾人召開討伐神祕強敵『六凶』的作戰會議，展開新世界的反擊。",
            "第6章": "深入吉歐・格黑納的熱鬧宴會，探尋被遺漏的世界真相，同時遭遇了流浪的神祕三姊妹。",
            "第7章": "火山燃燒，蠍獅少女帶來強烈威脅，華音的叛亂讓局勢更加複雜，考驗著眾人的應變實力。",
            "第8章": "吉歐・提格尼亞的代表與各方勢力進行早餐會談，神祕的薇歐莉特與格蕾斯在此正式浮上檯面。",
            "第9章": "傀儡的絲線在暗中垂落，粉碎的願望伴隨著靈魂的歸處，讓這場新世界的探索陷入更深的迷霧。",
            "第10章": "冥府的代表者與死者們迎面而來，帶來大壞蛋大復活的混亂，眾人必須在生死邊緣展開防線。",
            "第11章": "凱留與普蕾西亞在冰雪中展開新牽絆，巨鯨城近侍與潛藏的憤怒交織，新世界的衝突逐步升溫。",
            "第12章": "在短暫的停戰與堇色悲哀後，眾人重整旗鼓，正式朝著攻略神祕『黑曜宮』的目標進發。",
            "第13章": "大江戶的公主們齊聚一堂召開第二次公主會議，面對真實的告白與考驗，做出攸關未來的決定。",
            "第14章": "尋找主人的下落，眾人登上龍之浮島，接受來自阿爾莎特的邀請，揭開更深層的世界核心。",
            "第15章": "邪惡的公主騎士們與伏龍現身，伴隨著『嚮導幼君』的謎團，命運的齒輪再度加速運轉。"
        }
    },

    // 將劇情對白中可能出現的化名、代稱或特殊版本名字，映射至資料庫 unit_data 的真實 unit_name
    // 注意：目標名必須完全符合台版 unit_data.unit_name 欄位的值
    getCharaRealName(name) {
        if (!name) return "";
        
        // 如果包含多個名字（如「貪吃佩可、普蕾西亞」或「靜流＆璃乃」），只取第一個名字進行 profile 與頭像匹配
        let singleName = name.split(/[、＆&]|和|與/)[0].trim();
        
        // 先做全名完整匹配別名
        const aliases = {
            // ===== 主線主要角色 =====
            "貪吃佩可的聲音":   "貪吃佩可",
            "大食客":           "貪吃佩可",
            "飢餓的公主":       "貪吃佩可",
            "可可蘿的聲音":     "可可蘿",
            "導引者":           "可可蘿",
            "引導者":           "可可蘿",
            "導引少女":         "可可蘿",
            "凱留的聲音":       "凱留",
            "貓耳魔法少女":     "凱留",
            // ===== 反派/劇情 NPC =====
            "霸瞳天星的聲音":   "霸瞳皇帝",
            "霸瞳天星":         "霸瞳皇帝",
            "拉比林斯達的聲音": "拉比林斯達",
            "克莉絲提娜的聲音": "克莉絲提娜",
            "露娜的聲音":       "露娜",
            "厄莉絲的聲音":     "厄莉絲",
            "雪的聲音":         "雪",
            "流夏的聲音":       "流夏",
            "暮光流星的成員":   "流夏",
            "雪菲的聲音":       "雪菲",
            "似似花的聲音":     "似似花",
            "亞里莎的聲音":     "亞里莎",
            "帆稀的聲音":       "帆稀",
            "嘉夜的聲音":       "嘉夜",
            "祈梨的聲音":       "祈梨",
            "矛依未的聲音":     "矛依未",
            // ===== 其他常見 NPC =====
            "吉塔的聲音":       "吉塔",
            "深月的聲音":       "深月",
            "克蕾琪塔的聲音":   "克蕾琪塔",
            "蘭法的聲音":       "蘭法",
            "美空的聲音":       "美空",
            "涅比亞的聲音":     "涅比亞",
            "古蕾婭的聲音":     "古蕾婭",
            "安的聲音":         "安",
            "莫妮卡的聲音":     "莫妮卡",
        };
        
        if (aliases[singleName]) return aliases[singleName];
        
        // 移除常見括號限定語，例如 "貪吃佩可（夏日）" -> "貪吃佩可"
        let clean = singleName.replace(/（[^）]+）/g, "").replace(/\([^)]+\)/g, "").trim();
        if (aliases[clean]) return aliases[clean];
        
        // 移除「的聲音」後綴
        if (clean.endsWith("的聲音")) {
            clean = clean.replace(/的聲音$/, "");
        }
        return clean;
    },

    getAvatarHtml(realName) {
        const unitId = this.speakerAvatars[realName];
        if (unitId) {
            const baseId = Math.floor(unitId / 100) * 100;
            const avatarUrl = `https://redive.estertion.win/icon/unit/${baseId + 31}.webp`;
            return `<img src="${avatarUrl}" style="width: 100%; height: 100%; object-fit: cover;" onerror="if(this.src.includes('31.webp')) { this.src=this.src.replace('31.webp', '11.webp'); } else { this.style.display='none'; this.parentNode.innerHTML='<div class=&quot;npc-avatar-placeholder&quot;>${realName.substring(0, 2)}</div>'; }">`;
        } else {
            return `<div class="npc-avatar-placeholder">${realName.substring(0, 2)}</div>`;
        }
    },

    async loadData() {
        try {
            // 預載入所有角色的 unit_id 映射，限制 ID 區間以排除劇情 dummy ID，並使用 MIN(unit_id) 取得最原始的玩家實裝角色 ID
            if (Object.keys(this.speakerAvatars).length === 0) {
                try {
                    const avatarSql = `
                        SELECT unit_name, MIN(unit_id) as unit_id 
                        FROM unit_data 
                        WHERE unit_id < 200000 AND unit_id >= 100000 
                        GROUP BY unit_name
                    `;
                    const avatarsResult = await window.PCRDatabase.runQuery(avatarSql);
                    if (avatarsResult && avatarsResult.length > 0) {
                        avatarsResult.forEach(row => {
                            this.speakerAvatars[row.unit_name] = row.unit_id;
                        });
                        console.log(`[QuestMapModule] 預載入 ${Object.keys(this.speakerAvatars).length} 筆角色頭像映射`);
                    }
                } catch (e) {
                    console.error("預載入角色頭像失敗:", e);
                }
            }

            // 載入登場角色話數映射快取
            if (!this.appearanceMap) {
                try {
                    const resp = await fetch('story/speaker_appearance.json');
                    if (resp.ok) {
                        this.appearanceMap = await resp.json();
                        console.log(`[QuestMapModule] 成功載入登場角色快取`);
                    }
                } catch (e) {
                    console.error("無法加載登場快取:", e);
                }
            }

            // 載入主線劇情
            if (this.stories.length === 0) {
                const sql = `
                    SELECT story_id, title, sub_title, story_group_id 
                    FROM story_detail 
                    WHERE story_id >= 2000000 AND story_id < 3000000
                    ORDER BY story_id ASC
                `;
                const rawData = await window.PCRDatabase.runQuery(sql);
                this.stories = rawData.map(row => ({
                    id: row.story_id,
                    chapter: row.title || "",
                    title: row.sub_title || "",
                    groupId: row.story_group_id
                }));
                console.log(`[QuestMapModule] 成功載入 ${this.stories.length} 筆主線劇情`);
            }

            // 載入活動列表
            if (this.events.length === 0) {
                const eventSql = `
                    SELECT story_group_id, title, start_time, thumbnail_id, value
                    FROM event_story_data 
                    ORDER BY start_time DESC
                `;
                this.events = await window.PCRDatabase.runQuery(eventSql);
                console.log(`[QuestMapModule] 成功載入 ${this.events.length} 筆活動主檔`);
            }

            // 載入活動劇情話數
            if (this.eventStories.length === 0) {
                const eventDetailSql = `
                    SELECT story_id, title, sub_title, story_group_id 
                    FROM event_story_detail 
                    ORDER BY story_id ASC
                `;
                const rawEventStories = await window.PCRDatabase.runQuery(eventDetailSql);
                // 【修正 Bug 1】統一格式：sub_title 映射為 title，與主線 stories 格式一致，避免話數標題顯示錯誤
                this.eventStories = rawEventStories.map(row => ({
                    story_id: row.story_id,
                    id: row.story_id,             // 加 id 別名，方便統一存取
                    story_group_id: row.story_group_id,
                    chapter: row.title || "",     // 話數分類名（如「初音的禮物大作戰 序章」）
                    title: row.sub_title || "",   // 話數小標題（官方大綱，原本在 sub_title 欄位）
                    groupId: row.story_group_id
                }));
                console.log(`[QuestMapModule] 成功載入 ${this.eventStories.length} 筆活動話數`);
            }
        } catch (err) {
            console.error("[QuestMapModule] 載入劇情數據失敗:", err);
        }
    },

    // 將資料按「部別」與「章」進行階層式分組
    groupStories() {
        this.chapters = {};
        const filtered = this.stories.filter(s => {
            const isPart3 = s.chapter.includes("第3部");
            const isPart2 = s.chapter.includes("第2部") && !isPart3;
            const isPart1 = !isPart2 && !isPart3;
            
            if (this.currentPart === 1) return isPart1;
            if (this.currentPart === 2) return isPart2;
            return isPart3;
        });

        filtered.forEach(s => {
            const match = s.chapter.match(/^(第\d+部\s*)?([^\s]+章|[^\s]+序章|[^\s]+幕間[^\s]*)/);
            let chName = match ? match[2] : "其他章節";
            if (s.chapter.includes("序章")) chName = "序章";
            
            if (!this.chapters[chName]) {
                this.chapters[chName] = [];
            }
            this.chapters[chName].push(s);
        });
    },

    // 活動按年月分組的邏輯
    groupEventStories() {
        this.chapters = {};
        
        const sortedEvents = [...this.events].sort((a, b) => new Date(b.start_time) - new Date(a.start_time));
        
        sortedEvents.forEach(evt => {
            const date = new Date(evt.start_time);
            const timeLabel = isNaN(date.getFullYear()) ? "【未知時間】" : `【${date.getFullYear()}年${date.getMonth() + 1}月】`;
            const chName = `${timeLabel} ${evt.title}`;
            
            const childStories = this.eventStories.filter(s => s.story_group_id === evt.story_group_id);
            if (childStories.length > 0) {
                // 【修正 Bug 1 配套】eventStories 已預先 map，欄位名稱已統一，直接延展並補上 eventValue
                this.chapters[chName] = childStories.map(s => ({
                    id: s.story_id,
                    chapter: s.chapter || "",  // 活動話分類名
                    title: s.title || "",       // 話數小標題（已由 sub_title 映射）
                    groupId: s.story_group_id,
                    story_id: s.story_id,
                    eventValue: evt.value       // event_id，用於組 CDN logo URL
                }));
            }
        });
    },

    switchTabType(type) {
        this.activeTabType = type;
        this.activeStoryId = null;
        this.expandedChapter = null;
        this.render();
    },

    async render(skipAutoSelect = false) {
        await this.loadData();
        
        const tab = document.getElementById('map-tab');
        
        if (this.activeTabType === 'speaker') {
            this.renderSpeakerTab(tab);
            return;
        }

        if (this.activeTabType === 'event') {
            this.groupEventStories();
        } else {
            this.groupStories();
        }
        
        // 預設展開第一個章節
        const chapterKeys = Object.keys(this.chapters);
        if ((!this.expandedChapter || !this.chapters[this.expandedChapter]) && chapterKeys.length > 0) {
            this.expandedChapter = chapterKeys[0];
        }

        tab.innerHTML = `
            <div class="map-container">
                <div class="map-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                    <div>
                        <h2>📖 阿斯特萊亞劇情編年史</h2>
                        <p class="subtitle">階層式章節導航，載入 So-net 官方繁中劇情大綱與對話文本</p>
                    </div>
                    <!-- 類型切換器：主線 vs 活動 vs 登場角色 -->
                    <div class="category-selector" style="display: flex; gap: 12px;">
                        <button class="part-btn ${this.activeTabType === 'main' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('main')" style="font-size: 0.95rem; padding: 10px 24px;">⚔️ 主線劇情</button>
                        <button class="part-btn ${this.activeTabType === 'event' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('event')" style="font-size: 0.95rem; padding: 10px 24px;">🏆 活動劇情</button>
                        <button class="part-btn ${this.activeTabType === 'speaker' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('speaker')" style="font-size: 0.95rem; padding: 10px 24px;">👥 登場角色</button>
                    </div>
                </div>
                
                <!-- 部別切換器 (僅主線時顯示) -->
                <div class="part-selector" style="display: ${this.activeTabType === 'main' ? 'flex' : 'none'}; margin-top: 15px;">
                    <button class="part-btn ${this.currentPart === 1 ? 'active' : ''}" onclick="QuestMapModule.switchPart(1)">第一部：霸瞳天星篇</button>
                    <button class="part-btn ${this.currentPart === 2 ? 'active' : ''}" onclick="QuestMapModule.switchPart(2)">第二部：厄莉絲與救贖篇</button>
                    <button class="part-btn ${this.currentPart === 3 ? 'active' : ''}" onclick="QuestMapModule.switchPart(3)">第三部：全新世界篇</button>
                </div>
                
                <div class="map-layout" style="margin-top: 20px;">
                    <!-- 左側：官方大綱與對白面板 -->
                    <div class="map-visual-area">
                        <div class="cinema-panel" style="height: 100%;">
                            <!-- 官方大綱與冒險手札 -->
                            <div class="cinema-meta" style="height: 100%; display: flex; flex-direction: column;">
                                <div class="cinema-ch-row" style="display: flex; align-items: center; justify-content: space-between;">
                                    <div style="display: flex; align-items: center; gap: 10px;">
                                        <span id="cinema-ch-tag" class="ch-tag">第 1 章</span>
                                        <h3 id="cinema-title" style="margin: 0; color: var(--text-primary);">話標題</h3>
                                    </div>
                                </div>
                                <div class="summary-section" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; margin-top: 15px;">
                                    <!-- 頁籤選擇器：單話大綱 vs 整章摘要 -->
                                    <div class="summary-tabs" style="display: flex; border-bottom: 2px solid rgba(94, 107, 125, 0.15); margin-bottom: 10px; gap: 8px;">
                                        <button id="tab-summary-episode" class="summary-tab active" onclick="QuestMapModule.switchSummaryTab('episode')" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid var(--accent-color); color: var(--accent-color); cursor: pointer; font-weight: bold; font-size: 0.88rem;">📜 單話大綱</button>
                                        <button id="tab-summary-chapter" class="summary-tab" onclick="QuestMapModule.switchSummaryTab('chapter')" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--text-secondary); cursor: pointer; font-size: 0.88rem;">📖 整章摘要簡介</button>
                                    </div>
                                    <div id="cinema-summary" class="summary-text" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column;">
                                        點擊右側章節清單，即刻載入大綱與對白文本。
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 右側：階層式「章 ➔ 話」雙層風琴式摺疊選單 (Accordion) -->
                    <div class="map-control-panel">
                        <div class="panel-section-title">
                            📖 ${this.activeTabType === 'main' ? '主線劇情編年史目錄' : '歷年活動劇情目錄'}
                        </div>
                        <div class="story-list-scrollbar">
                            <div class="accordion-container">
                                ${chapterKeys.map((chKey, chIndex) => {
                                    const isExpanded = this.expandedChapter === chKey;
                                    const childStories = this.chapters[chKey];
                                    const safeId = `acc-item-${chIndex}`;
                                    
                                    let chTitle = "";
                                    let chIcon = isExpanded ? '📂' : '📁';
                                    
                                    if (QuestMapModule.activeTabType === 'main') {
                                        let cleanChKey = chKey;
                                        if (QuestMapModule.currentPart === 3) {
                                            if (chKey.includes("幕間")) {
                                                const chNum = chKey.replace("幕間", "").trim();
                                                cleanChKey = `${chNum} (🏙️ 現實世界篇)`;
                                            } else {
                                                cleanChKey = `${chKey} (🎮 遊戲世界)`;
                                            }
                                        }
                                        const partTitles = QuestMapModule.chapterTitles[QuestMapModule.currentPart] || {};
                                        chTitle = partTitles[chKey] ? ` - ${partTitles[chKey]}` : "";
                                        
                                        return `
                                            <div class="accordion-item ${isExpanded ? 'active' : ''}" id="${safeId}">
                                                <div class="accordion-header" onclick="QuestMapModule.toggleChapter(${chIndex})">
                                                    <div class="acc-header-title">
                                                        <span class="acc-folder-icon" style="display: flex; align-items: center; justify-content: center;">${chIcon}</span>
                                                        <span class="acc-ch-name" style="margin-left: 8px;">${cleanChKey}${chTitle}</span>
                                                    </div>
                                                    <div class="acc-count">${childStories.length} 話</div>
                                                </div>
                                                <div class="accordion-content" style="max-height: ${isExpanded ? 'none' : '0px'}">
                                                    ${childStories.map(s => `
                                                        <div class="story-item ${this.activeStoryId === s.id ? 'active' : ''}" 
                                                             id="story-item-${s.id}"
                                                             onclick="QuestMapModule.selectStory(${s.id})">
                                                            <div class="story-dot"></div>
                                                            <div class="story-item-content">
                                                                <div class="story-item-ch">${s.chapter.replace(/^(第\d+部\s*)?([^\s]+章\s*|[^\s]+序章\s*|[^\s]+幕間[^\s]*\s*)/, '')}</div>
                                                                <div class="story-item-title">${s.title}</div>
                                                            </div>
                                                        </div>
                                                    `).join('')}
                                                </div>
                                            </div>
                                        `;
                                    } else {
                                        // 活動時，chKey 本身已是 "【年月】 活動名"
                                        // 活動 logo：用 eventValue (event_id) 組 CDN URL
                                        const firstStory = childStories[0] || {};
                                        if (firstStory.eventValue) {
                                            chIcon = `<img src="https://redive.estertion.win/event_still/banner_${firstStory.eventValue}.webp" onerror="this.onerror=null; this.src='https://redive.estertion.win/icon/unit/000000.webp';" style="width: 32px; height: 32px; border-radius: 4px; object-fit: cover; border: 1px solid rgba(255,255,255,0.15);">`;
                                        }
                                        return `
                                            <div class="accordion-item ${isExpanded ? 'active' : ''}" id="${safeId}">
                                                <div class="accordion-header" onclick="QuestMapModule.toggleChapter(${chIndex})">
                                                    <div class="acc-header-title">
                                                        <span class="acc-folder-icon" style="display: flex; align-items: center; justify-content: center;">${chIcon}</span>
                                                        <span class="acc-ch-name" style="margin-left: 8px;">${chKey}</span>
                                                    </div>
                                                    <div class="acc-count">${childStories.length} 話</div>
                                                </div>
                                                <div class="accordion-content" style="max-height: ${isExpanded ? 'none' : '0px'}">
                                                    ${childStories.map(s => {
                                                        const cleanEventTitle = chKey.substring(chKey.indexOf('\u300d') + 1).trim();
                                                        let displayChapterName = s.chapter.replace(cleanEventTitle, '').trim();
                                                        if (!displayChapterName) displayChapterName = s.chapter;
                                                        return `
                                                            <div class="story-item ${this.activeStoryId === s.id ? 'active' : ''}" 
                                                                 id="story-item-${s.id}"
                                                                 onclick="QuestMapModule.selectStory(${s.id})">
                                                                <div class="story-dot"></div>
                                                                <div class="story-item-content">
                                                                    <div class="story-item-ch">${displayChapterName}</div>
                                                                    <div class="story-item-title">${s.title}</div>
                                                                </div>
                                                            </div>
                                                        `;
                                                    }).join('')}
                                                </div>
                                            </div>
                                        `;
                                    }
                                }).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 預設選擇第一話（jumpToStory 呼叫時傳入 skipAutoSelect=true 可略過，避免競態條件）
        if (!skipAutoSelect && chapterKeys.length > 0 && this.expandedChapter && this.chapters[this.expandedChapter] && this.chapters[this.expandedChapter].length > 0) {
            this.selectStory(this.chapters[this.expandedChapter][0].id);
        }
    },

    switchPart(part) {
        this.currentPart = part;
        this.activeStoryId = null;
        this.expandedChapter = null;
        this.render();
    },

    // 控制風琴選單的展開與收合（接受索引數字，避免特殊字元破壞 DOM id）
    toggleChapter(chIndex) {
        const chapterKeys = Object.keys(this.chapters);
        const chKey = chapterKeys[chIndex];
        if (!chKey) return;

        const prevChapter = this.expandedChapter;
        const prevChIndex = chapterKeys.indexOf(prevChapter);

        if (this.expandedChapter === chKey) {
            this.expandedChapter = null;
        } else {
            this.expandedChapter = chKey;
        }

        // 收合上一個展開的章節
        if (prevChIndex !== -1) {
            const prevItem = document.getElementById(`acc-item-${prevChIndex}`);
            if (prevItem) {
                prevItem.classList.remove('active');
                prevItem.querySelector('.accordion-content').style.maxHeight = "0px";
                if (this.activeTabType === 'main') {
                    prevItem.querySelector('.acc-folder-icon').innerText = "📁";
                }
            }
        }

        // 展開當前章節
        const currItem = document.getElementById(`acc-item-${chIndex}`);
        if (currItem && this.expandedChapter === chKey) {
            currItem.classList.add('active');
            const childStories = this.chapters[chKey];
            currItem.querySelector('.accordion-content').style.maxHeight = 'none';
            if (this.activeTabType === 'main') {
                currItem.querySelector('.acc-folder-icon').innerText = "📂";
            }
            
            // 自動選取該章第一話
            if (childStories.length > 0) {
                this.selectStory(childStories[0].id);
            }
        }
    },

    // 選擇並放映特定話數
    async selectStory(storyId) {
        this.activeStoryId = storyId;
        
        document.querySelectorAll('.story-item').forEach(el => el.classList.remove('active'));
        const activeItem = document.getElementById(`story-item-${storyId}`);
        if (activeItem) activeItem.classList.add('active');

        const story = this.stories.find(s => s.id === storyId) || this.eventStories.find(s => s.story_id === storyId);
        if (!story) return;

        const chTag = document.getElementById('cinema-ch-tag');
        const titleEl = document.getElementById('cinema-title');

        if (chTag && titleEl) {
            if (this.activeTabType === 'event') {
                chTag.innerText = "活動";
            } else {
                chTag.innerText = story.chapter.match(/^(第\d+部\s*)?([^\s]+)/) ? story.chapter.match(/^(第\d+部\s*)?([^\s]+)/)[2] : "主線";
            }
            titleEl.innerText = story.title || "話標題";

            await this.updateSummaryContent();
            
            if (this.isDialogueExpanded) {
                this.loadDialogue(storyId);
            }
        }
    },

    switchSummaryTab(tabType) {
        this.activeSummaryTab = tabType;
        const btnEp = document.getElementById('tab-summary-episode');
        const btnCh = document.getElementById('tab-summary-chapter');
        if (btnEp && btnCh) {
            if (tabType === 'episode') {
                btnEp.classList.add('active');
                btnEp.style.borderBottom = "2px solid var(--accent-color)";
                btnEp.style.color = "var(--accent-color)";
                btnCh.classList.remove('active');
                btnCh.style.borderBottom = "2px solid transparent";
                btnCh.style.color = "var(--text-secondary)";
            } else {
                btnCh.classList.add('active');
                btnCh.style.borderBottom = "2px solid var(--accent-color)";
                btnCh.style.color = "var(--accent-color)";
                btnEp.classList.remove('active');
                btnEp.style.borderBottom = "2px solid transparent";
                btnEp.style.color = "var(--text-secondary)";
            }
        }
        
        this.updateSummaryContent();
    },

    async updateSummaryContent() {
        const summaryEl = document.getElementById('cinema-summary');
        if (!summaryEl || !this.activeStoryId) return;

        const story = this.stories.find(s => s.id === this.activeStoryId) || this.eventStories.find(s => s.story_id === this.activeStoryId);
        if (!story) return;

        if (this.activeSummaryTab === 'episode') {
            try {
                const isEvent = this.activeTabType === 'event';
                const tableName = isEvent ? 'event_story_detail' : 'story_detail';
                const sql = `SELECT sub_title FROM ${tableName} WHERE story_id = ${this.activeStoryId}`;
                const result = await window.PCRDatabase.runQuery(sql);
                let officialSummary = "";
                if (result && result.length > 0 && result[0].sub_title) {
                    officialSummary = result[0].sub_title;
                }
                summaryEl.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 14px; text-align: left;">

                        <!-- 官方話數大綱卡片 -->
                        <div style="
                            background: linear-gradient(135deg, rgba(232,56,117,0.04) 0%, rgba(196,36,106,0.04) 100%);
                            border: 1px solid rgba(232,56,117,0.15);
                            border-radius: 12px;
                            padding: 14px 16px;
                            line-height: 1.7;
                            font-size: 0.9rem;
                            color: var(--text-primary);
                        ">
                            <div style="display:flex; align-items:center; gap:6px; margin-bottom:8px;">
                                <span style="
                                    background: var(--accent-gradient);
                                    color:#fff;
                                    font-size:0.72rem;
                                    font-weight:700;
                                    padding: 2px 10px;
                                    border-radius: 20px;
                                    letter-spacing:1px;
                                ">📌 官方大綱</span>
                            </div>
                            <p style="margin:0; color: var(--text-primary);">${officialSummary || "本話為重要主線劇情，美食殿堂的羈絆在此得到了進一步的昇華。"}</p>
                        </div>

                        <!-- 逐字台詞面板區 -->
                        <div class="dialogue-section">
                            <div class="game-dialogue-panel">
                                <!-- 頂部標題裝飾條 -->
                                <div class="game-dialogue-header" style="border-radius: 12px 12px 0 0;">✦ 劇情全文 ✦</div>
                                <!-- 登場角色頭像列 -->
                                <div id="chara-badges-bar" class="game-chara-list-bar" style="
                                    background: rgba(252,242,246,0.9);
                                    border-left: 1.5px solid rgba(232,56,117,0.15);
                                    border-right: 1.5px solid rgba(232,56,117,0.15);
                                    border-top: none;
                                    border-bottom: 1px solid rgba(232,56,117,0.1);
                                ">
                                    <span style="color: var(--text-secondary); font-size: 0.8rem;">正在載入登場角色頭像...</span>
                                </div>
                                <!-- 對白捲動區 -->
                                <div id="dialogue-board" class="game-dialogue-board" style="max-height: 360px; overflow-y: auto;">
                                    <!-- 台詞渲染容器 -->
                                </div>
                                <!-- 底部按鈕 -->
                                <div class="game-dialogue-footer" style="border-radius: 0 0 12px 12px;">
                                    <div class="game-footer-btn close" onclick="document.getElementById('dialogue-board').scrollTop = 0">⬆ 回到頂端</div>
                                    <div class="game-footer-btn skip" onclick="document.getElementById('dialogue-board').scrollTop = 99999">⬇ 跳至底端</div>
                                </div>
                            </div>
                        </div>

                    </div>
                `;
            } catch (e) {
                console.error(e);
                summaryEl.innerHTML = `<div style="color: #ff6b6b;">無法載入官方大綱。</div>`;
            }
        } else {
            // 整章摘要
            if (this.activeTabType === 'event') {
                const currentEvent = this.events.find(e => e.story_group_id === story.groupId);
                if (currentEvent) {
                    const date = new Date(currentEvent.start_time);
                    const timeLabel = isNaN(date.getFullYear()) ? "未知時間" : `${date.getFullYear()}年${date.getMonth() + 1}月`;
                    const totalEpisodes = this.eventStories.filter(s => s.groupId === currentEvent.story_group_id).length;
                    summaryEl.innerHTML = `
                        <div class="chapter-summary-box" style="text-align: left; line-height: 1.6; font-size: 0.92rem; color: var(--text-primary); padding: 15px; background: rgba(232, 56, 117, 0.03); border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.08);">
                            <span style="color: var(--accent-color); font-weight: 700; font-size: 1rem; display: block; margin-bottom: 8px;">🏆 【${currentEvent.title}】 活動介紹：</span>
                            <p style="color: var(--text-primary); margin: 0 0 10px 0; font-size: 0.88rem; line-height: 1.7;">
                                本劇情為 <strong>${timeLabel}</strong> 登場的期間限定角色活動劇情。講述了與該活動核心主角們展開的專屬冒險篇章。
                            </p>
                            <div style="font-size: 0.82rem; color: var(--text-secondary); border-top: 1px dashed rgba(232, 56, 117, 0.15); padding-top: 10px; margin-top: 10px;">
                                📅 登場時間：${currentEvent.start_time}<br>
                                📂 活動話數：共 ${totalEpisodes} 話
                            </div>
                        </div>
                    `;
                } else {
                    summaryEl.innerHTML = `
                        <div class="chapter-summary-box" style="text-align: left; line-height: 1.6; font-size: 0.92rem; color: var(--text-primary); padding: 15px; background: rgba(232, 56, 117, 0.03); border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.08);">
                            <span style="color: var(--accent-color); font-weight: 700; font-size: 1rem; display: block; margin-bottom: 8px;">🏆 活動劇情摘要：</span>
                            <p style="color: var(--text-primary); margin: 0; font-size: 0.88rem; line-height: 1.7;">暫無本活動的摘要簡介。</p>
                        </div>
                    `;
                }
            } else {
                let chName = story.chapter.match(/^(第\d+部\s*)?([^\s]+章|[^\s]+序章|[^\s]+幕間[^\s]*)/);
                let cleanChKey = chName ? chName[2] : "其他章節";
                if (story.chapter.includes("序章")) cleanChKey = "序章";

                const summaries = this.chapterSummaries[this.currentPart] || {};
                const chapterText = summaries[cleanChKey] || "暫無本章節的摘要簡介。";

                summaryEl.innerHTML = `
                    <div class="chapter-summary-box" style="text-align: left; line-height: 1.6; font-size: 0.92rem; color: var(--text-primary); padding: 15px; background: rgba(232, 56, 117, 0.03); border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.08);">
                        <span style="color: var(--accent-color); font-weight: 700; font-size: 1rem; display: block; margin-bottom: 8px;">📖 【${cleanChKey}】 劇情摘要：</span>
                        <p style="color: var(--text-primary); margin: 0; font-size: 0.88rem; text-indent: 2em; line-height: 1.7;">${chapterText}</p>
                    </div>
                `;
            }
        }
    },

    // 異步動態批次查詢對話中角色的頭像 ID
    async loadDialogueAvatars(names) {
        if (!names || names.length === 0) return;
        
        const realNames = [...new Set(names.map(n => this.getCharaRealName(n)))].filter(Boolean);
        const toQuery = realNames.filter(n => !this.speakerAvatars[n] && n !== "旁白" && n !== "【系統】");
        if (toQuery.length === 0) return;
        
        try {
            const placeholders = toQuery.map(() => '?').join(',');
            const sql = `
                SELECT unit_name, MIN(unit_id) as unit_id 
                FROM unit_data 
                WHERE unit_name IN (${placeholders}) 
                AND unit_id < 200000 
                AND unit_id >= 100000
                GROUP BY unit_name
            `;
            const result = await window.PCRDatabase.runQuery(sql, toQuery);
            if (result && result.length > 0) {
                result.forEach(row => {
                    this.speakerAvatars[row.unit_name] = row.unit_id;
                });
            }
        } catch (e) {
            console.error("[QuestMapModule] 載入對白頭像失敗:", e);
        }
    },

    async loadDialogue(storyId) {
        const board = document.getElementById('dialogue-board');
        if (!board) return;
        
        board.innerHTML = `
            <div style="text-align: center; color: rgba(255,255,255,0.5); padding: 40px 0; font-size: 0.9rem;">
                <span class="loading-spinner" style="display: inline-block; animation: spin 1s linear infinite; margin-right: 5px;">🔄</span> 正在載入本地官方繁中對白，請稍候...
            </div>
        `;
        
        try {
            const response = await fetch(`story/${storyId}.json?v=${Date.now()}`);
            if (!response.ok) {
                throw new Error("HTTP " + response.status);
            }
            
            const dialogueList = await response.json();
            
            if (!dialogueList || dialogueList.length === 0) {
                board.innerHTML = `<div style="color: rgba(255,255,255,0.4); text-align: center; font-size: 0.9rem; padding: 20px;">本話無語音對白數據。</div>`;
                return;
            }

            // 1. 動態批次拉取說話者頭像 ID（支持多發言者拆分）
            const speakerNames = [];
            dialogueList.forEach(item => {
                if (item.name) {
                    const names = item.name.split(/[、＆&]|和|與/).map(n => n.trim()).filter(Boolean);
                    names.forEach(name => {
                        if (!speakerNames.includes(name)) {
                            speakerNames.push(name);
                        }
                    });
                }
            });
            await this.loadDialogueAvatars(speakerNames);

            // 2. 渲染頂部登場角色頭像徽章列
            const badgesBar = document.getElementById('chara-badges-bar');
            if (badgesBar) {
                const validSpeakers = speakerNames.filter(n => n !== "旁白" && n !== "【系統】" && !n.includes("【選擇肢】") && !n.includes("【選擇】") && n !== "？？？");
                
                // 為了視覺清爽度：過濾掉在資料庫中查無頭像的純路人 NPC，只在頂部顯示實裝人物頭像
                const playableSpeakers = validSpeakers.filter(name => {
                    const realName = this.getCharaRealName(name);
                    return !!this.speakerAvatars[realName];
                });

                if (playableSpeakers.length === 0) {
                    badgesBar.style.display = "none";
                } else {
                    badgesBar.style.display = "flex";
                    
                    const renderedSet = new Set();
                    const badgeHtmls = [];

                    playableSpeakers.forEach(name => {
                        const realName = this.getCharaRealName(name);
                        if (renderedSet.has(realName)) return;
                        renderedSet.add(realName);

                        const unitId = this.speakerAvatars[realName];
                        let avatarUrl = "https://redive.estertion.win/icon/unit/000000.webp";
                        if (unitId) {
                            const baseId = Math.floor(unitId / 100) * 100;
                            avatarUrl = `https://redive.estertion.win/icon/unit/${baseId + 31}.webp`;
                        }
                        
                        badgeHtmls.push(`
                            <div class="game-chara-avatar-badge" title="${realName}" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realName).replace(/"/g, '&quot;')})">
                                <img src="${avatarUrl}" onerror="if(this.src.includes('31.webp')) { this.src=this.src.replace('31.webp', '11.webp'); } else { this.src='https://redive.estertion.win/icon/unit/000000.webp'; }">
                            </div>
                        `);
                    });

                    badgesBar.innerHTML = badgeHtmls.join('');
                }
            }
            
            // 3. 渲染為仿遊戲內 UI 卡片
            let html = "";
            dialogueList.forEach(item => {
                const speaker = item.name || "旁白";
                const words = (item.words || "").replace(/\{player\}/g, "祐樹");
                
                let speakerClass = "";
                let isNarrator = speaker === "旁白" || speaker === "【系統】" || speaker === "？？？";
                let isChoice = speaker.includes("【選擇肢】") || speaker.includes("【選擇】");
                
                if (isNarrator) speakerClass = "role-narrator";
                else if (isChoice) speakerClass = "role-choice";
                
                const realNameForBtn = (isNarrator || isChoice) ? "" : QuestMapModule.getCharaRealName(speaker);
                
                let avatarHtml = "";
                if (!isNarrator && !isChoice) {
                    const realName = realNameForBtn;
                    const avatarContent = QuestMapModule.getAvatarHtml(realName);
                    
                    avatarHtml = `
                        <div class="game-chara-avatar-wrapper" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realName).replace(/"/g, '&quot;')})" style="cursor: pointer;">
                            <div class="game-chara-avatar">
                                ${avatarContent}
                            </div>
                        </div>
                    `;
                }
                
                const speakerBtnHtml = "";
                
                html += `
                    <div class="game-dialogue-line ${speakerClass}">
                        ${avatarHtml}
                        <div class="game-dialogue-content">
                            <div class="game-dialogue-speaker" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realNameForBtn).replace(/\"/g, '&quot;')})" style="cursor: pointer; display: inline-block;">${speaker}</div>
                            <div class="game-dialogue-text">${words}</div>
                        </div>
                    </div>
                `;
            });
            
            board.innerHTML = html;
            board.scrollTop = 0;
            
        } catch (err) {
            console.error("加載台詞失敗:", err);
            board.innerHTML = `
                <div class="dialogue-error-box" style="padding: 15px; border-radius: 8px; background: rgba(230, 73, 73, 0.05); border: 1px dashed rgba(230, 73, 73, 0.2); text-align: left;">
                    <div style="color: #d63031; font-weight: 700; font-size: 0.88rem; margin-bottom: 6px;">⚠️ 台詞文本尚未下載</div>
                    <div style="color: var(--text-primary); font-size: 0.82rem; line-height: 1.5;">
                        本話的對白文本尚未下載到您的電腦中。<br>
                        請在本地專案根目錄中，執行命令下載全部對白：
                    </div>
                    <code style="display: block; margin-top: 8px; background: rgba(0,0,0,0.05); padding: 8px; border-radius: 4px; color: var(--accent-color); font-family: Consolas, monospace; font-size: 0.8rem; border: 1px solid rgba(94, 107, 125, 0.15);">
                        python download_stories_tw.py
                    </code>
                </div>
            `;
        }
    },

    async showCharaModal(charaName) {
        const realCharaName = this.getCharaRealName(charaName);
        
        let profile = this.charaDetailCache[realCharaName];
        if (!profile) {
            try {
                const sql = `
                    SELECT guild, race, age, height, weight, birth_month, birth_day, blood_type, catch_copy, self_text, voice 
                    FROM unit_profile 
                    WHERE unit_name = ? OR unit_name LIKE ?
                    LIMIT 1
                `;
                const result = await window.PCRDatabase.runQuery(sql, [realCharaName, realCharaName + '（%']);
                if (result && result.length > 0) {
                    profile = result[0];
                    this.charaDetailCache[realCharaName] = profile;
                }
            } catch (e) {
                console.error("讀取角色 Profile 失敗:", e);
            }
        }

        // 【修正 Bug 3】appearanceMap 的 key 是原始發言者名（可能含括號限定語），同時嘗試標準化名與原始名
        const appearances = (this.appearanceMap &&
            (this.appearanceMap[realCharaName] || this.appearanceMap[charaName])) || [];
        
        let avatarUrl = "https://redive.estertion.win/icon/unit/000000.webp";
        const unitId = this.speakerAvatars[realCharaName];
        if (unitId) {
            const baseId = Math.floor(unitId / 100) * 100;
            avatarUrl = `https://redive.estertion.win/icon/unit/${baseId + 31}.webp`;
        }

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
            document.body.appendChild(modalEl);
        }

        let appListHtml = "";
        if (appearances.length === 0) {
            appListHtml = `<div style="color: var(--text-secondary); font-size: 0.85rem; font-style: italic;">暫無登場話數統計數據。</div>`;
        } else {
            appListHtml = appearances.map(storyId => {
                const story = this.stories.find(s => s.id === storyId) || this.eventStories.find(s => s.story_id === storyId);
                let label = `ID: ${storyId}`;
                if (story) {
                    const cleanCh = story.chapter.replace(/^(第\d+部\s*)?([^\s]+章\s*|[^\s]+序章\s*|[^\s]+幕間[^\s]*\s*)/, '');
                    label = `${cleanCh} ${story.title}`.trim();
                    if (label.length > 15) label = label.substring(0, 15) + "...";
                }
                return `<button class="chara-appear-btn" onclick="QuestMapModule.jumpToStory(${storyId}, 'game-chara-modal')" style="background: rgba(232,56,117,0.07); border: 1px solid rgba(232,56,117,0.2); border-radius: 8px; padding: 6px 12px; color: var(--accent-color); cursor: pointer; font-size: 0.82rem; font-weight: 600; transition: all 0.2s; display: inline-block;">${label}</button>`;
            }).join('');
        }

        const guild = profile ? (profile.guild || "未知") : "未知";
        const race = profile ? (profile.race || "未知") : "未知";
        const age = profile ? (profile.age || "未知") : "未知";
        const height = profile ? (profile.height || "未知") : "未知";
        const weight = profile ? (profile.weight || "未知") : "未知";
        const birth = (profile && profile.birth_month) ? `${profile.birth_month}月${profile.birth_day}日` : "未知";
        const cv = profile ? (profile.voice || "未知") : "未知";
        const selfText = profile ? (profile.self_text || "暫無自我介紹。").replace(/\\n/g, '<br>') : "暫無自我介紹。";
        const catchCopy = profile ? (profile.catch_copy || "") : "";

        let detailsHtml = "";
        if (profile) {
            detailsHtml = `
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
                            <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${age}歲</td>
                            <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">生日：</td>
                            <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${birth}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">身高：</td>
                            <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${height}cm</td>
                            <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">體重：</td>
                            <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${weight}kg</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">聲優：</td>
                            <td colspan="3" style="padding: 4px 0; color: var(--accent-color); font-weight: bold;">${cv}</td>
                        </tr>
                    </table>
                </div>
            `;
        } else {
            detailsHtml = `
                <div style="flex: 1; min-width: 200px; display: flex; flex-direction: column; justify-content: center;">
                    <div style="color: var(--text-secondary); font-size: 0.9rem; font-style: italic; border: 1px dashed rgba(232, 56, 117, 0.2); padding: 15px; border-radius: 8px; background: rgba(232, 56, 117, 0.03);">
                        ℹ️ 此角色為劇中登場人物或 NPC，尚無設定集數據。
                    </div>
                </div>
            `;
        }

        let bioHtml = "";
        if (profile) {
            bioHtml = `
                ${catchCopy ? `<div style="font-style: italic; color: var(--accent-color); font-size: 0.9rem; margin-bottom: 10px; text-align: left;">「${catchCopy}」</div>` : ''}
                <div style="background: rgba(94, 107, 125, 0.04); padding: 12px; border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.08); font-size: 0.85rem; line-height: 1.6; color: var(--text-primary); margin-bottom: 15px; text-align: left;">
                    ${selfText}
                </div>
            `;
        }

        modalEl.innerHTML = `
            <div class="game-modal-content" style="max-height: 85vh; overflow-y: auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(94, 107, 125, 0.1); padding-bottom: 12px; margin-bottom: 15px;">
                    <h3 style="margin: 0; color: var(--accent-color); font-size: 1.25rem;">🔍 角色檔案：${realCharaName}</h3>
                    <span class="game-modal-close-btn" onclick="document.getElementById('game-chara-modal').classList.remove('active')" style="cursor: pointer; font-size: 1.5rem; color: var(--text-secondary);">&times;</span>
                </div>
                
                <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 15px;">
                    <div style="width: 100px; height: 100px; border-radius: 12px; overflow: hidden; border: 2px solid rgba(232, 56, 117, 0.15); background: #ffffff; display: flex; align-items: center; justify-content: center;">
                        <img src="${avatarUrl}" style="width: 100%; height: 100%; object-fit: cover;" onerror="if(this.src.includes('31.webp')) { this.src=this.src.replace('31.webp', '11.webp'); } else { this.src='https://redive.estertion.win/icon/unit/000000.webp'; }">
                    </div>
                    ${detailsHtml}
                </div>
 
                ${bioHtml}
 
                <div style="border-top: 1px solid rgba(94, 107, 125, 0.1); padding-top: 15px;">
                    <h4 style="margin: 0 0 10px 0; color: var(--text-primary); font-size: 0.95rem;">📖 登場話數 (點擊直接跳轉放映)：</h4>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; max-height: 150px; overflow-y: auto; padding: 5px;">
                        ${appListHtml}
                    </div>
                </div>
            </div>
        `;
        
        modalEl.classList.add('active');
    },

    jumpToStory(storyId, closeModalId) {
        if (closeModalId) {
            const modal = document.getElementById(closeModalId);
            if (modal) modal.classList.remove('active');
        }
        
        // 判斷是主線還是活動
        const isEvent = this.eventStories.some(s => s.story_id === storyId);
        if (isEvent && this.activeTabType !== 'event') {
            this.activeTabType = 'event';
        } else if (!isEvent && this.activeTabType !== 'main') {
            this.activeTabType = 'main';
            
            // 確認部別
            const story = this.stories.find(s => s.id === storyId);
            if (story) {
                if (story.chapter.includes("第3部")) this.currentPart = 3;
                else if (story.chapter.includes("第2部")) this.currentPart = 2;
                else this.currentPart = 1;
            }
        }
        
        // 找到對應的章
        if (isEvent) {
            this.groupEventStories();
        } else {
            this.groupStories();
        }
        
        let targetChKey = null;
        for (const [chKey, stories] of Object.entries(this.chapters)) {
            if (stories.some(s => s.id === storyId)) {
                targetChKey = chKey;
                break;
            }
        }
        
        if (targetChKey) {
            this.expandedChapter = targetChKey;
        }
        
        // 【修正 Bug 7】傳入 skipAutoSelect=true，避免 render 先自動選第一話產生競態條件
        this.render(true).then(() => {
            this.selectStory(storyId);
            setTimeout(() => {
                const el = document.getElementById(`story-item-${storyId}`);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        });
    },

    renderSpeakerTab(tab) {
        const searchVal = this.speakerSearchQuery || "";
        const sortVal = this.speakerSortOrder || "appearances-desc";

        let speakers = Object.keys(this.appearanceMap || {});
        if (searchVal.trim()) {
            const query = searchVal.trim().toLowerCase();
            speakers = speakers.filter(name => name.toLowerCase().includes(query));
        }

        speakers.sort((a, b) => {
            const countA = (this.appearanceMap[a] || []).length;
            const countB = (this.appearanceMap[b] || []).length;
            if (sortVal === 'appearances-desc') {
                return countB - countA || a.localeCompare(b, 'zh-Hant-TW');
            } else if (sortVal === 'appearances-asc') {
                return countA - countB || a.localeCompare(b, 'zh-Hant-TW');
            } else {
                return a.localeCompare(b, 'zh-Hant-TW');
            }
        });

        tab.innerHTML = `
            <div class="map-container glass-card">
                <div class="map-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 15px; margin-bottom: 20px;">
                    <div>
                        <h2>👥 登場角色總覽</h2>
                        <p class="subtitle">統計所有登場人物的登場話數，點擊可直接查詢詳細資料與登場話數列表</p>
                    </div>
                    <div class="category-selector" style="display: flex; gap: 12px;">
                        <button class="part-btn ${this.activeTabType === 'main' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('main')" style="font-size: 0.95rem; padding: 10px 24px;">⚔️ 主線劇情</button>
                        <button class="part-btn ${this.activeTabType === 'event' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('event')" style="font-size: 0.95rem; padding: 10px 24px;">🏆 活動劇情</button>
                        <button class="part-btn ${this.activeTabType === 'speaker' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('speaker')" style="font-size: 0.95rem; padding: 10px 24px;">👥 登場角色</button>
                    </div>
                </div>

                <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap; margin-bottom: 20px;">
                    <div style="flex: 1; min-width: 250px;">
                        <input type="text" id="speaker-search-input" placeholder="🔍 搜尋登場角色名字..." value="${searchVal}" 
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
                    ${speakers.map(name => {
                        const count = (this.appearanceMap[name] || []).length;
                        const realName = this.getCharaRealName(name);
                        const unitId = this.speakerAvatars[realName];
                        let avatarUrl = "https://redive.estertion.win/icon/unit/000000.webp";
                        if (unitId) {
                            const baseId = Math.floor(unitId / 100) * 100;
                            avatarUrl = `https://redive.estertion.win/icon/unit/${baseId + 31}.webp`;
                        }
                        
                        return `
                            <div class="speaker-card glass-card" onclick="QuestMapModule.showCharaModal(${JSON.stringify(name).replace(/"/g, '&quot;')})" 
                                 onmouseover="this.style.transform='translateY(-3px)'; this.style.borderColor='rgba(255,255,255,0.2)'; this.style.background='rgba(255,255,255,0.08)';"
                                 onmouseout="this.style.transform='none'; this.style.borderColor='rgba(255,255,255,0.08)'; this.style.background='rgba(255,255,255,0.03)';"
                                 style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 15px 10px; text-align: center; cursor: pointer; transition: all 0.2s ease-in-out; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;">
                                <div style="width: 70px; height: 70px; border-radius: 50%; overflow: hidden; border: 2px solid rgba(255,255,255,0.1); background: #000; display: flex; align-items: center; justify-content: center;">
                                    <img src="${avatarUrl}" style="width: 100%; height: 100%; object-fit: cover;" onerror="if(this.src.includes('31.webp')) { this.src=this.src.replace('31.webp', '11.webp'); } else { this.src='https://redive.estertion.win/icon/unit/000000.webp'; }">
                                </div>
                                <div style="font-weight: bold; font-size: 0.9rem; color: #fff; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; width: 100%;" title="${name}">${name}</div>
                                <div style="font-size: 0.78rem; color: #ffa94d;">🎬 登場 ${count} 話</div>
                            </div>
                        `;
                    }).join('')}
                    ${speakers.length === 0 ? `<div style="grid-column: 1/-1; text-align: center; color: rgba(255,255,255,0.4); padding: 50px 0;">查無符合條件的登場角色</div>` : ''}
                </div>
            </div>
        `;
    },

    handleSpeakerSearch(value) {
        this.speakerSearchQuery = value;
        const grid = document.querySelector('.speaker-grid');
        if (grid) {
            // 用來即時重新 render 網格避免整頁重繪造成輸入框失去焦點
            const searchVal = value.trim().toLowerCase();
            const sortVal = this.speakerSortOrder || "appearances-desc";
            
            let speakers = Object.keys(this.appearanceMap || {});
            if (searchVal) {
                speakers = speakers.filter(name => name.toLowerCase().includes(searchVal));
            }
            
            speakers.sort((a, b) => {
                const countA = (this.appearanceMap[a] || []).length;
                const countB = (this.appearanceMap[b] || []).length;
                if (sortVal === 'appearances-desc') {
                    return countB - countA || a.localeCompare(b, 'zh-Hant-TW');
                } else if (sortVal === 'appearances-asc') {
                    return countA - countB || a.localeCompare(b, 'zh-Hant-TW');
                } else {
                    return a.localeCompare(b, 'zh-Hant-TW');
                }
            });
            
            grid.innerHTML = speakers.map(name => {
                const count = (this.appearanceMap[name] || []).length;
                const realName = this.getCharaRealName(name);
                const unitId = this.speakerAvatars[realName];
                let avatarUrl = "https://redive.estertion.win/icon/unit/000000.webp";
                if (unitId) {
                    const baseId = Math.floor(unitId / 100) * 100;
                    avatarUrl = `https://redive.estertion.win/icon/unit/${baseId + 31}.webp`;
                }
                
                return `
                    <div class="speaker-card glass-card" onclick="QuestMapModule.showCharaModal(${JSON.stringify(name).replace(/"/g, '&quot;')})" 
                         onmouseover="this.style.transform='translateY(-3px)'; this.style.borderColor='rgba(255,255,255,0.2)'; this.style.background='rgba(255,255,255,0.08)';"
                         onmouseout="this.style.transform='none'; this.style.borderColor='rgba(255,255,255,0.08)'; this.style.background='rgba(255,255,255,0.03)';"
                         style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 15px 10px; text-align: center; cursor: pointer; transition: all 0.2s ease-in-out; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;">
                        <div style="width: 70px; height: 70px; border-radius: 50%; overflow: hidden; border: 2px solid rgba(255,255,255,0.1); background: #000; display: flex; align-items: center; justify-content: center;">
                            <img src="${avatarUrl}" style="width: 100%; height: 100%; object-fit: cover;" onerror="if(this.src.includes('31.webp')) { this.src=this.src.replace('31.webp', '11.webp'); } else { this.src='https://redive.estertion.win/icon/unit/000000.webp'; }">
                        </div>
                        <div style="font-weight: bold; font-size: 0.9rem; color: #fff; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; width: 100%;" title="${name}">${name}</div>
                        <div style="font-size: 0.78rem; color: #ffa94d;">🎬 登場 ${count} 話</div>
                    </div>
                `;
            }).join('') + (speakers.length === 0 ? `<div style="grid-column: 1/-1; text-align: center; color: rgba(255,255,255,0.4); padding: 50px 0;">查無符合條件的登場角色</div>` : '');
        }
    },

    handleSpeakerSort(value) {
        this.speakerSortOrder = value;
        const grid = document.querySelector('.speaker-grid');
        if (grid) {
            this.handleSpeakerSearch(this.speakerSearchQuery || "");
        }
    }
};
