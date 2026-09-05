/**
 * PCRD Data Hub - 主線劇情放映與編年史模組 (QuestMapModule)
 * 負責從 SQLite 載入主線劇情列表，將其重構為階層式的「章 ➔ 話」摺疊選單，
 * 並提供 So-net 官方主線影片與官方文本大綱的精確對接。
 *
 * 相依：窗體 PCRDatabase, AvatarService, ChapterDataService
 */

const AvatarService = window.AvatarService;
const ChapterDataService = window.ChapterDataService;

const QuestMapModule = {
    stories: [],
    events: [],
    eventStories: [],
    eventSummaries: null,
    chapters: {},
    currentPart: 1,
    activeTabType: 'main',
    isDialogueExpanded: true,
    activeStoryId: null,
    expandedChapter: null,
    speakerAvatars: {},
    appearanceMap: null,
    charaDetailCache: {},
    activeSummaryTab: 'episode',
    speakerSearchQuery: "",
    speakerSortOrder: "appearances-desc",
    isRendering: false,
    isLoadingDialogue: false,
    currentView: 'menu',
    storyThumbnails: null,
    activeCharaName: null,
    charaSearchQuery: "",

    normalizeString(str) {
        if (!str) return "";
        let val = str.toLowerCase();
        // 繁簡/錯別字容錯轉換：菈/拉, 婭/亞, 莉/麗, 涅/霓, 雅/婭/亞
        const map = {
            '菈': '拉', '婭': '亞', '莉': '麗', '涅': '霓', '雅': '亞', '拉': '拉', '亞': '亞', '麗': '麗', '霓': '霓'
        };
        let res = "";
        for (let char of val) {
            res += map[char] || char;
        }
        return res;
    },

    handleCharaSearch(inputVal) {
        this.charaSearchQuery = inputVal;
        // 使用 debounce 防止每次按鍵都完整重建 DOM 或頻繁操作
        clearTimeout(this._charaSearchTimer);
        this._charaSearchTimer = setTimeout(() => {
            this._updateCharaGrid();
        }, 300);
    },

    /** 只更新角色 grid 內容，不重建整個頁面，從而保留搜尋框焦點與游標 */
    _updateCharaGrid() {
        const gridEl = document.querySelector('.chara-grid');
        if (!gridEl) {
            // fallback: 如果找不到 grid，完整重建
            this.safeRender(() => this._render());
            return;
        }

        const normalizedQuery = this.normalizeString(this.charaSearchQuery).trim();
        const chapterKeys = Object.keys(this.chapters).sort();

        let gridHtml = "";
        let count = 0;
        chapterKeys.forEach(chName => {
            const normalizedName = this.normalizeString(chName);
            if (normalizedQuery && !normalizedName.includes(normalizedQuery)) {
                return;
            }

            const stories = this.chapters[chName];
            const firstStory = stories[0];
            const groupId = firstStory ? firstStory.groupId : 1001;
            const cardId = `${groupId}31`;
            const remoteCardUrl = `https://redive.estertion.win/card/full/${cardId}.webp`;
            const localCardUrl = `card/${cardId}.webp`;
            
            gridHtml += `
                <div class="chara-card" style="background-image: url('${localCardUrl}'), url('${remoteCardUrl}')" onclick="QuestMapModule.selectChara('${this.escapeForAttr(chName)}')">
                    <div class="chara-card-overlay">
                        <div class="chara-card-name">${this.escapeHtml(chName)}</div>
                        <div class="chara-card-count">${stories.length} 話</div>
                    </div>
                </div>
            `;
            count++;
        });

        if (count === 0) {
            gridEl.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-secondary); font-size: 1.1rem;">查無此角色</div>`;
        } else {
            gridEl.innerHTML = gridHtml;
        }
    },

    escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    escapeForAttr(str) {
        if (!str) return "";
        return String(str)
            .replace(/\\/g, "\\\\")
            .replace(/'/g, "\\'")
            .replace(/"/g, "\\\"");
    },

    getStoryItemHtml(s, chDisplay, titleDisplay) {
        const thumbData = (this.storyThumbnails && this.storyThumbnails[s.id]) || {};
        const stillId = thumbData.still_id || s.still_id || null;
        const bgId = thumbData.bg_id || s.bg_id || null;
        const options = (s.type === 'chara' && s.groupId) ? { characterGroupId: s.groupId } : {};
        const thumbHtml = StoryAssetService.getStoryThumbnailHtml(
            s.id,
            stillId,
            bgId,
            'story-thumb-img',
            'width:100%;height:100%;object-fit:cover;',
            options
        );
 return `
 <div class="story-item ${this.activeStoryId === s.id ? 'active' : ''}" id="story-item-${s.id}" onclick="QuestMapModule.selectStory(${s.id})">
 <div class="story-item-thumb">
 ${thumbHtml}
 </div>
 <div class="story-item-content">
 <div class="story-item-ch">${this.escapeHtml(chDisplay)}</div>
 <div class="story-item-title">${this.escapeHtml(titleDisplay)}</div>
 </div>
 <div class="story-item-arrow">
 <svg viewBox="0 0 24 24">
 <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/>
 </svg>
 </div>
 </div>
 `;
 },

    getCharaRealName(name) {
        if (!name) return "";
        let singleName = name.split(/[、＆&]|和|與/)[0].trim();
        const aliases = {
            "貪吃佩可的聲音": "貪吃佩可", "大食客": "貪吃佩可", "飢餓的公主": "貪吃佩可",
            "可可蘿的聲音": "可可蘿", "導引者": "可可蘿", "引導者": "可可蘿", "導引少女": "可可蘿",
            "凱留的聲音": "凱留", "貓耳魔法少女": "凱留",
            "霸瞳天星的聲音": "霸瞳皇帝", "霸瞳天星": "霸瞳皇帝",
            "拉比林斯達的聲音": "拉比林斯達", "克莉絲提娜的聲音": "克莉絲提娜",
            "露娜的聲音": "露娜", "厄莉絲的聲音": "厄莉絲",
            "雪的聲音": "雪", "流夏的聲音": "流夏", "暮光流星的成員": "流夏",
            "雪菲的聲音": "雪菲", "似似花的聲音": "似似花", "亞里莎的聲音": "亞里莎",
            "帆稀的聲音": "帆稀", "嘉夜的聲音": "嘉夜", "祈梨的聲音": "祈梨",
            "矛依未的聲音": "矛依未", "涅雅": "涅婭",
            "安涅默涅": "安涅默涅", "普蕾西亞": "普蕾西亞",
            "莉莉的聲音": "莉莉", "可璃的聲音": "可璃亞",
            "可璃": "可璃亞", "可璃亞的聲音": "可璃亞",
            "八斗金局長": "八斗神", "八斗": "八斗神", "八斗神局長": "八斗神",
            "剎鬼‧八斗神": "八斗神", "傻": "倭",
            "菲絲雷斯": "菲絲", "吉塔的聲音": "吉塔", "深月的聲音": "深月",
            "克蕾琪塔的聲音": "克蕾琪塔", "蘭法的聲音": "蘭法", "美空的聲音": "美空",
            "涅比亞的聲音": "涅比亞", "古蕾婭的聲音": "古蕾婭", "安的聲音": "安",
            "莫妮卡的聲音": "莫妮卡",
            "ジュ": "純", "シュ": "雪", "アオ": "碧", "カオ": "香織", "ユカ": "由加莉",
            "コッ": "可可蘿", "コッコロ": "可可蘿", "ナレーション": "旁白", "ナレ": "旁白"
        };
        if (aliases[singleName]) return aliases[singleName];
        let clean = singleName.replace(/（[^）]+）/g, "").replace(/\([^)]+\)/g, "").trim();
        if (aliases[clean]) return aliases[clean];
        if (clean.endsWith("的聲音")) clean = clean.replace(/的聲音$/, "");
        return clean;
    },

    getAvatarHtml(realName) {
        return AvatarService.getAvatarHtml(realName, this.speakerAvatars);
    },

    // safeRender 包裝器：防止競態條件
    async safeRender(fn) {
        if (this.isRendering) return;
        this.isRendering = true;
        try {
            await fn();
        } finally {
            this.isRendering = false;
        }
    },

    async loadData() {
        try {
            // 優先確保 ChapterDataService 完整就緒（包含章節中繼資料與分支劇情補充元數據）
            if (window.ChapterDataService) {
                await window.ChapterDataService.load();
            }

            // 確保 AvatarService Manifest 完整就緒 (Exact Dialogue Avatar 治理)
            if (window.AvatarService && typeof window.AvatarService.ensureManifestLoaded === 'function') {
                await window.AvatarService.ensureManifestLoaded();
            }

            if (Object.keys(this.speakerAvatars).length === 0) {
                try {
                    const checkTableSql = `SELECT name FROM sqlite_master WHERE type='table' AND name='unit_data'`;
                    const tableCheck = await window.PCRDatabase.runQuery(checkTableSql);
                    if (!tableCheck || tableCheck.length === 0) {
                        console.warn("[QuestMapModule] unit_data 表不存在，跳過頭像預載入");
                    } else {
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
                            // 透過 AvatarService 註冊自定義 NPC 映射
                            Object.entries(AvatarService.customMap).forEach(([name, id]) => {
                                this.speakerAvatars[name] = id;
                            });
                            // 動態載入並合併 npc_avatars.json 映射
                            try {
                                const npcResp = await fetch('data/npc_avatars.json');
                                if (npcResp.ok) {
                                    const npcMap = await npcResp.json();
                                    Object.entries(npcMap).forEach(([name, id]) => {
                                        this.speakerAvatars[name] = id;
                                    });
                                    // Grace uses "飛白" as her name in the real-world scene.
                                    this.speakerAvatars["格蕾斯"] = 138901;
                                    this.speakerAvatars["飛白"] = 138901;
                                    console.log("[QuestMapModule] 成功載入並合併 npc_avatars.json");
                                }
                            } catch (npcErr) {
                                console.warn("[QuestMapModule] 載入 npc_avatars.json 失敗:", npcErr);
                            }
                            console.log(`[QuestMapModule] 預載入 ${Object.keys(this.speakerAvatars).length} 筆角色頭像映射 (含手動NPC補全)`);
                        }
                    }
                } catch (e) {
                    console.error("預載入角色頭像失敗:", e);
                }
            }

            if (!this.storyThumbnails) {
                try {
                    const resp = await fetch('data/story_thumbnails.json');
                    if (resp.ok) {
                        this.storyThumbnails = await resp.json();
                        console.log(`[QuestMapModule] 成功載入劇情縮圖快取 (${Object.keys(this.storyThumbnails).length} 筆)`);
                    }
                } catch (e) {
                    console.error("無法加載劇情縮圖快取:", e);
                }
            }

            if (!this.eventSummaries) {
                try {
                    const resp = await fetch('data/event_summaries.json');
                    if (resp.ok) {
                        this.eventSummaries = await resp.json();
                        console.log(`[QuestMapModule] 成功載入活動劇情摘要 (${Object.keys(this.eventSummaries).length} 筆)`);
                    } else {
                        this.eventSummaries = {};
                    }
                } catch (e) {
                    console.error("無法加載活動劇情摘要:", e);
                    this.eventSummaries = {};
                }
            }

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

            if (!this.movieLinks) {
                try {
                    const resp = await fetch('data/movie_links.json');
                    if (resp.ok) {
                        this.movieLinks = await resp.json();
                        console.log(`[QuestMapModule] 成功載入動畫連結映射表`);
                    }
                } catch (e) {
                    this.movieLinks = {};
                }
            }

            if (!this.extraEvents) {
                try {
                    const resp = await fetch('data/extra_events.json');
                    if (resp.ok) {
                        this.extraEvents = await resp.json();
                        // Event 10215 launched after the database snapshot. Keep its
                        // local navigation available until upstream detail rows arrive.
                        const villaEvent = this.extraEvents.events?.find(e => e.story_group_id === 10215);
                        if (villaEvent) {
                            villaEvent.title = 'VILLAINESS\n避開吧！鏡華的變疑分子毀滅結局';
                            villaEvent.start_time = '2026/08/01 16:00:00';
                        }
                        const villaStoryIds = [5215000, 5215001, 5215002, 5215003, 5215004, 5215005, 5215006, 5215007];
                        const villaLabels = ['序章', '第 1 話', '第 2 話', '第 3 話', '第 4 話', '第 5 話', '第 6 話', '終幕'];
                        const villaBackgrounds = ['502430', '501820', '500182', '502440', '510170', '510125', '500030', '500340'];
                        // Not every episode references its still in the dialogue
                        // commands. Use the prologue CG as the event fallback, with
                        // the dedicated stills for episodes 5 and 7 where available.
                        const villaStills = ['521500101', '521500101', '521500101', '521500101', '521500101', '521500501', '521500101', '521500701'];
                        villaStoryIds.forEach((id, index) => {
                            if (this.storyThumbnails) {
                                this.storyThumbnails[id] = {
                                    still_id: villaStills[index],
                                    bg_id: villaBackgrounds[index]
                                };
                            }
                        });
                        if (villaEvent && !this.extraEvents.stories?.some(s => s.groupId === 10215)) {
                            this.extraEvents.stories.push(...villaStoryIds.map((id, index) => ({
                                id,
                                chapter: villaLabels[index],
                                title: index === 0 ? 'VILLAINESS' : villaLabels[index],
                                groupId: 10215,
                                isEvent: true,
                                still_id: villaStills[index],
                                bg_id: villaBackgrounds[index]
                            })));
                        }
                        console.log(`[QuestMapModule] 成功載入新形式活動 (${this.extraEvents.events.length} 個活動)`);
                    }
                } catch (e) {
                    console.error("無法加載新形式活動:", e);
                }
            }

            if (this.stories.length === 0) {
                const checkChara = await window.PCRDatabase.runQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='chara_story_detail'");
                const isTW = !(checkChara && checkChara.length > 0);

                if (isTW) {
                    // 1. 台版主線劇情
                    const sql = `
                        SELECT story_id, title, sub_title, story_group_id
                        FROM story_detail
                        WHERE story_id >= 2000000 AND story_id < 3000000
                        ORDER BY story_id ASC
                    `;
                    const rawData = await window.PCRDatabase.runQuery(sql);
                    this.stories = rawData.map(row => {
                        const groupId = row.story_group_id;
                        return {
                            id: row.story_id,
                            chapter: row.title || "",
                            title: row.sub_title || "",
                            groupId: groupId,
                            part: ChapterDataService.getPartFromGroupId(groupId),
                            isEvent: false,
                            type: 'main',
                        };
                    });

                    // 2. 台版個人劇情
                    const charaSql = `
                        SELECT story_id, title, sub_title, story_group_id
                        FROM story_detail
                        WHERE story_id >= 1000000 AND story_id < 2000000
                        ORDER BY story_id ASC
                    `;
                    const rawChara = await window.PCRDatabase.runQuery(charaSql);
                    const charaStories = rawChara.map(row => ({
                        id: row.story_id,
                        chapter: row.title || "個人劇情",
                        title: row.sub_title || "",
                        groupId: row.story_group_id,
                        isEvent: false,
                        type: 'chara',
                    }));

                    // 【最新角色個人劇情目錄自動兜底】
                    // 由於台服資料庫 (redive_tw.db) 有時尚未上架新角色的個人故事章節 (如冬日栞)，
                    // 我們在此自動為已下載故事對話的新角色補全 4 話的個人故事目錄，確保網頁必定能順利讀取！
                    const pendingNewCharas = [
                        { unitId: 138301, name: "貪吃佩可（阿斯特萊亞）", prefix: "138300" },
                        { unitId: 138701, name: "若菜（冬日）", prefix: "138700" },
                        { unitId: 138801, name: "栞（冬日）", prefix: "138800" },
                        { unitId: 139101, name: "凱留（霸瞳天星）", prefix: "139100" },
                        { unitId: 139201, name: "美穗", prefix: "139200" },
                        { unitId: 139301, name: "真穗", prefix: "139300" },
                        { unitId: 139401, name: "艾麗卡", prefix: "139400" }
                    ];

                    pendingNewCharas.forEach(ch => {
                        const checkGroupId = Math.floor(ch.unitId / 100);
                        const exists = charaStories.some(s => s.groupId === checkGroupId);
                        if (!exists) {
                            for (let i = 1; i <= 4; i++) {
                                charaStories.push({
                                    id: parseInt(`${ch.prefix}${i}`),
                                    chapter: `${ch.name} 第${i}話`,
                                    title: `第 ${i} 話`,
                                    groupId: checkGroupId,
                                    isEvent: false,
                                    type: 'chara',
                                });
                            }
                        }
                    });

                    this.stories = this.stories.concat(charaStories);

                    // 3. 台版公會劇情
                    const guildSql = `
                        SELECT story_id, title, sub_title, story_group_id
                        FROM story_detail
                        WHERE story_id >= 3000000 AND story_id < 4000000
                        ORDER BY story_id ASC
                    `;
                    const rawGuild = await window.PCRDatabase.runQuery(guildSql);
                    const guildStories = rawGuild.map(row => ({
                        id: row.story_id,
                        chapter: row.title || "公會劇情",
                        title: row.sub_title || "",
                        groupId: row.story_group_id,
                        isEvent: false,
                        type: 'guild',
                    }));
                    this.stories = this.stories.concat(guildStories);

                    // 4. 台版露娜塔/系統劇情
                    const towerSql = `
                        SELECT story_id, title, sub_title, story_group_id
                        FROM story_detail
                        WHERE story_id >= 4000000 AND story_id < 5000000
                        ORDER BY story_id ASC
                    `;
                    const rawTower = await window.PCRDatabase.runQuery(towerSql);
                    const towerStories = rawTower.map(row => ({
                        id: row.story_id,
                        chapter: row.title || "露娜塔/系統劇情",
                        title: row.sub_title || "",
                        groupId: row.story_group_id,
                        isEvent: false,
                        type: 'tower',
                    }));
                    this.stories = this.stories.concat(towerStories);

                    // 5. 台版第 3 部分支劇情補充 (Supplemental Branch Stories)
                    if (window.ChapterDataService && Array.isArray(window.ChapterDataService.branchStories)) {
                        const existingIds = new Set(this.stories.map(s => s.id));
                        const newBranchStories = window.ChapterDataService.branchStories.filter(s => !existingIds.has(s.id));
                        this.stories = this.stories.concat(newBranchStories);
                        console.log(`[QuestMapModule] 成功補充載入 ${newBranchStories.length} 篇第 3 部分支劇情`);
                    }

                    console.log(`[QuestMapModule] 台版模式載入完畢：主線 ${rawData.length} 筆，個人 ${charaStories.length} 筆，公會 ${guildStories.length} 筆，其他 ${towerStories.length} 筆`);

                } else {
                    // 原日版模式
                    const sql = `
                        SELECT story_id, title, sub_title, story_group_id
                        FROM story_detail
                        WHERE story_id >= 2000000 AND story_id < 5000000
                        ORDER BY story_id ASC
                    `;
                    const rawData = await window.PCRDatabase.runQuery(sql);
                    this.stories = rawData.map(row => {
                        const groupId = row.story_group_id;
                        return {
                            id: row.story_id,
                            chapter: row.title || "",
                            title: row.sub_title || "",
                            groupId: groupId,
                            part: ChapterDataService.getPartFromGroupId(groupId),
                            isEvent: false,
                            type: 'main',
                        };
                    });
                    console.log(`[QuestMapModule] 日版模式載入：${this.stories.length} 筆主線`);

                    // 1. 個人劇情 (Chara Story)
                    try {
                        const charaSql = "SELECT story_id, title, sub_title, story_group_id FROM chara_story_detail";
                        const rawChara = await window.PCRDatabase.runQuery(charaSql);
                        const charaStories = rawChara.map(row => ({
                            id: row.story_id,
                            chapter: row.title || "個人劇情",
                            title: row.sub_title || "",
                            groupId: row.story_group_id,
                            isEvent: false,
                            type: 'chara',
                        }));
                        this.stories = this.stories.concat(charaStories);
                    } catch (e) { console.warn("日版個人劇情載入失敗:", e); }

                    // 2. 公會劇情 (Guild Story)
                    try {
                        const guildSql = "SELECT story_id, title, sub_title, story_group_id FROM guild_story_detail";
                        const rawGuild = await window.PCRDatabase.runQuery(guildSql);
                        const guildStories = rawGuild.map(row => ({
                            id: row.story_id,
                            chapter: row.title || "公會劇情",
                            title: row.sub_title || "",
                            groupId: row.story_group_id,
                            isEvent: false,
                            type: 'guild',
                        }));
                        this.stories = this.stories.concat(guildStories);
                    } catch (e) { console.warn("日版公會劇情載入失敗:", e); }

                    // 3. 露娜塔/系統劇情 (Tower/System Story)
                    try {
                        const towerSql = "SELECT story_id, title, sub_title, story_group_id FROM tower_story_detail";
                        const rawTower = await window.PCRDatabase.runQuery(towerSql);
                        const towerStories = rawTower.map(row => ({
                            id: row.story_id,
                            chapter: row.title || "露娜塔/系統劇情",
                            title: row.sub_title || "",
                            groupId: row.story_group_id,
                            isEvent: false,
                            type: 'tower',
                        }));
                        this.stories = this.stories.concat(towerStories);
                    } catch (e) { console.warn("日版露娜塔劇情載入失敗:", e); }
                }
            }

            if (this.events.length === 0) {
                const eventSql = `
                    SELECT story_group_id, title, start_time, thumbnail_id, value
                    FROM event_story_data
                    ORDER BY start_time DESC
                `;
                this.events = await window.PCRDatabase.runQuery(eventSql);
                
                // 合併新形式活動主檔
                if (this.extraEvents && this.extraEvents.events) {
                    const extraStartTimeMap = {
                        10201: "2025/06/01 16:00:00",
                        10202: "2025/07/01 16:00:00",
                        10203: "2025/08/01 16:00:00",
                        10204: "2025/09/01 16:00:00",
                        10205: "2025/10/01 16:00:00",
                        10206: "2025/11/01 16:00:00",
                        10207: "2025/12/01 16:00:00",
                        10208: "2026/01/01 16:00:00",
                        10209: "2026/02/01 16:00:00",
                        10210: "2026/03/01 16:00:00",
                        10211: "2026/04/01 16:00:00",
                        10212: "2026/05/01 16:00:00",
                        10213: "2026/06/01 16:00:00",
                        10214: "2026/07/01 16:00:00",
                        10215: "2026/08/01 16:00:00",
                        10216: "2026/09/01 16:00:00"
                    };

                    const extraEventsMapped = this.extraEvents.events.map(e => ({
                        story_group_id: e.story_group_id,
                        title: e.title,
                        start_time: extraStartTimeMap[e.story_group_id] || e.start_time || "2025/01/01 16:00:00",
                        thumbnail_id: e.thumbnail_id,
                        value: e.value
                    }));
                    // 將新形式活動合併，並按時間倒序排序
                    this.events = extraEventsMapped.concat(this.events);
                    this.events.sort((a, b) => {
                        const timeA = new Date(a.start_time.replace(/-/g, '/')).getTime();
                        const timeB = new Date(b.start_time.replace(/-/g, '/')).getTime();
                        return timeB - timeA;
                    });
                }
                console.log(`[QuestMapModule] 成功載入 ${this.events.length} 筆活動主檔 (含新形式活動並排序)`);
            }

            if (this.eventStories.length === 0) {
                const eventDetailSql = `
                    SELECT story_id, title, sub_title, story_group_id
                    FROM event_story_detail
                    ORDER BY story_id ASC
                `;
                const rawEventStories = await window.PCRDatabase.runQuery(eventDetailSql);
                this.eventStories = rawEventStories.map(row => ({
                    id: row.story_id,
                    chapter: row.title || "",
                    title: row.sub_title || "",
                    groupId: row.story_group_id,
                    isEvent: true,
                }));
                
                // 合併新形式活動故事
                if (this.extraEvents && this.extraEvents.stories) {
                    const extraStoriesMapped = this.extraEvents.stories.map(s => ({
                        id: s.id,
                        chapter: s.chapter || "",
                        title: s.title || "",
                        groupId: s.groupId,
                        isEvent: true,
                        still_id: s.still_id,
                        bg_id: s.bg_id
                    }));
                    this.eventStories = this.eventStories.concat(extraStoriesMapped);
                }
                console.log(`[QuestMapModule] 成功載入 ${this.eventStories.length} 筆活動話數 (含新形式活動)`);
            }
        } catch (err) {
            console.error("[QuestMapModule] 載入劇情數據失敗:", err);
        }
    },

    groupStories() {
        this.chapters = {};
        const filtered = this.stories.filter(s => s.type === 'main' && s.part === this.currentPart);

        filtered.forEach(s => {
            // Part 3 主線分頁：隱藏幕間劇情 (group_id >= 3000)
            if (this.currentPart === 3 && this.activeTabType === 'main' && s.groupId >= 3000) {
                return;
            }
            const chKey = ChapterDataService.getChapterKey(this.currentPart, s.groupId, s.chapter);
            if (!this.chapters[chKey]) this.chapters[chKey] = [];
            this.chapters[chKey].push(s);
        });

        // 依章節順序排序
        const orderMap = {};
        const chapterList = ChapterDataService.getAllChapters(this.currentPart);
        chapterList.forEach((c, i) => { orderMap[c.key] = c.order; });

        const sorted = {};
        Object.keys(this.chapters)
            .sort((a, b) => (orderMap[a] ?? 999) - (orderMap[b] ?? 999))
            .forEach(k => { sorted[k] = this.chapters[k]; });
        this.chapters = sorted;
    },

    groupEventStories() {
        this.chapters = {};
        const sortedEvents = [...this.events].sort((a, b) => {
            const da = new Date(a.start_time);
            const db = new Date(b.start_time);
            return db - da || 0;
        });

        sortedEvents.forEach(evt => {
            const date = new Date(evt.start_time);
            const timeLabel = isNaN(date.getFullYear()) ? "【未知時間】" : `【${date.getFullYear()}年${date.getMonth() + 1}月】`;
            const chName = `${timeLabel} ${evt.title}`;

            const childStories = this.eventStories.filter(s => s.groupId === evt.story_group_id);
            if (childStories.length > 0) {
                this.chapters[chName] = childStories.map(s => ({
                    id: s.id,
                    chapter: s.chapter || "",
                    title: s.title || "",
                    groupId: s.groupId,
                    isEvent: true,
                    eventValue: evt.value,
                    still_id: s.still_id,
                    bg_id: s.bg_id,
                }));
            }
        });
    },

    groupGuildStories() {
        this.chapters = {};
        const filtered = this.stories.filter(s => s.type === 'guild');
        // 依 groupId (公會編號) 排序，讓公會順序固定
        filtered.sort((a, b) => (a.groupId || 0) - (b.groupId || 0));
        filtered.forEach(s => {
            let guildName = "其他公會";
            if (s.chapter) {
                const match = s.chapter.match(/^(.*?)\s*第\d+話/);
                if (match) {
                    guildName = match[1].trim();
                } else {
                    const parts = s.chapter.split(/\s+第/);
                    if (parts[0]) {
                        guildName = parts[0].trim();
                    } else {
                        guildName = s.chapter;
                    }
                }
            }
            if (!this.chapters[guildName]) this.chapters[guildName] = [];
            this.chapters[guildName].push(s);
        });
    },

    groupCharaStories() {
        this.chapters = {};
        const filtered = this.stories.filter(s => s.type === 'chara');
        // 依 groupId (角色 unit_id) 排序，並讓話數遞增
        filtered.sort((a, b) => {
            if (a.groupId !== b.groupId) {
                return (a.groupId || 0) - (b.groupId || 0);
            }
            return a.id - b.id;
        });
        filtered.forEach(s => {
            // 從 s.chapter 提取角色名。例如 "日和 第1話" -> 提取 "日和"
            let charaName = "其他角色";
            if (s.chapter) {
                const match = s.chapter.match(/^(.*?)\s*第\d+話/);
                if (match) {
                    charaName = match[1].trim();
                } else {
                    const parts = s.chapter.split(/\s+第/);
                    if (parts[0]) {
                        charaName = parts[0].trim();
                    }
                }
            }
            s.charaName = charaName;

            // 從 s.chapter 提取話數（如 "第1話"）
            let episodeLabel = "";
            if (s.chapter) {
                const match = s.chapter.match(/第\d+話/);
                if (match) {
                    episodeLabel = match[0];
                }
            }
            s.episodeLabel = episodeLabel;

            const chKey = charaName;
            if (!this.chapters[chKey]) this.chapters[chKey] = [];
            this.chapters[chKey].push(s);
        });
    },

    groupTowerStories() {
        this.chapters = {};
        const filtered = this.stories.filter(s => s.type === 'tower');
        filtered.sort((a, b) => a.id - b.id);
        filtered.forEach(s => {
            const chKey = s.chapter || "露娜塔/系統劇情";
            if (!this.chapters[chKey]) this.chapters[chKey] = [];
            this.chapters[chKey].push(s);
        });
    },

    switchTabType(type) {
        this.activeTabType = type;
        this.activeStoryId = null;
        this.expandedChapter = null;
        this.safeRender(() => this._render());
    },

 goBackToMenu() {
 this.currentView = 'menu';
 this._fadeTransition(() => this._render());
 },

    handleFloatingBack() {
        this.handleBackClick();
    },

    enterCategory(type) {
        this.currentView = 'list';
        this.activeTabType = type;
        this.activeStoryId = null;
        this.expandedChapter = null;
        if (type === 'chara') {
            this.activeCharaName = null;
        }
        this._fadeTransition(() => this._render());
    },

    /** 視圖切換時的 fade-out → fade-in 過渡動畫 */
    _fadeTransition(renderFn) {
        const tab = document.getElementById('map-tab');
        if (!tab) { this.safeRender(renderFn); return; }
        tab.style.transition = 'opacity 0.2s ease-out';
        tab.style.opacity = '0';
        setTimeout(() => {
            this.safeRender(async () => {
                await renderFn.call(this);
                requestAnimationFrame(() => {
                    tab.style.transition = 'opacity 0.3s ease-in';
                    tab.style.opacity = '1';
                });
            });
        }, 200);
    },

    changeMenuBg(type) {
        const bgArea = document.getElementById('menu-visual-area');
        if (!bgArea) return;
        const bgs = {
            'main': 'https://redive.estertion.win/card/full/105931.webp',
            'chara': 'https://redive.estertion.win/card/full/100131.webp',
            'guild': 'https://redive.estertion.win/card/full/105331.webp',
            'extra': 'https://redive.estertion.win/card/full/105631.webp'
        };
        const url = bgs[type] || bgs['main'];
        bgArea.style.backgroundImage = `url('${url}')`;
    },

    async _render(skipAutoSelect = false) {
        await this.loadData();

        const tab = document.getElementById('map-tab');

        if (this.currentView === 'menu') {
            tab.innerHTML = `
            <div class="menu-container">
                <div class="menu-cards-area">
                    <!-- 主要劇情 (左右佈局，橫跨3列) -->
                    <div class="menu-card card-main" onmouseenter="QuestMapModule.changeMenuBg('main')" onclick="QuestMapModule.enterCategory('main')" 
                         style="background-image: url('https://redive.estertion.win/card/full/105861.webp'); background-position: center 25%;">
                        <div class="menu-card-bg-mask"></div>
                        <div class="menu-card-inner">
                            <div class="menu-card-title">主要</div>
                            <div class="menu-card-desc">可以在此處閱覽阿斯特萊亞大陸上發生的故事</div>
                        </div>
                    </div>
                    <!-- 角色劇情 (上下佈局) -->
                    <div class="menu-card card-sub" onmouseenter="QuestMapModule.changeMenuBg('chara')" onclick="QuestMapModule.enterCategory('chara')" 
                         style="background-image: url('https://redive.estertion.win/card/full/100261.webp');">
                        <div class="menu-card-bg-mask"></div>
                        <div class="menu-card-inner">
                            <div class="menu-card-title">角色</div>
                            <div class="menu-card-desc">提升羈絆Rank後會追加新的故事</div>
                        </div>
                    </div>
                    <!-- 公會劇情 (上下佈局) -->
                    <div class="menu-card card-sub" onmouseenter="QuestMapModule.changeMenuBg('guild')" onclick="QuestMapModule.enterCategory('guild')" 
                         style="background-image: url('https://redive.estertion.win/card/full/101761.webp');">
                        <div class="menu-card-bg-mask"></div>
                        <div class="menu-card-inner">
                            <div class="menu-card-title">公會</div>
                            <div class="menu-card-desc">在這裡可以看到女孩們的日常故事</div>
                        </div>
                    </div>
                    <!-- 額外劇情 (上下佈局) -->
                    <div class="menu-card card-sub" onmouseenter="QuestMapModule.changeMenuBg('extra')" onclick="QuestMapModule.enterCategory('tower')" 
                         style="background-image: url('https://redive.estertion.win/card/full/104461.webp');">
                        <div class="menu-card-bg-mask"></div>
                        <div class="menu-card-inner">
                            <div class="menu-card-title">額外</div>
                            <div class="menu-card-desc">可以回顧那些有點特別的故事</div>
                        </div>
                    </div>
                </div>
            </div>
`;
 const existingBackBtn = document.querySelector('.floating-back-btn');
 if (existingBackBtn) existingBackBtn.remove();
 return;
 }

        if (this.activeTabType === 'speaker') {
            this.renderSpeakerTab(tab);
            return;
        }

        if (this.activeTabType === 'event') {
            this.groupEventStories();
        } else if (this.activeTabType === 'guild') {
            this.groupGuildStories();
        } else if (this.activeTabType === 'chara') {
            this.groupCharaStories();
        } else if (this.activeTabType === 'tower') {
            this.groupTowerStories();
        } else {
            this.groupStories();
        }

        const chapterKeys = Object.keys(this.chapters);
        if (this.activeTabType === 'chara' && this.activeCharaName) {
            this.expandedChapter = this.activeCharaName;
        } else if ((!this.expandedChapter || !this.chapters[this.expandedChapter]) && chapterKeys.length > 0) {
            this.expandedChapter = chapterKeys[0];
        }

        // 1. 如果是角色 Tab 且尚未選定角色，渲染角色卡片網格 (Grid)
        if (this.activeTabType === 'chara' && !this.activeCharaName) {
            let gridHtml = "";
            const normalizedQuery = this.normalizeString(this.charaSearchQuery).trim();
            let count = 0;

            chapterKeys.sort().forEach(chName => {
                const normalizedName = this.normalizeString(chName);
                if (normalizedQuery && !normalizedName.includes(normalizedQuery)) {
                    return;
                }

                const stories = this.chapters[chName];
                const firstStory = stories[0];
                const groupId = firstStory ? firstStory.groupId : 1001;
                // 3★卡面 ID
                const cardId = `${groupId}31`;
                const remoteCardUrl = `https://redive.estertion.win/card/full/${cardId}.webp`;
                const localCardUrl = `card/${cardId}.webp`;
                
                gridHtml += `
                    <div class="chara-card" style="background-image: url('${localCardUrl}'), url('${remoteCardUrl}')" onclick="QuestMapModule.selectChara('${this.escapeForAttr(chName)}')">
                        <div class="chara-card-overlay">
                            <div class="chara-card-name">${this.escapeHtml(chName)}</div>
                            <div class="chara-card-count">${stories.length} 話</div>
                        </div>
                    </div>
                `;
                count++;
            });

            if (count === 0) {
                gridHtml = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-secondary); font-size: 1.1rem;">查無此角色</div>`;
            }

            tab.innerHTML = `
                <div class="floating-back-btn" onclick="QuestMapModule.handleFloatingBack()" style="position: fixed; top: 20px; left: 20px; z-index: 9998; width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #2d6bcf, #1a4a9e); color: #fff; border: 2px solid rgba(255,255,255,0.3); cursor: pointer; box-shadow: 0 4px 15px rgba(26, 74, 158, 0.5); display: flex; align-items: center; justify-content: center; font-size: 1.2rem; font-weight: bold; transition: transform 0.2s ease, box-shadow 0.2s ease;" onmouseover="this.style.transform='scale(1.15)'; this.style.boxShadow='0 6px 20px rgba(26, 74, 158, 0.7)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 15px rgba(26, 74, 158, 0.5)';">←</div>
                <div class="map-container">
                    <div class="breadcrumb-container" style="margin-bottom: 15px; display: flex; align-items: center; gap: 12px; font-size: 0.95rem;">
                        <button onclick="QuestMapModule.handleBackClick()" class="back-to-menu-btn" style="
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            width: 32px;
                            height: 32px;
                            border-radius: 50%;
                            background: linear-gradient(135deg, #0984e3, #00cec9);
                            color: #fff;
                            border: none;
                            cursor: pointer;
                            box-shadow: 0 2px 6px rgba(9, 132, 227, 0.4);
                            transition: transform 0.2s ease, box-shadow 0.2s ease;
                            font-size: 1rem;
                            font-weight: bold;
                            flex-shrink: 0;
                        " onmouseover="this.style.transform='scale(1.1)'; this.style.boxShadow='0 4px 12px rgba(9, 132, 227, 0.6)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 2px 6px rgba(9, 132, 227, 0.4)';">
                            ←
                        </button>
                        <span class="breadcrumb-item linkable" onclick="QuestMapModule.goBackToMenu()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;"><span style="font-size: 1.1rem;">🏠</span> 劇情大廳</span>
                        <span class="breadcrumb-separator" style="color: rgba(255,255,255,0.3);">/</span>
                        <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">👤 角色</span>
                    </div>
                    <div class="map-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                        <div>
                            <h2>📖 角色劇情目錄</h2>
                            <p class="subtitle">選擇角色以瀏覽其個人絆劇情目錄與解鎖插畫</p>
                        </div>
                        <div>
                            <input type="text" id="chara-search-input" placeholder="搜尋角色名稱 (支援繁簡/容錯)..." class="region-select" style="width: 280px; background-image: none; padding-right: 12px;" value="${this.escapeHtml(this.charaSearchQuery)}" oninput="QuestMapModule.handleCharaSearch(this.value)">
                        </div>
                    </div>
                    <div class="chara-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 15px; margin-top: 20px;">
                        ${gridHtml}
                    </div>
                </div>
            `;
            const existingBackBtn = document.querySelector('.floating-back-btn');
            if (existingBackBtn) existingBackBtn.remove();
            return;
        }

        // 2. 預先建構右側控制面板的 HTML 內容，完全避免巢狀 template literal 解析錯誤
        let controlPanelHtml = "";
        if (this.activeTabType === 'chara' && this.activeCharaName) {
            controlPanelHtml = `
                <div class="chara-breadcrumb" style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px; background: rgba(0,0,0,0.05); padding: 8px; border-radius: 4px;">
                    <div class="chara-back-btn" onclick="QuestMapModule.clearActiveChara()" style="cursor: pointer; color: var(--accent-color); font-weight: bold; font-size: 0.85rem;">
                        ⬅ 返回角色列表
                    </div>
                    <span style="color: rgba(0,0,0,0.25); font-size: 0.8rem;">/</span>
                    <span style="font-size: 0.85rem; font-weight: bold; color: var(--text-primary);">${this.escapeHtml(this.activeCharaName)}</span>
                </div>
                <div class="accordion-content" style="max-height: none; display: block; padding-top: 8px;">
                    ${(this.chapters[this.activeCharaName] || []).map(s => {
                        const displayTitle = s.episodeLabel ? `${s.episodeLabel} ${s.title}` : s.title;
                        return this.getStoryItemHtml(s, "個人故事", displayTitle);
                    }).join('')}
                </div>
            `;
        } else {
            let accordionHtml = "";
            chapterKeys.forEach((chKey, chIndex) => {
                const isExpanded = this.expandedChapter === chKey;
                const childStories = this.chapters[chKey] || [];
                const safeId = `acc-item-${chIndex}`;

                let chTitle = "";
                let chIcon = isExpanded ? '📂' : '📁';

                if (this.activeTabType === 'main') {
                    let cleanChKey = chKey;
                    const firstStory = childStories[0];
                    const groupId = firstStory ? firstStory.groupId : null;
                    const info = firstStory ? ChapterDataService.getChapterInfo(this.currentPart, groupId) : null;
                    chTitle = info?.title ? ` - ${info.title}` : "";

                    // 取得章節縮圖 (優先使用章節內首個故事的官方專屬縮圖，無則逐步降級至 still_id / bg_id / 預設卡面)
                    let foundStoryId = (childStories && childStories.length > 0) ? childStories[0].id : null;
                    let foundStillId = null;
                    let foundBgId = null;

                    if (groupId && this.storyThumbnails && this.storyThumbnails[groupId]) {
                        const thumb = this.storyThumbnails[groupId];
                        foundStillId = thumb.still_id;
                        foundBgId = thumb.bg_id;
                    }

                    if (!foundStillId && !foundBgId && this.storyThumbnails && childStories) {
                        for (const s of childStories) {
                            const thumb = this.storyThumbnails[s.id];
                            if (thumb) {
                                if (thumb.still_id) {
                                    foundStillId = thumb.still_id;
                                    break; // 優先使用劇照，找到立即停止
                                }
                                if (!foundBgId && thumb.bg_id) {
                                    foundBgId = thumb.bg_id;
                                }
                            }
                        }
                    }

                    const chapterCardThumbHtml = StoryAssetService.getStoryThumbnailHtml(
                        foundStoryId,
                        foundStillId,
                        foundBgId,
                        'chapter-card-img',
                        ''
                    );

                    accordionHtml += `
                        <div class="accordion-item ${isExpanded ? 'active' : ''}" id="${safeId}">
                            <div class="accordion-header chapter-card" onclick="QuestMapModule.toggleChapter(${chIndex})">
                                <div class="acc-header-title">
                                    <div class="chapter-card-thumb">
                                        ${chapterCardThumbHtml}
                                    </div>
                                    <span class="acc-ch-name" style="margin-left: 8px;">${this.escapeHtml(cleanChKey)}${this.escapeHtml(chTitle)}</span>
                                </div>
                                <div class="acc-count">${childStories.length} 話</div>
                            </div>
                            <div class="accordion-content" style="max-height: ${isExpanded ? 'none' : '0px'}">
                                ${childStories.map(s => {
                                    const chDisplay = s.chapter.replace(/^(第\d+部\s*)?([^\s]+章\s*|[^\s]+序章\s*|[^\s]+幕間[^\s]*\s*)/, '');
                                    const titleDisplay = s.title;
                                    return this.getStoryItemHtml(s, chDisplay, titleDisplay);
                                }).join('')}
                            </div>
                        </div>
                    `;
                } else if (this.activeTabType === 'event') {
                    chIcon = "🏆";
                    let foundStoryId = (childStories && childStories.length > 0) ? childStories[0].id : null;
                    let foundStillId = null;
                    let foundBgId = null;
                    if (childStories) {
                        for (const s of childStories) {
                            if (s.still_id) { foundStillId = s.still_id; break; }
                            if (!foundBgId && s.bg_id) foundBgId = s.bg_id;
                        }
                    }
                    const chapterCardThumbHtml = StoryAssetService.getStoryThumbnailHtml(
                        foundStoryId,
                        foundStillId,
                        foundBgId,
                        'chapter-card-img',
                        ''
                    );

                    accordionHtml += `
                        <div class="accordion-item ${isExpanded ? 'active' : ''}" id="${safeId}">
                            <div class="accordion-header chapter-card" onclick="QuestMapModule.toggleChapter(${chIndex})">
                                <div class="acc-header-title">
                                    <div class="chapter-card-thumb">
                                        ${chapterCardThumbHtml}
                                    </div>
                                    <span class="acc-ch-name" style="margin-left: 8px;">${this.escapeHtml(chKey)}</span>
                                </div>
                                <div class="acc-count">${childStories.length} 話</div>
                            </div>
                            <div class="accordion-content" style="max-height: ${isExpanded ? 'none' : '0px'}">
                                ${childStories.map(s => {
                                    const cleanEventTitle = chKey.substring(chKey.indexOf('」') + 1).trim();
                                    let displayChapterName = s.chapter.replace(cleanEventTitle, '').trim();
                                    if (!displayChapterName) displayChapterName = s.chapter;
                                    return this.getStoryItemHtml(s, displayChapterName, s.title);
                                }).join('')}
                            </div>
                        </div>
                    `;
                } else {
                    chIcon = this.activeTabType === 'guild' ? "👥" : "🌙";
                    accordionHtml += `
                        <div class="accordion-item ${isExpanded ? 'active' : ''}" id="${safeId}">
                            <div class="accordion-header" onclick="QuestMapModule.toggleChapter(${chIndex})">
                                <div class="acc-header-title">
                                    <span class="acc-folder-icon" style="display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">${chIcon}</span>
                                    <span class="acc-ch-name" style="margin-left: 8px;">${this.escapeHtml(chKey)}</span>
                                </div>
                                <div class="acc-count">${childStories.length} 話</div>
                            </div>
                            <div class="accordion-content" style="max-height: ${isExpanded ? 'none' : '0px'}">
                                ${childStories.map(s => {
                                    let displayChapterName = "特別故事";
                                    if (this.activeTabType === 'guild' && s.chapter) {
                                        const match = s.chapter.match(/第\d+話/);
                                        if (match) displayChapterName = match[0];
                                    }
                                    return this.getStoryItemHtml(s, displayChapterName, s.title);
                                }).join('')}
                            </div>
                        </div>
                    `;
                }
            });
            controlPanelHtml = `
                <div class="accordion-container">
                    ${accordionHtml}
                </div>
            `;
        }

        const isCharaActive = (this.activeTabType === 'chara' && this.activeCharaName);
        tab.innerHTML = `
 <div class="floating-back-btn" onclick="${isCharaActive ? 'QuestMapModule.clearActiveChara()' : 'QuestMapModule.handleFloatingBack()'}" style="position: fixed; top: 20px; left: 20px; z-index: 9998; width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #2d6bcf, #1a4a9e); color: #fff; border: 2px solid rgba(255,255,255,0.3); cursor: pointer; box-shadow: 0 4px 15px rgba(26, 74, 158, 0.5); display: flex; align-items: center; justify-content: center; font-size: 1.2rem; font-weight: bold; transition: transform 0.2s ease, box-shadow 0.2s ease;" onmouseover="this.style.transform='scale(1.15)'; this.style.boxShadow='0 6px 20px rgba(26, 74, 158, 0.7)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 15px rgba(26, 74, 158, 0.5)';">←</div>
 <div class="map-container">
 <div class="breadcrumb-container" style="margin-bottom: 15px; display: flex; align-items: center; gap: 12px; font-size: 0.95rem;">
 <button onclick="QuestMapModule.handleBackClick()" class="back-to-menu-btn" style="
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #0984e3, #00cec9);
                    color: #fff;
                    border: none;
                    cursor: pointer;
                    box-shadow: 0 2px 6px rgba(9, 132, 227, 0.4);
                    transition: transform 0.2s ease, box-shadow 0.2s ease;
                    font-size: 1rem;
                    font-weight: bold;
                    flex-shrink: 0;
                " onmouseover="this.style.transform='scale(1.1)'; this.style.boxShadow='0 4px 12px rgba(9, 132, 227, 0.6)';" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 2px 6px rgba(9, 132, 227, 0.4)';">
                    ←
                </button>
                <span class="breadcrumb-item linkable" onclick="QuestMapModule.goBackToMenu()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;"><span style="font-size: 1.1rem;">🏠</span> 劇情大廳</span>
                <span class="breadcrumb-separator" style="color: rgba(255,255,255,0.3);">/</span>
                ${isCharaActive ? `
                    <span class="breadcrumb-item linkable" onclick="QuestMapModule.clearActiveChara()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;">👤 角色</span>
                    <span class="breadcrumb-separator" style="color: rgba(255,255,255,0.3);">/</span>
                    <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">👤 ${this.escapeHtml(this.activeCharaName)}</span>
                ` : `
                    <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">${
                        this.activeTabType === 'main' ? '⚔️ 主要' :
                        this.activeTabType === 'event' ? '🏆 活動' :
                        this.activeTabType === 'guild' ? '👥 公會' :
                        this.activeTabType === 'chara' ? '👤 角色' :
                        this.activeTabType === 'tower' ? '🌙 額外' : '👥 登場角色'
                    }</span>
                `}
            </div>
            <div class="map-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <div>
                    <h2>📖 ${
                        this.activeTabType === 'main' ? '主要' :
                        this.activeTabType === 'event' ? '活動' :
                        this.activeTabType === 'guild' ? '公會' :
                        this.activeTabType === 'chara' ? '角色' :
                        this.activeTabType === 'tower' ? '額外' : '登場角色'
                    }</h2>
                    <p class="subtitle">載入 So-net 官方繁中劇情大綱與對話文本</p>
                </div>
                ${(this.activeTabType === 'main' || this.activeTabType === 'event') ? `
                <div class="category-selector" style="display: flex; gap: 12px; flex-wrap: wrap;">
                    <button class="part-btn ${this.activeTabType === 'main' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('main')" style="font-size: 0.95rem; padding: 10px 24px;">⚔️ 主線劇情</button>
                    <button class="part-btn ${this.activeTabType === 'event' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('event')" style="font-size: 0.95rem; padding: 10px 24px;">🏆 活動劇情</button>
                </div>
                ` : ''}
            </div>

            <div class="part-selector" style="display: ${this.activeTabType === 'main' ? 'flex' : 'none'}; margin-top: 15px;">
                <button class="part-btn ${this.currentPart === 1 ? 'active' : ''}" onclick="QuestMapModule.switchPart(1)">第一部</button>
                <button class="part-btn ${this.currentPart === 2 ? 'active' : ''}" onclick="QuestMapModule.switchPart(2)">第二部</button>
                <button class="part-btn ${this.currentPart === 3 ? 'active' : ''}" onclick="QuestMapModule.switchPart(3)">第三部</button>
            </div>

            <div class="map-layout" style="margin-top: 20px;">
                <div class="map-visual-area">
                    <div class="cinema-panel">
                        <div class="cinema-meta" style="display: flex; flex-direction: column;">
                            <div class="cinema-ch-row" style="display: flex; align-items: center; justify-content: space-between;">
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span id="cinema-ch-tag" class="ch-tag">第 1 章</span>
                                    <h3 id="cinema-title" style="margin: 0; color: var(--text-primary);">話標題</h3>
                                </div>
                                <button class="mobile-only-dir-btn" onclick="QuestMapModule.scrollToControlPanel()" style="padding: 6px 12px; background: rgba(232, 56, 117, 0.08); border: 1px solid rgba(232, 56, 117, 0.2); border-radius: 20px; color: var(--accent-color); font-weight: bold; cursor: pointer; font-size: 0.82rem; transition: all 0.2s;">📂 快速目錄</button>
                            </div>
                            <div class="summary-section" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; margin-top: 15px;">
                                <div class="summary-tabs" style="display: flex; border-bottom: 2px solid rgba(94, 107, 125, 0.15); margin-bottom: 10px; gap: 8px;">
                                    <button id="tab-summary-episode" class="summary-tab active" onclick="QuestMapModule.switchSummaryTab('episode')" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid var(--accent-color); color: var(--accent-color); cursor: pointer; font-weight: bold; font-size: 0.88rem;">📜 單話大綱</button>
                                    <button id="tab-summary-ai-summary" class="summary-tab" onclick="QuestMapModule.switchSummaryTab('ai-summary')" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--text-secondary); cursor: pointer; font-size: 0.88rem;">💡 單話摘要簡介</button>
                                    <button id="tab-summary-chapter" class="summary-tab" onclick="QuestMapModule.switchSummaryTab('chapter')" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--text-secondary); cursor: pointer; font-size: 0.88rem;">📖 整章摘要簡介</button>
                                </div>
                                <div id="cinema-summary" class="summary-text" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column;">
                                    點擊右側章節清單，即刻載入大綱與對白文本。
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="map-control-panel">
                    <div class="panel-section-title">
                        📖 ${
                            this.activeTabType === 'main' ? '主線劇情編年史目錄' : 
                            this.activeTabType === 'event' ? '歷年活動劇情目錄' :
                            this.activeTabType === 'guild' ? '公會劇情目錄' :
                            this.activeTabType === 'chara' ? `${this.activeCharaName} 的個人劇情目錄` :
                            this.activeTabType === 'tower' ? '露娜塔/系統劇情目錄' : '目錄'
                        }
                    </div>
                    <div class="story-list-scrollbar">
                        ${controlPanelHtml}
                    </div>
                </div>
            </div>
        </div>
        `;

        if (!skipAutoSelect && (this.activeTabType !== 'chara' || this.activeCharaName) && chapterKeys.length > 0 && this.expandedChapter && this.chapters[this.expandedChapter] && this.chapters[this.expandedChapter].length > 0) {
            setTimeout(() => {
                this.selectStory(this.chapters[this.expandedChapter][0].id);
            }, 0);
        }
        this.updateReaderState();

        // 處理非同步暫存跳轉
        if (this.pendingJumpStoryId) {
            const tempId = this.pendingJumpStoryId;
            this.pendingJumpStoryId = null;
            setTimeout(() => {
                this.jumpToStory(tempId);
            }, 50);
        }
    },

    async render(skipAutoSelect = false) {
        this.safeRender(() => this._render(skipAutoSelect));
    },

    switchPart(part) {
        this.currentPart = part;
        this.activeStoryId = null;
        this.expandedChapter = null;

        const isMobile = window.innerWidth <= 768;
        const container = document.querySelector('.map-container');
        const isReading = container && container.classList.contains('show-reader');

        this.safeRender(() => this._render()).then(() => {
            if (isMobile && isReading) {
                const chapterKeys = Object.keys(this.chapters);
                if (chapterKeys.length > 0) {
                    const firstChapter = chapterKeys[0];
                    this.expandedChapter = firstChapter;
                    const childStories = this.chapters[firstChapter] || [];
                    if (childStories.length > 0) {
                        this.selectStory(childStories[0].id);
                    }
                }
            }
        });
    },

    selectChara(charaName) {
        this.activeCharaName = charaName;
        this.expandedChapter = charaName;
        this.safeRender(() => this._render());
    },

    clearActiveChara() {
        this.activeCharaName = null;
        this.expandedChapter = null;
        this.safeRender(() => this._render());
    },

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

        if (prevChIndex !== -1) {
            const prevItem = document.getElementById(`acc-item-${prevChIndex}`);
            if (prevItem) {
                prevItem.classList.remove('active');
                const content = prevItem.querySelector('.accordion-content');
                if (content) content.style.maxHeight = "0px";
                if (this.activeTabType === 'main') {
                    const icon = prevItem.querySelector('.acc-folder-icon');
                    if (icon) icon.innerText = "📁";
                }
            }
        }

        const currItem = document.getElementById(`acc-item-${chIndex}`);
        if (currItem && this.expandedChapter === chKey) {
            currItem.classList.add('active');
            const childStories = this.chapters[chKey];
            const content = currItem.querySelector('.accordion-content');
            if (content) {
                // 先設為 auto 量測實際高度，再用 transition 展開
                content.style.maxHeight = 'none';
                const scrollH = content.scrollHeight;
                content.style.maxHeight = '0px';
                requestAnimationFrame(() => {
                    content.style.maxHeight = scrollH + 'px';
                    // 動畫結束後切回 none 以適應動態內容
                    setTimeout(() => { content.style.maxHeight = 'none'; }, 350);
                });
            }
            if (this.activeTabType === 'main') {
                const icon = currItem.querySelector('.acc-folder-icon');
                if (icon) icon.innerText = "📂";
            }

            if (childStories.length > 0) {
                this.selectStory(childStories[0].id);
            }
        }
    },

    getStoryById(storyId) {
        return this.stories.find(s => s.id === storyId) || this.eventStories.find(s => s.id === storyId);
    },

    async selectStory(storyId) {
        this.activeStoryId = storyId;

        document.querySelectorAll('.story-item').forEach(el => el.classList.remove('active'));
        const activeItem = document.getElementById(`story-item-${storyId}`);
        if (activeItem) activeItem.classList.add('active');

        const story = this.getStoryById(storyId);
        if (!story) return;

        const chTag = document.getElementById('cinema-ch-tag');
        const titleEl = document.getElementById('cinema-title');

        if (chTag && titleEl) {
            if (this.activeTabType === 'event') {
                chTag.innerText = "活動";
            } else if (this.activeTabType === 'guild') {
                chTag.innerText = "公會";
            } else if (this.activeTabType === 'chara') {
                chTag.innerText = "個人";
            } else if (this.activeTabType === 'tower') {
                chTag.innerText = "其他";
            } else {
                const match = story.chapter.match(/^(第\d+部\s*)?([^\s]+)/);
                chTag.innerText = match ? match[2] : "主線";
            }
            titleEl.innerText = story.title || "話標題";

            await this.updateSummaryContent();

            if (this.isDialogueExpanded) {
                this.loadDialogue(storyId);
            }
            this.updateNavigationButtons();
            this.updateReaderState();
        }
    },

    toPrevStory() {
        const prevId = this.getPrevStoryId();
        if (prevId) this.selectStory(prevId);
    },

    toNextStory() {
        const nextId = this.getNextStoryId();
        if (nextId) this.selectStory(nextId);
    },

    getPrevStoryId() {
        const storyItems = Array.from(document.querySelectorAll('.story-item'));
        const storyIds = storyItems.map(el => parseInt(el.id.replace('story-item-', ''), 10));
        const index = storyIds.indexOf(this.activeStoryId);
        return index > 0 ? storyIds[index - 1] : null;
    },

    getNextStoryId() {
        const storyItems = Array.from(document.querySelectorAll('.story-item'));
        const storyIds = storyItems.map(el => parseInt(el.id.replace('story-item-', ''), 10));
        const index = storyIds.indexOf(this.activeStoryId);
        return index !== -1 && index < storyIds.length - 1 ? storyIds[index + 1] : null;
    },

    updateNavigationButtons() {
        const prevId = this.getPrevStoryId();
        const nextId = this.getNextStoryId();
        const btnPrev = document.getElementById('btn-prev-story');
        const btnNext = document.getElementById('btn-next-story');
        if (btnPrev) btnPrev.style.display = prevId ? 'block' : 'none';
        if (btnNext) btnNext.style.display = nextId ? 'block' : 'none';
    },

    scrollToControlPanel() {
        const panel = document.querySelector('.map-control-panel');
        if (panel) {
            panel.scrollIntoView({ behavior: 'smooth' });
            panel.classList.add('highlight-panel');
            setTimeout(() => {
                panel.classList.remove('highlight-panel');
            }, 1500);
        }
    },

    updateReaderState() {
        const container = document.querySelector('.map-container');
        if (container) {
            if (this.activeStoryId && this.currentView !== 'menu') {
                container.classList.add('show-reader');
            } else {
                container.classList.remove('show-reader');
            }
        }
    },

    exitReader() {
        this.activeStoryId = null;
        document.querySelectorAll('.story-item').forEach(el => el.classList.remove('active'));
        this.updateReaderState();
        const summaryEl = document.getElementById('cinema-summary');
        if (summaryEl) {
            summaryEl.innerHTML = '點擊上方章節清單，即刻載入大綱與對白文本。';
        }
        window.scrollTo({ top: 0, behavior: 'instant' });
    },

    handleBackClick() {
        const container = document.querySelector('.map-container');
        if (container && container.classList.contains('show-reader')) {
            this.exitReader();
        } else {
            if (this.activeTabType === 'chara' && this.activeCharaName) {
                this.clearActiveChara();
            } else {
                this.goBackToMenu();
            }
        }
    },

    scrollToTop() {
        const isMobile = window.innerWidth <= 768;
        if (isMobile) {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
            const cinemaSummary = document.getElementById('cinema-summary');
            if (cinemaSummary) cinemaSummary.scrollTop = 0;
        }
    },

    getQuickDirectoryHtml() {
        const isMobile = window.innerWidth <= 768;
        if (!isMobile) {
            return null;
        }

        const currentChapter = this.expandedChapter || "";
        const childStories = this.chapters[currentChapter] || [];
        const chaptersList = Object.keys(this.chapters);

        let html = `<div class="quick-directory-wrapper"><div class="quick-dir-scroll-container">`;
        
        if (this.activeSummaryTab === 'part' && this.activeTabType === 'main') {
            for (let p = 1; p <= 3; p++) {
                const isActivePart = this.currentPart === p;
                html += `<button class="quick-dir-btn part-btn ${isActivePart ? 'active' : ''}" style="background: rgba(9, 132, 227, 0.06) !important; border-color: rgba(9, 132, 227, 0.2) !important; color: #0984e3 !important;" onclick="QuestMapModule.selectPartFromTab(${p})">第${p}部</button>`;
            }
        } else if (this.activeSummaryTab === 'chapter') {
            chaptersList.forEach(chKey => {
                const isActive = chKey === currentChapter;
                const shortChName = chKey.replace(/^(第\d+部\s*)/, '');
                html += `<button class="quick-dir-btn chapter-btn ${isActive ? 'active' : ''}" onclick="QuestMapModule.selectChapterFromTab('${this.escapeHtml(chKey)}')">${this.escapeHtml(shortChName)}</button>`;
            });
            if (chaptersList.length === 0) {
                html += `<span style="font-size: 0.85rem; color: var(--text-secondary); padding: 8px;">暫無章節</span>`;
            }
        } else {
            childStories.forEach(s => {
                const isActive = s.id === this.activeStoryId;
                const shortTitle = s.title_short || s.title.split(' ')[0] || `第${s.episode}話`;
                html += `<button class="quick-dir-btn episode-btn ${isActive ? 'active' : ''}" onclick="QuestMapModule.selectEpisodeFromTab(${s.id})">${this.escapeHtml(shortTitle)}</button>`;
            });
            if (childStories.length === 0) {
                html += `<span style="font-size: 0.85rem; color: var(--text-secondary); padding: 8px;">此章節暫無話數</span>`;
            }
        }
        
        html += `</div></div>`;
        return html;
    },

    async selectPartFromTab(part) {
        this.currentPart = part;
        this.activeStoryId = null;
        this.expandedChapter = null;
        this.activeSummaryTab = 'chapter'; // 點部自動跳章

        await this.safeRender(() => this._render());

        const chapterKeys = Object.keys(this.chapters);
        if (chapterKeys.length > 0) {
            const firstChapter = chapterKeys[0];
            this.expandedChapter = firstChapter;
            const childStories = this.chapters[firstChapter] || [];
            if (childStories.length > 0) {
                await this.selectStory(childStories[0].id);
            } else {
                this.updateSummaryTabsUI();
                this.updateSummaryContent();
            }
        } else {
            this.updateSummaryTabsUI();
            this.updateSummaryContent();
        }
    },

    async selectChapterFromTab(chKey) {
        this.expandedChapter = chKey;
        this.activeSummaryTab = 'episode'; // 點章自動跳話
        
        const childStories = this.chapters[chKey] || [];
        if (childStories.length > 0) {
            await this.selectStory(childStories[0].id);
        } else {
            this.updateSummaryTabsUI();
            this.updateSummaryContent();
        }
    },

    async selectEpisodeFromTab(storyId) {
        // 維持在 episode 頁籤，只切換話數
        await this.selectStory(storyId);
    },

    handleChapterTabClick() {
        if (this.activeSummaryTab === 'episode') {
            this.switchSummaryTab('chapter'); // 切換回選章
        } else {
            this.switchSummaryTab('episode'); // 切換回選話
        }
    },

    switchSummaryTab(tabType) {
        this.activeSummaryTab = tabType;
        this.updateSummaryTabsUI();
        this.updateSummaryContent();
    },

    updateSummaryTabsUI() {
        const isMobile = window.innerWidth <= 768;
        const tabsContainer = document.querySelector('.summary-tabs');
        if (!tabsContainer) return;

        if (!isMobile) {
            // 桌機版回復原本的三頁籤
            tabsContainer.innerHTML = `
                <button id="tab-summary-episode" class="summary-tab ${this.activeSummaryTab === 'episode' ? 'active' : ''}" onclick="QuestMapModule.switchSummaryTab('episode')" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid ${this.activeSummaryTab === 'episode' ? 'var(--accent-color)' : 'transparent'}; color: ${this.activeSummaryTab === 'episode' ? 'var(--accent-color)' : 'var(--text-secondary)'}; cursor: pointer; font-weight: ${this.activeSummaryTab === 'episode' ? 'bold' : 'normal'}; font-size: 0.88rem;">📜 單話大綱</button>
                <button id="tab-summary-ai-summary" class="summary-tab ${this.activeSummaryTab === 'ai-summary' ? 'active' : ''}" onclick="QuestMapModule.switchSummaryTab('ai-summary')" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid ${this.activeSummaryTab === 'ai-summary' ? 'var(--accent-color)' : 'transparent'}; color: ${this.activeSummaryTab === 'ai-summary' ? 'var(--accent-color)' : 'var(--text-secondary)'}; cursor: pointer; font-weight: ${this.activeSummaryTab === 'ai-summary' ? 'bold' : 'normal'}; font-size: 0.88rem;">💡 單話摘要簡介</button>
                <button id="tab-summary-chapter" class="summary-tab ${this.activeSummaryTab === 'chapter' ? 'active' : ''}" onclick="QuestMapModule.switchSummaryTab('chapter')" style="padding: 8px 16px; background: transparent; border: none; border-bottom: 2px solid ${this.activeSummaryTab === 'chapter' ? 'var(--accent-color)' : 'transparent'}; color: ${this.activeSummaryTab === 'chapter' ? 'var(--accent-color)' : 'var(--text-secondary)'}; cursor: pointer; font-weight: ${this.activeSummaryTab === 'chapter' ? 'bold' : 'normal'}; font-size: 0.88rem;">📖 整章摘要簡介</button>
            `;
            return;
        }

        // 行動端頁籤
        const story = this.getStoryById(this.activeStoryId);
        const hasPart = this.activeTabType === 'main';

        let partText = "第1部";
        if (story) {
            partText = `第${story.part || this.currentPart || 1}部`;
        } else if (this.currentPart) {
            partText = `第${this.currentPart}部`;
        }

        let chapterText = "第1章";
        if (this.expandedChapter) {
            const match = this.expandedChapter.match(/第\d+章/);
            chapterText = match ? match[0] : this.expandedChapter;
        } else if (story && story.chapter) {
            const match = story.chapter.match(/第\d+章/);
            chapterText = match ? match[0] : story.chapter;
        }

        if (this.activeSummaryTab === 'part' && !hasPart) {
            this.activeSummaryTab = 'chapter';
        }
        if (!this.activeSummaryTab) {
            this.activeSummaryTab = 'episode';
        }

        let tabsHtml = "";
        if (hasPart) {
            tabsHtml += `
                <button id="tab-summary-part" class="summary-tab ${this.activeSummaryTab === 'part' ? 'active' : ''}" onclick="QuestMapModule.switchSummaryTab('part')" style="flex: 1; text-align: center; padding: 8px 6px; background: transparent; border: none; border-bottom: 2px solid ${this.activeSummaryTab === 'part' ? 'var(--accent-color)' : 'transparent'}; color: ${this.activeSummaryTab === 'part' ? 'var(--accent-color)' : 'var(--text-secondary)'}; cursor: pointer; font-weight: ${this.activeSummaryTab === 'part' ? 'bold' : 'normal'}; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${partText}</button>
            `;
        }
        
        const isChapterOrEpisodeActive = this.activeSummaryTab === 'chapter' || this.activeSummaryTab === 'episode';
        let displayChName = chapterText;
        if (this.activeSummaryTab === 'chapter') {
            displayChName = `📖 選擇章節 (${chapterText})`;
        }

        tabsHtml += `
            <button id="tab-summary-chapter" class="summary-tab ${isChapterOrEpisodeActive ? 'active' : ''}" onclick="QuestMapModule.handleChapterTabClick()" style="flex: 1; text-align: center; padding: 8px 6px; background: transparent; border: none; border-bottom: 2px solid ${isChapterOrEpisodeActive ? 'var(--accent-color)' : 'transparent'}; color: ${isChapterOrEpisodeActive ? 'var(--accent-color)' : 'var(--text-secondary)'}; cursor: pointer; font-weight: ${isChapterOrEpisodeActive ? 'bold' : 'normal'}; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${displayChName}</button>
        `;

        tabsContainer.innerHTML = tabsHtml;
    },

    async updateSummaryContent() {
        const summaryEl = document.getElementById('cinema-summary');
        if (!summaryEl || !this.activeStoryId) return;

        const story = this.getStoryById(this.activeStoryId);
        if (!story) return;

        const isMobile = window.innerWidth <= 768;

        if (this.activeSummaryTab === 'episode' || (isMobile && this.activeSummaryTab !== 'ai-summary')) {
            try {
                let tableName = 'story_detail';
                if (story.isEvent) {
                    tableName = 'event_story_detail';
                } else {
                    const checkChara = await window.PCRDatabase.runQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='chara_story_detail'");
                    const isTW = !(checkChara && checkChara.length > 0);
                    if (isTW) {
                        tableName = 'story_detail';
                    } else if (story.type === 'guild') {
                        tableName = 'guild_story_detail';
                    } else if (story.type === 'chara') {
                        tableName = 'chara_story_detail';
                    } else if (story.type === 'tower') {
                        tableName = 'tower_story_detail';
                    }
                }
                const sql = `SELECT sub_title FROM ${tableName} WHERE story_id = ${this.activeStoryId}`;
                const result = await window.PCRDatabase.runQuery(sql);
                let officialSummary = "";
                if (result && result.length > 0 && result[0].sub_title) {
                    officialSummary = result[0].sub_title;
                }
                const isMobile = window.innerWidth <= 768;
                let topDirOrSummaryHtml = "";
                if (isMobile) {
                    topDirOrSummaryHtml = this.getQuickDirectoryHtml();
                } else {
                    topDirOrSummaryHtml = `
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
                            <p style="margin:0; color: var(--text-primary);">${this.escapeHtml(officialSummary) || "本話為重要主線劇情，美食殿堂的羈絆在此得到了進一步的昇華。"}</p>
                        </div>
                    `;
                }

                summaryEl.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 14px; text-align: left;">
                        ${topDirOrSummaryHtml}

                        <div class="dialogue-section">
                            <div class="game-dialogue-panel">
                                <div class="game-dialogue-header" style="border-radius: 12px 12px 0 0;">✦ 劇情全文 ✦</div>
                                <div id="chara-badges-bar" class="game-chara-list-bar" style="
                                    background: rgba(252,242,246,0.9);
                                    border-left: 1.5px solid rgba(232,56,117,0.15);
                                    border-right: 1.5px solid rgba(232,56,117,0.15);
                                    border-top: none;
                                    border-bottom: 1px solid rgba(232,56,117,0.1);
                                ">
                                    <span style="color: var(--text-secondary); font-size: 0.8rem;">正在載入登場角色頭像...</span>
                                </div>
                                <div id="dialogue-board" class="game-dialogue-board">
                                </div>
                                <div class="game-dialogue-footer" style="border-radius: 0 0 12px 12px;">
                                    <div id="btn-prev-story" class="game-footer-btn close" style="display: none;" onclick="QuestMapModule.toPrevStory()">⬅ 上一話</div>
                                    <div class="game-footer-btn close" onclick="QuestMapModule.scrollToTop()">⬆ 回到頂端</div>
                                    <div id="btn-next-story" class="game-footer-btn skip" style="display: none;" onclick="QuestMapModule.toNextStory()">➡️ 下一話</div>
                                </div>
                            </div>
                        </div>

                    </div>
                `;
                this.updateSummaryTabsUI();
            } catch (e) {
                console.error(e);
                summaryEl.innerHTML = `<div style="color: #ff6b6b;">無法載入官方大綱。</div>`;
            }
        } else if (this.activeSummaryTab === 'ai-summary') {
            try {
                // 取得單話摘要
                const aiSummary = ChapterDataService.getStorySummary(story.part, story.groupId, story.id);
                const displaySummary = aiSummary || "暫無本話的單話摘要簡介。";

                summaryEl.innerHTML = `
                    <div class="chapter-summary-box" style="text-align: left; line-height: 1.7; font-size: 0.92rem; color: var(--text-primary); padding: 18px; background: rgba(232, 56, 117, 0.03); border-radius: 12px; border: 1px solid rgba(232, 56, 117, 0.12); box-shadow: 0 4px 12px rgba(232, 56, 117, 0.02);">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                            <span style="background: var(--accent-gradient); color: #fff; font-size: 0.75rem; font-weight: 700; padding: 3px 12px; border-radius: 20px; letter-spacing: 0.5px;">💡 單話摘要簡介</span>
                            <span style="font-size: 0.8rem; color: var(--text-secondary);">ID: ${story.id}</span>
                        </div>
                        <p style="color: var(--text-primary); margin: 0; font-size: 0.9rem; white-space: pre-wrap; line-height: 1.8;">${this.escapeHtml(displaySummary)}</p>
                    </div>
                `;
                this.updateSummaryTabsUI();
            } catch (e) {
                console.error(e);
                summaryEl.innerHTML = `<div style="color: #ff6b6b;">無法載入單話摘要。</div>`;
            }
        } else {
            if (story.isEvent) {
                const currentEvent = this.events.find(e => e.story_group_id === story.groupId);
                if (currentEvent) {
                    const date = new Date(currentEvent.start_time);
                    const timeLabel = isNaN(date.getFullYear()) ? "未知時間" : `${date.getFullYear()}年${date.getMonth() + 1}月`;
                    const totalEpisodes = this.eventStories.filter(s => s.groupId === currentEvent.story_group_id).length;
                    const gidStr = String(currentEvent.story_group_id);
                    const aiSummary = (this.eventSummaries && this.eventSummaries[gidStr]) ? this.eventSummaries[gidStr] : null;
                    let descHtml = "";
                    if (aiSummary) {
                        descHtml = `<p style="color: var(--text-primary); margin: 0 0 10px 0; font-size: 0.88rem; white-space: pre-wrap; line-height: 1.7;">${this.escapeHtml(aiSummary)}</p>`;
                    } else {
                        descHtml = `
                            <p style="color: var(--text-primary); margin: 0 0 10px 0; font-size: 0.88rem; line-height: 1.7;">
                                本劇情為 <strong>${timeLabel}</strong> 登場的期間限定角色活動劇情。講述了與該活動核心主角們展開的專屬冒險篇章。
                            </p>
                        `;
                    }

                    summaryEl.innerHTML = `
                        <div class="chapter-summary-box" style="text-align: left; line-height: 1.6; font-size: 0.92rem; color: var(--text-primary); padding: 15px; background: rgba(232, 56, 117, 0.03); border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.08);">
                            <span style="color: var(--accent-color); font-weight: 700; font-size: 1rem; display: block; margin-bottom: 8px;">🏆 【${currentEvent.title}】 活動介紹：</span>
                            ${descHtml}
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
                const chKey = ChapterDataService.getChapterKey(story.part, story.groupId, story.chapter);
                const info = ChapterDataService.getChapterInfo(story.part, story.groupId);
                const summaryText = (info && info.summary) ? info.summary : "暫無本章節的摘要簡介。";
                const realWorldSummary = (info && info.real_world_summary) ? info.real_world_summary : null;

                let realWorldHtml = "";
                if (realWorldSummary) {
                    realWorldHtml = `
                        <div class="real-world-summary-box" style="margin-top: 15px; padding: 12px; border-radius: 8px; background: rgba(9, 132, 227, 0.08); border: 1px solid rgba(9, 132, 227, 0.25); text-align: left; line-height: 1.6;">
                            <div style="color: #0984e3; font-weight: 700; font-size: 0.9rem; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                                <span>🌐</span> 現實線劇情摘要
                            </div>
                            <p style="margin: 0; color: var(--text-primary); font-size: 0.85rem; white-space: pre-wrap; line-height: 1.7;">${this.escapeHtml(realWorldSummary)}</p>
                        </div>
                    `;
                }

                summaryEl.innerHTML = `
                    <div class="chapter-summary-box" style="text-align: left; line-height: 1.6; font-size: 0.92rem; color: var(--text-primary); padding: 15px; background: rgba(232, 56, 117, 0.03); border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.08);">
                        <span style="color: var(--accent-color); font-weight: 700; font-size: 1rem; display: block; margin-bottom: 8px;">📖 【${chKey}】 劇情摘要：</span>
                        <p style="color: var(--text-primary); margin: 0; font-size: 0.88rem; white-space: pre-wrap; line-height: 1.7;">${this.escapeHtml(summaryText)}</p>
                        ${realWorldHtml}
                    </div>
                `;
            }
        }
    },

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

        if (this.isLoadingDialogue) return;
        this.isLoadingDialogue = true;

        window.DialogueView.renderLoading(board);

        try {
            const response = await fetch(`story/${storyId}.json?v=${Date.now()}`);
            if (!response.ok) throw new Error("HTTP " + response.status);

            const rawDialogueList = await response.json();

            if (!rawDialogueList || rawDialogueList.length === 0) {
                window.DialogueView.renderEmpty(board);
                return;
            }

            // 使用 DialogueNormalizer 進行純資料正規化與發言人萃取
            const { dialogueList, speakerNames } = window.DialogueNormalizer.normalize(rawDialogueList);

            await this.loadDialogueAvatars(speakerNames);

            const badgesBar = document.getElementById('chara-badges-bar');
            const cinemaPanel = document.querySelector('.cinema-panel');
            const currentStoryObj = this.getStoryById(storyId);

            window.DialogueView.renderDialogue({
                boardEl: board,
                badgesBarEl: badgesBar,
                cinemaPanelEl: cinemaPanel,
                storyId: storyId,
                dialogueList: dialogueList,
                speakerNames: speakerNames,
                speakerAvatars: this.speakerAvatars,
                currentStoryObj: currentStoryObj,
                resolveRealName: this.getCharaRealName.bind(this),
                escapeHtml: this.escapeHtml.bind(this)
            });

        } catch (err) {
            console.error("加載台詞失敗:", err);
            window.DialogueView.renderError(board, storyId);
        } finally {
            this.isLoadingDialogue = false;
        }
    },

    openStillPopup(event) {
        return window.MediaService.openStillPopup(event);
    },

    closeStillPopup() {
        return window.MediaService.closeStillPopup();
    },

    playVoice(voiceName) {
        return window.MediaService.playVoice(voiceName);
    },

    openMoviePopup(movieId) {
        if (!movieId) return;
        if (window.MediaService && typeof window.MediaService.openMoviePopup === 'function') {
            return window.MediaService.openMoviePopup(movieId, this.movieLinks);
        }
        const cleanId = String(movieId).replace('movie_', '').replace('story_', '');
        const gdriveId = this.movieLinks ? (this.movieLinks[cleanId] || this.movieLinks[`story_${cleanId}`]) : null;

        let modal = document.getElementById('movie-player-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'movie-player-modal';
            modal.className = 'movie-player-modal';
            modal.innerHTML = `
                <div class="movie-player-box">
                    <div class="movie-player-body" id="movie-player-body"></div>
                </div>
            `;
            document.body.appendChild(modal);
            modal.addEventListener('click', (e) => {
                if (e.target === modal) QuestMapModule.closeMoviePopup();
            });
        }

        const bodyEl = document.getElementById('movie-player-body');
        if (!bodyEl) return;

        if (gdriveId) {
            bodyEl.innerHTML = `<iframe src="https://drive.google.com/file/d/${gdriveId}/preview?autoplay=1" allow="autoplay; fullscreen; encrypted-media" allowfullscreen></iframe>`;
        } else {
            bodyEl.innerHTML = `
                <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #fff; background: #162030; padding: 24px; text-align: center;">
                    <div style="font-size: 2.6rem; margin-bottom: 12px; animation: pulse 2s infinite;">☁️</div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #60a5fa; margin-bottom: 8px;">動畫標識：story_${cleanId}</div>
                    <div style="font-size: 0.88rem; color: #cbd5e1; max-width: 480px; line-height: 1.6;">
                        此動畫正在準備上傳至 Google Drive 雲端中，或尚未同步至映射表。<br>
                        若您在本地已壓制完畢，請執行同步腳本更新線上串流連結。
                    </div>
                </div>
            `;
        }

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    },

    closeMoviePopup() {
        if (window.MediaService && typeof window.MediaService.closeMoviePopup === 'function') {
            return window.MediaService.closeMoviePopup();
        }
        const modal = document.getElementById('movie-player-modal');
        if (modal) {
            modal.classList.remove('active');
            const bodyEl = document.getElementById('movie-player-body');
            if (bodyEl) bodyEl.innerHTML = '';
        }
        document.body.style.overflow = '';
    },

    handleAvatarError(img, realName) {
        // 方案 B 重構：已廢棄，由 AvatarService 統一接管
    },

    // Modal 單例管理 (向下相容與委託)
    getCharaModal() {
        return window.CharaModalView ? window.CharaModalView.getCharaModal() : null;
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

        const appearances = (this.appearanceMap &&
            (this.appearanceMap[realCharaName] || this.appearanceMap[charaName])) || [];

        window.CharaModalView.renderModal({
            realCharaName,
            profile,
            appearances,
            speakerAvatars: this.speakerAvatars,
            avatarService: window.AvatarService,
            resolveStoryLabel: (storyId) => {
                const story = this.getStoryById(storyId);
                if (!story) return `ID: ${storyId}`;
                const cleanCh = story.chapter.replace(/^(第\d+部\s*)?([^\s]+章\s*|[^\s]+序章\s*|[^\s]+幕間[^\s]*\s*)/, '');
                let label = `${cleanCh} ${story.title}`.trim();
                if (label.length > 15) label = label.substring(0, 15) + "...";
                return label;
            },
            escapeHtml: (str) => this.escapeHtml(str)
        });
    },

    jumpToStory(storyId, closeModalId) {
        if (closeModalId) {
            const modal = document.getElementById(closeModalId);
            if (modal) modal.classList.remove('active');
        }

        // 如果 stories 尚未載入完畢，暫存此次跳轉，等待 _render 結束後自動重試
        if (this.stories.length === 0) {
            this.pendingJumpStoryId = storyId;
            return;
        }

        const story = this.getStoryById(storyId);
        if (!story) {
            console.warn('[QuestMapModule] 找不到對應的故事 ID:', storyId);
            return;
        }

        const isEvent = story.isEvent;
        const storyType = story.type; // 'main', 'chara', 'guild', 'tower'
        if (isEvent && this.activeTabType !== 'event') {
            this.activeTabType = 'event';
        } else if (!isEvent) {
            // 根據 story.type 正確導向對應的分頁
            if (storyType && ['chara', 'guild', 'tower'].includes(storyType)) {
                this.activeTabType = storyType;
            } else {
                this.activeTabType = 'main';
                if (story.part) this.currentPart = story.part;
            }
        }

        if (isEvent) {
            this.groupEventStories();
        } else if (storyType === 'chara') {
            this.groupCharaStories();
        } else if (storyType === 'guild') {
            this.groupGuildStories();
        } else if (storyType === 'tower') {
            this.groupTowerStories();
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
            if (storyType === 'chara') {
                this.activeCharaName = targetChKey;
            }
        }

        this.safeRender(async () => {
            await this._render(true);
            this.selectStory(storyId);
            setTimeout(() => {
                const el = document.getElementById(`story-item-${storyId}`);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        });
    },

    _getSpeakerViewOptions() {
        return {
            appearanceMap: this.appearanceMap,
            speakerAvatars: this.speakerAvatars,
            searchQuery: this.speakerSearchQuery,
            sortOrder: this.speakerSortOrder,
            avatarService: window.AvatarService,
            resolveRealName: (name) => this.getCharaRealName(name),
            escapeHtml: (str) => this.escapeHtml(str)
        };
    },

    renderSpeakerTab(tab) {
        if (!tab) return;
        const options = this._getSpeakerViewOptions();
        tab.innerHTML = window.SpeakerView.renderSpeakerPageHtml(options);
    },

    handleSpeakerSearch(value) {
        this.speakerSearchQuery = value;
        // 使用 debounce 防止每次按鍵都完整重建 DOM
        clearTimeout(this._speakerSearchTimer);
        this._speakerSearchTimer = setTimeout(() => {
            this._updateSpeakerGrid();
        }, 300);
    },

    handleSpeakerSort(value) {
        this.speakerSortOrder = value;
        this._updateSpeakerGrid();
    },

    /** 只更新角色 grid 內容，不重建整個頁面（保留搜尋框焦點） */
    _updateSpeakerGrid() {
        const gridEl = document.querySelector('.speaker-grid');
        if (!gridEl) {
            // fallback: 如果找不到 grid，完整重建
            const tab = document.getElementById('map-tab');
            if (tab) this.renderSpeakerTab(tab);
            return;
        }
        const options = this._getSpeakerViewOptions();
        gridEl.innerHTML = window.SpeakerView.renderSpeakerGridHtml(options);
    }
};

if (window.ChapterDataService && window.AvatarService && window.SpeakerView && window.CharaModalView && window.DialogueNormalizer && window.MediaService) {
    console.log("[QuestMapModule] 所有相依服務已就緒");
}
