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
    extraStoryIndex: null,
    activeExtraCategory: null,
    activeCharaName: null,
    charaSearchQuery: "",
    directoryLevel: 'level1', // 'level1' (章節/活動卡片清單) | 'level2' (話數清單)
    directoryLevel1ScrollTop: 0,
    autoVoiceStartIndex: null,
    _dialogueCache: new Map(),
    _loadDataPromise: null,
    _appearanceMapPromise: null,
    _movieLinksPromise: null,

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
            gridHtml += this.getCharaCardHtml(chName, stories);
            count++;
        });

        if (count === 0) {
            gridEl.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-secondary); font-size: 1.1rem;">查無此角色</div>`;
        } else {
            gridEl.innerHTML = gridHtml;
        }
    },

    getCharaCardHtml(chName, stories) {
        const firstStory = Array.isArray(stories) ? stories[0] : null;
        const groupId = firstStory ? firstStory.groupId : 1001;
        const cardId = `${groupId}31`;
        const localCardUrl = `card/${cardId}.webp`;
        const remoteCardUrl = `https://redive.estertion.win/card/full/${cardId}.webp`;

        return `
            <div class="chara-card" onclick="QuestMapModule.selectChara('${this.escapeForAttr(chName)}')">
                <img
                    class="chara-card-image"
                    src="${localCardUrl}"
                    data-fallback-src="${remoteCardUrl}"
                    loading="lazy"
                    decoding="async"
                    alt=""
                    onerror="QuestMapModule.handleCharaCardImageError(this)"
                >
                <div class="chara-card-overlay">
                    <div class="chara-card-name">${this.escapeHtml(chName)}</div>
                    <div class="chara-card-count">${Array.isArray(stories) ? stories.length : 0} 話</div>
                </div>
            </div>
        `;
    },

    handleCharaCardImageError(img) {
        if (!img || img.dataset.fallbackUsed === '1') return;
        const fallbackSrc = img.dataset.fallbackSrc;
        if (!fallbackSrc) return;
        img.dataset.fallbackUsed = '1';
        img.src = fallbackSrc;
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

    normalizeDisplayTitle(text) {
        if (!text) return "";
        return String(text)
            .replace(/\\n/g, " ")
            .replace(/\r?\n/g, " ")
            .replace(/[\u3000\s]+/g, " ")
            .trim();
    },

    getStoryItemHtml(s, chDisplay, titleDisplay) {
        const isSpecialNoThumb = (s.id >= 1001 && s.id <= 1005);
        let thumbHtml = "";
        if (isSpecialNoThumb) {
            thumbHtml = `<span style="font-size: 1.2rem; display: flex; align-items: center; justify-content: center; width: 100%; height: 100%;">📖</span>`;
        } else {
            const thumbData = (this.storyThumbnails && this.storyThumbnails[s.id]) || {};
            const stillId = thumbData.still_id || s.still_id || null;
            const bgId = thumbData.bg_id || s.bg_id || null;
            const options = (s.type === 'chara' && s.groupId) ? { characterGroupId: s.groupId } : {};
            thumbHtml = StoryAssetService.getStoryThumbnailHtml(
                s.id,
                stillId,
                bgId,
                'story-thumb-img',
                'width:100%;height:100%;object-fit:cover;',
                options
            );
        }
        const cleanCh = this.normalizeDisplayTitle(chDisplay);
        const cleanTitle = this.normalizeDisplayTitle(titleDisplay);
        const hasTitle = cleanTitle && cleanTitle !== cleanCh;
        return `
            <div class="story-item ${this.activeStoryId === s.id ? 'active' : ''}" id="story-item-${s.id}" onclick="QuestMapModule.selectStory(${s.id})">
                <div class="story-item-thumb">
                    ${thumbHtml}
                </div>
                <div class="story-item-content">
                    <div class="story-item-ch">${this.escapeHtml(cleanCh)}</div>
                    ${hasTitle ? `<div class="story-item-title">${this.escapeHtml(cleanTitle)}</div>` : ''}
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

    // Story Map playback / async lifecycle has one source of truth here.
    // AUTO.stop() normally stops MediaService too; the explicit stop also
    // covers manual voice playback while AUTO itself is IDLE.
    _stopStoryPlayback() {
        if (window.AutoVoiceController && typeof window.AutoVoiceController.stop === 'function') {
            window.AutoVoiceController.stop();
        }
        if (window.MediaService && typeof window.MediaService.stopVoice === 'function') {
            window.MediaService.stopVoice();
        }
    },

    _invalidateStoryAsyncWork() {
        this._storyRenderToken = (this._storyRenderToken || 0) + 1;
        this._dialogueLoadingToken = null;
        this.isLoadingDialogue = false;
    },

    teardownPlayback(options = {}) {
        this._stopStoryPlayback();
        if (options.invalidateAsync === true) {
            this._invalidateStoryAsyncWork();
        }
    },

    async loadData() {
        if (this._loadDataPromise) {
            return this._loadDataPromise;
        }

        this._loadDataPromise = this._loadDataInternal();
        try {
            return await this._loadDataPromise;
        } catch (err) {
            // Allow a later retry if startup failed (for example, transient DB/network error).
            this._loadDataPromise = null;
            throw err;
        }
    },

    async _loadDataInternal() {
        // The first menu can render before SQLite is ready. Data-backed views
        // join the single database startup promise when they are actually needed.
        // Keep this await outside the broad data-loading catch so startup failure
        // propagates to the caller instead of rendering an empty data view.
        if (window.PCRD_DATABASE_READY) {
            await window.PCRD_DATABASE_READY;
        }

        try {
            // 核心清單資料彼此獨立，並行準備。官方大綱 metadata 不屬於
            // 清單核心資料；它會在使用者真正開啟單話大綱時由 StoryDataService 載入。
            await Promise.all([
                window.ChapterDataService
                    ? window.ChapterDataService.load()
                    : Promise.resolve(),
                (window.AvatarService && typeof window.AvatarService.ensureManifestLoaded === 'function')
                    ? window.AvatarService.ensureManifestLoaded()
                    : Promise.resolve()
            ]);

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

            if (!this.extraStoryIndex) {
                try {
                    const resp = await fetch('data/extra_story_index.json');
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    this.extraStoryIndex = await resp.json();
                } catch (e) {
                    console.error('[QuestMapModule] 無法載入官方額外劇情索引:', e);
                    this.extraStoryIndex = { official_categories: [], special_categories: [] };
                }
            }

            if (this.stories.length === 0) {
                const checkChara = await window.PCRDatabase.runQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='chara_story_detail'");
                const isTW = !(checkChara && checkChara.length > 0);

                if (isTW) {
                    // 1. 台版主線劇情
                    const sql = `
                        SELECT story_id, title, sub_title, story_group_id, story_end
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
                            storyEnd: row.story_end || 0,
                        };
                    });

                    // 【主線第 16 章後續幕間劇情兜底 (XXVII ~ XXIX)】
                    const pendingCh16Interludes = [
                        { id: 2216097, chapter: "幕間‧XXVII", title: "裂開的天空，崩塌的世界", groupId: 2216, part: 3, isEvent: false, type: 'main', storyEnd: 0 },
                        { id: 2216098, chapter: "幕間‧XXVIII", title: "2nd vision", groupId: 2216, part: 3, isEvent: false, type: 'main', storyEnd: 0 },
                        { id: 2216099, chapter: "幕間‧XXIX", title: "ANSWER.", groupId: 2216, part: 3, isEvent: false, type: 'main', storyEnd: 0 },
                    ];
                    pendingCh16Interludes.forEach(ep => {
                        if (!this.stories.some(s => s.id === ep.id)) {
                            this.stories.push(ep);
                        }
                    });

                    // 【主線第 17 章前 3 話兜底】
                    const pendingCh17Stories = [
                        { id: 2217001, chapter: "3部 第17章 第1話", title: "「第二型態」", groupId: 2217, part: 3, isEvent: false, type: 'main', storyEnd: 0 },
                        { id: 2217002, chapter: "3部 第17章 第2話", title: "不相交的100億與１", groupId: 2217, part: 3, isEvent: false, type: 'main', storyEnd: 0 },
                        { id: 2217003, chapter: "3部 第17章 第3話", title: "雪菲vs彌勒", groupId: 2217, part: 3, isEvent: false, type: 'main', storyEnd: 0 },
                    ];
                    pendingCh17Stories.forEach(ep => {
                        if (!this.stories.some(s => s.id === ep.id)) {
                            this.stories.push(ep);
                        }
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
                    // 由於台服資料庫 (redive_tw.db) 有時尚未上架新角色的個人故事章節，
                    // 我們在此自動為已下載故事對話的新角色補全 4 話的個人故事目錄，確保網頁必定能順利讀取！
                    const pendingNewCharas = [
                        { unitId: 138301, name: "貪吃佩可（阿斯特萊亞）", prefix: "138300" },
                        { unitId: 138701, name: "若菜（冬日）", prefix: "138700" },
                        { unitId: 138801, name: "栞（冬日）", prefix: "138800" },
                        { unitId: 139101, name: "凱留（霸瞳天星）", prefix: "139100" },
                        { unitId: 139201, name: "美穗", prefix: "139200" },
                        { unitId: 139301, name: "真穗", prefix: "139300" },
                        { unitId: 139401, name: "艾麗卡", prefix: "139400" },
                        { unitId: 136901, name: "璐璐伊", prefix: "136900", titles: ["璐璐伊和觸手款待", "近侍璐璐伊和「深邃庭園」", "覺醒！扭動威力！", "奇妙海女的禮物"] },
                        { unitId: 139501, name: "莉莉（女武神）", prefix: "139500", titles: ["心響共鳴", "思慕逡巡", "比翼連理", "純白無垢"] },
                        { unitId: 139601, name: "可璃亞（女武神）", prefix: "139600", titles: ["可璃亞，成為不良分子", "我的真心話", "不是乖孩子了", "libertas qualia"] },
                        { unitId: 139701, name: "普蕾西亞（女武神）", prefix: "139700", titles: ["重逢 的 Porco", "贖罪 的 Ossabaw", "美夢 的 Mangalica", "硬邦邦 的 扭來扭去"] },
                        { unitId: 139801, name: "雪菲（真龍）", prefix: "139800", titles: ["停下來的翅膀", "兄妹之間", "在追憶的彼端所獲得的事物", "夢見黃昏之影與決心之夢"] },
                        { unitId: 139901, name: "露易絲瑪莉（夏日）", prefix: "139900", titles: ["HOT LIMIT", "夏日時光的憂鬱", "無法妥協的夏天", "小小戀歌"] }
                    ];

                    pendingNewCharas.forEach(ch => {
                        const checkGroupId = Math.floor(ch.unitId / 100);
                        for (let i = 1; i <= 4; i++) {
                            const storyId = parseInt(`${ch.prefix}${i}`, 10);
                            if (!charaStories.some(s => s.id === storyId)) {
                                const epTitle = (ch.titles && ch.titles[i - 1]) ? ch.titles[i - 1] : `第 ${i} 話`;
                                charaStories.push({
                                    id: storyId,
                                    chapter: `${ch.name} 第${i}話`,
                                    title: epTitle,
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

                    // 4. 台版露娜塔/系統/額外劇情 (4xxxxxx + 9xxxxxx)
                    const towerSql = `
                        SELECT story_id, title, sub_title, story_group_id
                        FROM story_detail
                        WHERE (story_id >= 4000000 AND story_id < 5000000)
                           OR (story_id >= 9000000 AND story_id < 10000000)
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
                        SELECT story_id, title, sub_title, story_group_id, story_end
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
                            storyEnd: row.story_end || 0,
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
                        10201: "2025-06-01T16:00:00+08:00",
                        10202: "2025-07-01T16:00:00+08:00",
                        10203: "2025-08-01T16:00:00+08:00",
                        10204: "2025-09-01T16:00:00+08:00",
                        10205: "2025-10-01T16:00:00+08:00",
                        10206: "2025-11-01T16:00:00+08:00",
                        10207: "2025-12-01T16:00:00+08:00",
                        10208: "2026-01-01T16:00:00+08:00",
                        10209: "2026-02-01T16:00:00+08:00",
                        10210: "2026-03-01T16:00:00+08:00",
                        10211: "2026-04-01T16:00:00+08:00",
                        10212: "2026-05-01T16:00:00+08:00",
                        10213: "2026-06-01T16:00:00+08:00",
                        10214: "2026-07-01T16:00:00+08:00",
                        10215: "2026-08-01T16:00:00+08:00",
                        10216: "2026-09-01T16:00:00+08:00",
                        10217: "2026-10-01T16:00:00+08:00",
                        10218: "2026-11-01T16:00:00+08:00"
                    };

                    const extraEventsMapped = this.extraEvents.events.map(e => ({
                        story_group_id: e.story_group_id,
                        title: e.title,
                        start_time: extraStartTimeMap[e.story_group_id] || e.start_time || "2025-01-01T16:00:00+08:00",
                        thumbnail_id: e.thumbnail_id,
                        value: e.value
                    }));
                    // 將新形式活動合併，並按時間倒序排序
                    const parseTime = (str) => {
                        if (!str) return 0;
                        const t = new Date(str).getTime();
                        if (!isNaN(t)) return t;
                        return new Date(String(str).replace(/-/g, '/')).getTime() || 0;
                    };
                    this.events = extraEventsMapped.concat(this.events);
                    this.events.sort((a, b) => {
                        const timeA = parseTime(a.start_time);
                        const timeB = parseTime(b.start_time);
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
            this.integrateExtraStories();
        } catch (err) {
            console.error("[QuestMapModule] 載入劇情數據失敗:", err);
        }
    },

    async ensureAppearanceMap() {
        if (this.appearanceMap) return this.appearanceMap;
        if (this._appearanceMapPromise) return this._appearanceMapPromise;

        this._appearanceMapPromise = (async () => {
            try {
                const resp = await fetch('story/speaker_appearance.json');
                if (!resp.ok) return null;
                this.appearanceMap = await resp.json();
                console.log('[QuestMapModule] 成功載入登場角色快取');
                return this.appearanceMap;
            } catch (e) {
                console.error('無法加載登場快取:', e);
                return null;
            } finally {
                this._appearanceMapPromise = null;
            }
        })();

        return this._appearanceMapPromise;
    },

    async ensureMovieLinks() {
        if (this.movieLinks) return this.movieLinks;
        if (this._movieLinksPromise) return this._movieLinksPromise;

        this._movieLinksPromise = (async () => {
            try {
                const resp = await fetch('data/movie_links.json');
                if (!resp.ok) return null;
                this.movieLinks = await resp.json();
                console.log('[QuestMapModule] 成功載入動畫連結映射表');
                return this.movieLinks;
            } catch (e) {
                console.warn('無法加載動畫連結映射表:', e);
                return null;
            } finally {
                this._movieLinksPromise = null;
            }
        })();

        return this._movieLinksPromise;
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
            const cleanTitle = this.normalizeDisplayTitle(evt.title);
            const chName = `${timeLabel} ${cleanTitle}`;

            const childStories = this.eventStories.filter(s => s.groupId === evt.story_group_id);
            if (childStories.length > 0) {
                this.chapters[chName] = childStories.map(s => ({
                    id: s.id,
                    chapter: this.normalizeDisplayTitle(s.chapter || ""),
                    title: this.normalizeDisplayTitle(s.title || ""),
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

    /**
     * 判定話數是否屬於 Extra 體系 (Phase 3 Part E 共用 Helper)
     * 規則:
     * 1. explicit entry: 出現在 official / legacy / special category.stories
     * 2. anniversary child: story.groupId 屬於 anniversary_countdown 10 anchors 對應 group
     * 3. 嚴禁單純以 story id 前綴或 type === 'tower' 猜測
     * @param {Object|number|string} storyOrId 故事物件或故事 ID
     * @returns {{ category: Object, categoryId: string, section: string, isSeriesChild: boolean }|null}
     */
    getExtraMembership(storyOrId) {
        if (!this.extraStoryIndex) return null;

        let story = null;
        let storyId = null;
        if (storyOrId && typeof storyOrId === 'object') {
            story = storyOrId;
            storyId = Number(story.id);
        } else if (storyOrId != null) {
            storyId = Number(storyOrId);
            story = this.getStoryById ? this.getStoryById(storyId) : (this.stories ? this.stories.find(s => s.id === storyId) : null);
        }
        if (!storyId || isNaN(storyId)) return null;

        const sections = [
            { key: 'official_categories', section: 'official' },
            { key: 'legacy_categories', section: 'legacy' },
            { key: 'special_categories', section: 'special' }
        ];

        // 規則 1: explicit entry
        for (const sec of sections) {
            const cats = this.extraStoryIndex[sec.key] || [];
            for (const category of cats) {
                if (category.stories && category.stories.some(s => Number(s.id) === storyId)) {
                    return {
                        category: category,
                        categoryId: category.id,
                        section: sec.section,
                        isSeriesChild: false
                    };
                }
            }
        }

        // 規則 2: anniversary child
        const officialCats = this.extraStoryIndex.official_categories || [];
        const annivCategory = officialCats.find(c => c.id === 'anniversary_countdown');
        if (annivCategory && Array.isArray(annivCategory.stories)) {
            const anniversaryGroupIds = new Set(annivCategory.stories.map(s => Math.floor(Number(s.id) / 1000)));
            const storyGroupId = story && story.groupId != null ? Number(story.groupId) : Math.floor(storyId / 1000);
            if (anniversaryGroupIds.has(storyGroupId)) {
                return {
                    category: annivCategory,
                    categoryId: 'anniversary_countdown',
                    section: 'official',
                    isSeriesChild: true
                };
            }
        }

        return null;
    },

    groupExtraStories() {
        this.chapters = {};
        const category = this.getExtraCategory(this.activeExtraCategory);
        if (!category) return;

        const catStories = this.stories.filter(s => {
            const m = this.getExtraMembership(s);
            return m && m.categoryId === category.id;
        });
        catStories.sort((a, b) => a.id - b.id);

        catStories.forEach(s => {
            const sid = s.id;
            let resolvedChapter = s.chapter || category.title;
            let resolvedTitle = s.title;

            if (category.id === 'luna_tower') {
                // VERIFIED GROUPING: tower_schedule period grouping (7001xxx -> 期數 1)
                const num = parseInt(String(sid).substring(1, 4), 10);
                resolvedChapter = `第 ${num} 期`;
                if (!resolvedTitle || resolvedTitle.startsWith('劇情 ')) {
                    const epNum = parseInt(String(sid).slice(-3), 10);
                    resolvedTitle = `第 ${epNum} 話`;
                }
            } else if (category.id === 'anniversary_countdown') {
                // DISPLAY FALLBACK: UI label for series index entries
                const num = parseInt(String(sid).substring(1, 4), 10);
                const anniMap = {
                    2: '0.5 週年倒數',
                    4: '1 週年倒數',
                    5: '1.5 週年倒數',
                    6: '2 週年倒數',
                    7: '2.5 週年倒數',
                    8: '3 週年倒數',
                    9: '3.5 週年倒數',
                    10: '4 週年倒數',
                    12: '5 週年倒數',
                    13: '5.5 週年倒數'
                };
                resolvedChapter = anniMap[num] || `第 ${num} 期紀念倒數`;
            } else if (category.id === 'raid_activity') {
                // VERIFIED GROUPING: story_group_id 9100
                resolvedChapter = '軍團之戰 (Legion War)';
            } else if (category.id === 'dungeon') {
                // VERIFIED GROUPING: official 20 entries are one subgroup.
                // 4003021/4003022 are canonical rows outside that index.
                resolvedChapter = '地下城';
            } else if (category.id === 'birthday_stories') {
                // DISPLAY FALLBACK (UI grouping): Month grouping for reader navigation UI
                const sub = s.title || '';
                const mMatch = sub.match(/(\d+)月/);
                resolvedChapter = mMatch ? `${mMatch[1]}月生日劇情` : '生日劇情';
            } else if (this.extraStoryIndex?.legacy_categories?.some(c => c.id === category.id)) {
                // Legacy groups are explicitly separated in the index so the
                // old "第 N 話" chapter-key collision cannot recur.
                resolvedChapter = category.title;
            } else if (category.id === 'arena') {
                // VERIFIED GROUPING: story_group_id 4002
                resolvedChapter = s.chapter || '競技場';
            } else {
                resolvedChapter = s.chapter || category.title;
            }

            // Create non-mutating view-model object
            const groupedStory = {
                ...s,
                chapter: resolvedChapter,
                title: resolvedTitle
            };

            if (!this.chapters[resolvedChapter]) this.chapters[resolvedChapter] = [];
            this.chapters[resolvedChapter].push(groupedStory);
        });
    },

    integrateExtraStories() {
        if (!this.extraStoryIndex) return;
        const existing = new Set(this.stories.map(s => s.id));
        const categories = [
            ...(this.extraStoryIndex.official_categories || []).map(c => ({ ...c, section: 'official' })),
            ...(this.extraStoryIndex.legacy_categories || []).map(c => ({ ...c, section: 'legacy' })),
            ...(this.extraStoryIndex.special_categories || []).map(c => ({ ...c, section: 'special' }))
        ];
        categories.forEach(category => category.stories.forEach(entry => {
            if (existing.has(entry.id)) {
                const existingStory = this.stories.find(s => s.id === entry.id);
                if (existingStory) {
                    existingStory.extraCategoryId = category.id;
                    existingStory.extraSection = category.section;
                }
                return;
            }
            this.stories.push({
                id: entry.id,
                chapter: category.title,
                title: entry.title || `劇情 ${entry.id}`,
                groupId: null,
                isEvent: false,
                type: 'extra',
                extraCategoryId: category.id,
                extraSection: category.section,
                language: entry.language
            });
            existing.add(entry.id);
        }));
    },

    getExtraCategory(categoryId) {
        const all = [
            ...(this.extraStoryIndex?.official_categories || []),
            ...(this.extraStoryIndex?.legacy_categories || []),
            ...(this.extraStoryIndex?.special_categories || [])
        ];
        return all.find(c => c.id === categoryId) || null;
    },

    /**
     * 解析 Extra 內層目錄系列卡片的縮圖描述符 (Pure Helper)
     * @param {Object|null} category 當前 Extra Category 物件 (由 getExtraCategory 取得)
     * @param {string} chKey 章節/期數名稱 (如 "第 1 期", "0.5 週年倒數")
     * @param {Array} [childStories=[]] 該期/系列下的話數列表
     * @returns {{ kind: string, id: string }|null} 縮圖描述符或 null
     */
    resolveExtraDirectoryThumbnail(category, chKey, childStories = []) {
        if (!category) return null;

        // A. luna_tower: 仍依期數使用 7001~7030
        if (category.id === 'luna_tower') {
            const match = String(chKey).match(/\d+/);
            if (match) {
                const towerId = 7000 + parseInt(match[0], 10);
                return { kind: 'tower_top', id: String(towerId) };
            }
            return null;
        }

        // B. anniversary_countdown: 依各 series 的首話使用各自 story thumbnail
        if (category.id === 'anniversary_countdown') {
            if (childStories && childStories.length > 0 && childStories[0].id) {
                return { kind: 'story', id: String(childStories[0].id) };
            }
            return null;
        }

        // C. 其他 category: 以 category 的 representativeStoryThumbnail 作為權威依據
        const repThumb = category.representativeStoryThumbnail;
        if (!repThumb || typeof repThumb !== 'string') {
            // D. category 沒有 representativeStoryThumbnail (例如 1001~1005 special categories) -> null
            return null;
        }

        const exstoryMatch = repThumb.match(/icon\/exstory_top\/(\d+)\.webp/);
        if (exstoryMatch) {
            return { kind: 'exstory_top', id: exstoryMatch[1] };
        }

        const towerMatch = repThumb.match(/icon\/tower_top\/(\d+)\.webp/);
        if (towerMatch) {
            return { kind: 'tower_top', id: towerMatch[1] };
        }

        const storyMatch = repThumb.match(/icon\/story\/(\d+)\.webp/);
        if (storyMatch) {
            return { kind: 'story', id: storyMatch[1] };
        }

        return null;
    },

    selectExtraCategory(categoryId) {
        if (!this.getExtraCategory(categoryId)) return;
        this.activeExtraCategory = categoryId;
        this.expandedChapter = null;
        this.directoryLevel = 'level1';
        this.directoryLevel1ScrollTop = 0;
        this.safeRender(() => this._render());
    },

    clearActiveExtraCategory() {
        this.teardownPlayback({ invalidateAsync: true });
        window.ReaderNavigation?.left();
        this.activeExtraCategory = null;
        this.activeStoryId = null;
        this.expandedChapter = null;
        this.directoryLevel = 'level1';
        this.directoryLevel1ScrollTop = 0;
        this.safeRender(() => this._render());
    },

    renderExtraCategorySelector(tab) {
        const official = this.extraStoryIndex?.official_categories || [];
        const legacy = this.extraStoryIndex?.legacy_categories || [];
        const special = this.extraStoryIndex?.special_categories || [];
        const legacyActivities = legacy.filter(c => !c.id.endsWith('_additional'));
        const supplementary = legacy.filter(c => c.id.endsWith('_additional'));
        const section = (title, list, compact = false) => `
            <h3 class="extra-section-title${compact ? ' extra-section-title-compact' : ''}">
                <span>📂</span> ${this.escapeHtml(title)}
            </h3>
            <div class="directory-primary-list extra-category-list${compact ? ' extra-compact-list' : ''}">
                ${list.map(c => `
                    <div class="directory-group-card extra-category-card${compact ? ' extra-compact-card' : ''}${c.representativeStoryThumbnail ? ' has-representative-thumbnail' : ' text-only'}" onclick="QuestMapModule.selectExtraCategory('${this.escapeForAttr(c.id)}')">
                        ${c.representativeStoryThumbnail ? `<div class="extra-card-thumbnail"><img src="${this.escapeForAttr(c.representativeStoryThumbnail)}" alt="${this.escapeForAttr(c.title)}" loading="lazy" decoding="async" onerror="this.closest('.extra-category-card').classList.add('thumbnail-failed')"></div>` : '<div class="extra-card-text-mark" aria-hidden="true">✦</div>'}
                        <div class="dir-group-info extra-card-info">
                            <div class="dir-group-name extra-compact-title">${this.escapeHtml(c.title)}</div>
                            <div class="dir-group-count extra-compact-count">${c.expected_count || c.stories.length} 篇</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        tab.innerHTML = `
            <div class="map-container">
                <div class="breadcrumb-container" style="display: flex; align-items: center; gap: 12px; font-size: 0.95rem;">
                    <span class="breadcrumb-item linkable" onclick="QuestMapModule.goBackToMenu()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;"><span style="font-size: 1.1rem;">🏠</span> 劇情大廳</span>
                    <span class="breadcrumb-separator" style="color: rgba(255,255,255,0.3);">/</span>
                    <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">🌙 額外劇情</span>
                </div>
                <div class="story-navigation-header">
                    <div class="other-category-title" style="display: flex; align-items: center; gap: 8px;">
                        <h2 style="margin: 0; font-size: 1.3rem; color: var(--text-primary);">📖 額外劇情分類</h2>
                        <p class="subtitle" style="margin: 0; color: var(--text-secondary); font-size: 0.85rem;">官方額外劇情、補充與特殊收錄</p>
                    </div>
                </div>
                ${section('官方額外劇情', official)}
                ${section('特別活動', legacyActivities, true)}
                ${section('補充收錄', supplementary, true)}
                ${section('特殊收錄', special, true)}
            </div>
        `;
    },

    switchTabType(type) {
        this.teardownPlayback({ invalidateAsync: true });
        this.activeTabType = type;
        this.activeStoryId = null;
        this.expandedChapter = null;
        this.directoryLevel = 'level1';
        this.directoryLevel1ScrollTop = 0;
        this.safeRender(() => this._render());
    },

    goBackToMenu() {
        this.teardownPlayback({ invalidateAsync: true });
        window.ReaderNavigation?.left();
        this.activeStoryId = null;
        this.currentView = 'menu';
        this._fadeTransition(() => this._render());
    },

    handleFloatingBack() {
        this.handleBackClick();
    },

    enterCategory(type) {
        this.teardownPlayback({ invalidateAsync: true });
        window.ReaderNavigation?.left();
        this.currentView = 'list';
        this.activeTabType = type;
        this.activeStoryId = null;
        this.expandedChapter = null;
        this.directoryLevel = 'level1';
        this.directoryLevel1ScrollTop = 0;
        if (type === 'chara') {
            this.activeCharaName = null;
        }
        if (type === 'extra') {
            this.activeExtraCategory = null;
        }
        this._fadeTransition(() => this._render());
    },

    /** 視圖切換時的 fade-out → fade-in 過渡動畫 */
    _fadeTransition(renderFn) {
        const tab = document.getElementById('map-tab');
        if (!tab) { this.safeRender(renderFn); return; }
        tab.style.transition = 'opacity 0.08s ease-out';
        tab.style.opacity = '0';
        setTimeout(() => {
            this.safeRender(async () => {
                await renderFn.call(this);
                requestAnimationFrame(() => {
                    tab.style.transition = 'opacity 0.12s ease-in';
                    tab.style.opacity = '1';
                });
            });
        }, 80);
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
        const tab = document.getElementById('map-tab');

        // The landing menu is static UI. Render it immediately instead of making
        // first paint wait for SQLite and the full Story Map data preload.
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
                    <div class="menu-card card-sub" onmouseenter="QuestMapModule.changeMenuBg('extra')" onclick="QuestMapModule.enterCategory('extra')" 
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

        await this.loadData();

        if (this.activeTabType === 'extra' && !this.activeExtraCategory) {
            this.renderExtraCategorySelector(tab);
            const existingBackBtn = document.querySelector('.floating-back-btn');
            if (existingBackBtn) existingBackBtn.remove();
            return;
        }

        if (this.activeTabType === 'speaker') {
            await this.ensureAppearanceMap();
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
        } else if (this.activeTabType === 'extra') {
            this.groupExtraStories();
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
                gridHtml += this.getCharaCardHtml(chName, stories);
                count++;
            });

            if (count === 0) {
                gridHtml = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-secondary); font-size: 1.1rem;">查無此角色</div>`;
            }

            tab.innerHTML = `
                <div class="map-container">
                    <div class="breadcrumb-container" style="display: flex; align-items: center; gap: 12px; font-size: 0.95rem;">
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
                <div class="directory-secondary-level" style="max-height: none; display: flex; flex-direction: column; gap: 6px; overflow-y: auto;">
                    ${(this.chapters[this.activeCharaName] || []).map(s => {
                        const displayTitle = s.episodeLabel ? `${s.episodeLabel} ${s.title}` : s.title;
                        return this.getStoryItemHtml(s, "個人故事", displayTitle);
                    }).join('')}
                </div>
            `;
        } else {
            let primaryCardsHtml = "";
            chapterKeys.forEach((chKey, chIndex) => {
                const isSelected = this.expandedChapter === chKey;
                const childStories = this.chapters[chKey] || [];
                const safeId = `dir-group-${chIndex}`;

                let chTitle = "";
                let chIcon = isSelected ? '📂' : '📁';

                if (this.activeTabType === 'main') {
                    let cleanChKey = chKey;
                    const firstStory = childStories[0];
                    const groupId = firstStory ? firstStory.groupId : null;
                    const info = firstStory ? ChapterDataService.getChapterInfo(this.currentPart, groupId) : null;
                    chTitle = info?.title ? ` - ${info.title}` : "";

                    // 取得章節縮圖 (優先使用官方資料庫 storyEnd === 1 指定之高潮/代表話數縮圖，若無則回退首話)
                    const endStory = childStories ? childStories.find(s => s.storyEnd === 1) : null;
                    let foundStoryId = endStory ? endStory.id : ((childStories && childStories.length > 0) ? childStories[0].id : null);
                    let foundStillId = null;
                    let foundBgId = null;

                    if (groupId && this.storyThumbnails && this.storyThumbnails[groupId]) {
                        const thumb = this.storyThumbnails[groupId];
                        foundStillId = thumb.still_id;
                        foundBgId = thumb.bg_id;
                    }

                    if (!foundStillId && !foundBgId && this.storyThumbnails && childStories) {
                        const targetStories = endStory ? [endStory, ...childStories.filter(s => s.id !== endStory.id)] : childStories;
                        for (const s of targetStories) {
                            const thumb = this.storyThumbnails[s.id];
                            if (thumb) {
                                if (thumb.still_id) {
                                    foundStillId = thumb.still_id;
                                    break;
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

                    primaryCardsHtml += `
                        <div class="directory-group-card ${isSelected ? 'active' : ''}" id="${safeId}" onclick="QuestMapModule.selectDirectoryGroup('${this.escapeForAttr(chKey)}')">
                            <div class="chapter-card-thumb">
                                ${chapterCardThumbHtml}
                            </div>
                            <div class="dir-group-info">
                                <div class="dir-group-name">${this.escapeHtml(cleanChKey)}${this.escapeHtml(chTitle)}</div>
                                <div class="dir-group-count">${childStories.length} 話</div>
                            </div>
                        </div>
                    `;
                } else if (this.activeTabType === 'event') {
                    let foundStoryId = (childStories && childStories.length > 0) ? childStories[0].id : null;
                    let foundStillId = null;
                    let foundBgId = null;
                    let eventTopId = null;

                    if (childStories && childStories.length > 0) {
                        const firstStory = childStories[0];
                        if (firstStory.id && String(firstStory.id).length >= 7) {
                            eventTopId = String(firstStory.id).slice(0, 4);
                        } else if (firstStory.groupId) {
                            eventTopId = String(firstStory.groupId);
                        }

                        for (const s of childStories) {
                            if (s.still_id) { foundStillId = s.still_id; break; }
                            if (!foundBgId && s.bg_id) foundBgId = s.bg_id;
                        }
                    }

                    const chapterCardThumbHtml = StoryAssetService.getEventTopThumbnailHtml(
                        eventTopId,
                        foundStoryId,
                        foundStillId,
                        foundBgId,
                        'chapter-card-img',
                        ''
                    );

                    primaryCardsHtml += `
                        <div class="directory-group-card ${isSelected ? 'active' : ''}" id="${safeId}" onclick="QuestMapModule.selectDirectoryGroup('${this.escapeForAttr(chKey)}')">
                            <div class="chapter-card-thumb">
                                ${chapterCardThumbHtml}
                            </div>
                            <div class="dir-group-info">
                                <div class="dir-group-name">${this.escapeHtml(this.normalizeDisplayTitle(chKey))}</div>
                                <div class="dir-group-count">${childStories.length} 話</div>
                            </div>
                        </div>
                    `;
                } else if (this.activeTabType === 'guild') {
                    let foundStoryId = (childStories && childStories.length > 0) ? childStories[0].id : null;
                    let foundStillId = null;
                    let foundBgId = null;
                    let guildId = null;

                    if (childStories && childStories.length > 0) {
                        const firstStory = childStories[0];
                        guildId = firstStory.groupId || (firstStory.id ? String(firstStory.id).slice(0, 4) : null);
                        for (const s of childStories) {
                            if (s.still_id) { foundStillId = s.still_id; break; }
                            if (!foundBgId && s.bg_id) foundBgId = s.bg_id;
                        }
                    }

                    const chapterCardThumbHtml = StoryAssetService.getGuildTopThumbnailHtml(
                        guildId,
                        foundStoryId,
                        foundStillId,
                        foundBgId,
                        'chapter-card-img',
                        ''
                    );

                    primaryCardsHtml += `
                        <div class="directory-group-card ${isSelected ? 'active' : ''}" id="${safeId}" onclick="QuestMapModule.selectDirectoryGroup('${this.escapeForAttr(chKey)}')">
                            <div class="chapter-card-thumb">
                                ${chapterCardThumbHtml}
                            </div>
                            <div class="dir-group-info">
                                <div class="dir-group-name">${this.escapeHtml(this.normalizeDisplayTitle(chKey))}</div>
                                <div class="dir-group-count">${childStories.length} 話</div>
                            </div>
                        </div>
                    `;
                } else if (this.activeTabType === 'extra') {
                    let foundStoryId = (childStories && childStories.length > 0) ? childStories[0].id : null;
                    let foundStillId = null;
                    let foundBgId = null;
                    let chapterCardThumbHtml = "";

                    if (childStories && childStories.length > 0) {
                        for (const s of childStories) {
                            if (s.still_id) { foundStillId = s.still_id; break; }
                            if (!foundBgId && s.bg_id) foundBgId = s.bg_id;
                        }
                    }

                    const currentCategory = this.getExtraCategory(this.activeExtraCategory);
                    const thumbDesc = this.resolveExtraDirectoryThumbnail(currentCategory, chKey, childStories);

                    if (thumbDesc) {
                        if (thumbDesc.kind === 'tower_top') {
                            chapterCardThumbHtml = StoryAssetService.getTowerTopThumbnailHtml(
                                thumbDesc.id,
                                foundStoryId,
                                foundStillId,
                                foundBgId,
                                'chapter-card-img',
                                ''
                            );
                        } else if (thumbDesc.kind === 'exstory_top') {
                            chapterCardThumbHtml = StoryAssetService.getExStoryTopThumbnailHtml(
                                thumbDesc.id,
                                foundStoryId,
                                foundStillId,
                                foundBgId,
                                'chapter-card-img',
                                ''
                            );
                        } else if (thumbDesc.kind === 'story') {
                            chapterCardThumbHtml = StoryAssetService.getStoryThumbnailHtml(
                                thumbDesc.id,
                                foundStillId,
                                foundBgId,
                                'chapter-card-img',
                                ''
                            );
                        }
                    }

                    if (chapterCardThumbHtml) {
                        primaryCardsHtml += `
                            <div class="directory-group-card ${isSelected ? 'active' : ''}" id="${safeId}" onclick="QuestMapModule.selectDirectoryGroup('${this.escapeForAttr(chKey)}')">
                                <div class="chapter-card-thumb">
                                    ${chapterCardThumbHtml}
                                </div>
                                <div class="dir-group-info">
                                    <div class="dir-group-name">${this.escapeHtml(this.normalizeDisplayTitle(chKey))}</div>
                                    <div class="dir-group-count">${childStories.length} 話</div>
                                </div>
                            </div>
                        `;
                    } else {
                        primaryCardsHtml += `
                            <div class="directory-group-card ${isSelected ? 'active' : ''}" id="${safeId}" onclick="QuestMapModule.selectDirectoryGroup('${this.escapeForAttr(chKey)}')">
                                <div class="dir-group-icon">🌙</div>
                                <div class="dir-group-info">
                                    <div class="dir-group-name">${this.escapeHtml(this.normalizeDisplayTitle(chKey))}</div>
                                    <div class="dir-group-count">${childStories.length} 話</div>
                                </div>
                            </div>
                        `;
                    }
                } else {
                    chIcon = "🌙";
                    primaryCardsHtml += `
                        <div class="directory-group-card ${isSelected ? 'active' : ''}" id="${safeId}" onclick="QuestMapModule.selectDirectoryGroup('${this.escapeForAttr(chKey)}')">
                            <div class="dir-group-icon">${chIcon}</div>
                            <div class="dir-group-info">
                                <div class="dir-group-name">${this.escapeHtml(this.normalizeDisplayTitle(chKey))}</div>
                                <div class="dir-group-count">${childStories.length} 話</div>
                            </div>
                        </div>
                    `;
                }
            });

            const selectedGroupStories = this.chapters[this.expandedChapter] || [];
            let currentGroupDisplayTitle = this.expandedChapter || "";
            if (this.activeTabType === 'main' && selectedGroupStories.length > 0) {
                const firstStory = selectedGroupStories[0];
                const groupId = firstStory ? firstStory.groupId : null;
                const info = firstStory ? ChapterDataService.getChapterInfo(this.currentPart, groupId) : null;
                const chTitle = info?.title ? ` - ${info.title}` : "";
                currentGroupDisplayTitle = `${this.expandedChapter}${chTitle}`;
            }

            const secondaryStoriesHtml = this.renderDirectorySecondaryHtml(this.expandedChapter);

            const isL1 = (this.directoryLevel === 'level1');
            const backBtnText = this.activeTabType === 'event' ? '⬅ 返回活動列表' : (this.activeTabType === 'extra' ? '⬅ 返回系列列表' : '⬅ 返回章節列表');

            controlPanelHtml = `
                <div class="directory-container">
                    <div class="directory-view-level1" id="directory-primary-list" style="display: ${isL1 ? 'flex' : 'none'};">
                        ${primaryCardsHtml}
                    </div>
                    <div class="directory-view-level2" id="directory-secondary-view" style="display: ${isL1 ? 'none' : 'flex'};">
                        <div class="directory-drilldown-header">
                            <button class="directory-back-btn" onclick="QuestMapModule.backToLevel1()">
                                ${backBtnText}
                            </button>
                            <div class="directory-group-badge-box">
                                <span class="directory-secondary-title" id="directory-secondary-title" title="${this.escapeHtml(this.normalizeDisplayTitle(currentGroupDisplayTitle))}">${this.escapeHtml(this.normalizeDisplayTitle(currentGroupDisplayTitle))}</span>
                                <span class="directory-secondary-count" id="directory-secondary-count">${selectedGroupStories.length} 話</span>
                            </div>
                        </div>
                        <div class="directory-secondary-level" id="directory-secondary-list">
                            ${secondaryStoriesHtml}
                        </div>
                    </div>
                </div>
            `;
        }

        const isCharaActive = (this.activeTabType === 'chara' && this.activeCharaName);
        const isExtraCategoryActive = (this.activeTabType === 'extra' && this.activeExtraCategory);
        const currentExtraCategory = isExtraCategoryActive ? this.getExtraCategory(this.activeExtraCategory) : null;

        let breadcrumbHtml = "";
        if (isCharaActive) {
            breadcrumbHtml = `
                <span class="breadcrumb-item linkable" onclick="QuestMapModule.clearActiveChara()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;">👤 角色</span>
                <span class="breadcrumb-separator" style="color: rgba(255,255,255,0.3);">/</span>
                <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">👤 ${this.escapeHtml(this.activeCharaName)}</span>
            `;
        } else if (isExtraCategoryActive && currentExtraCategory) {
            breadcrumbHtml = `
                <span class="breadcrumb-item linkable" onclick="QuestMapModule.clearActiveExtraCategory()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;">🌙 額外劇情</span>
                <span class="breadcrumb-separator" style="color: rgba(255,255,255,0.3);">/</span>
                <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">📖 ${this.escapeHtml(currentExtraCategory.title)}</span>
            `;
        } else {
            breadcrumbHtml = `
                <span class="breadcrumb-current" style="color: var(--text-primary); font-weight: 500;">${
                    this.activeTabType === 'main' ? '⚔️ 主線劇情' :
                    this.activeTabType === 'event' ? '🏆 活動' :
                    this.activeTabType === 'guild' ? '👥 公會' :
                    this.activeTabType === 'chara' ? '👤 角色' :
                    this.activeTabType === 'tower' ? '🌙 額外' :
                    this.activeTabType === 'extra' ? '🌙 額外' : '👥 登場角色'
                }</span>
            `;
        }

        tab.innerHTML = `
            <div class="map-container">
                <div class="breadcrumb-container" style="display: flex; align-items: center; gap: 12px; font-size: 0.95rem;">
                    <span class="breadcrumb-item linkable" onclick="QuestMapModule.goBackToMenu()" style="color: var(--accent-color); cursor: pointer; display: flex; align-items: center; gap: 4px; font-weight: bold; transition: opacity 0.2s;"><span style="font-size: 1.1rem;">🏠</span> 劇情大廳</span>
                    <span class="breadcrumb-separator" style="color: rgba(255,255,255,0.3);">/</span>
                    ${breadcrumbHtml}
                </div>
            <div class="story-navigation-header">
                ${(this.activeTabType === 'main' || this.activeTabType === 'event') ? `
                <div class="primary-nav-group" style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <button class="primary-nav-btn ${this.activeTabType === 'main' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('main')">⚔️ 主線劇情</button>
                    <button class="primary-nav-btn ${this.activeTabType === 'event' ? 'active' : ''}" onclick="QuestMapModule.switchTabType('event')">🏆 活動劇情</button>
                </div>
                ` : `
                <div class="other-category-title" style="display: flex; align-items: center; gap: 8px;">
                    <h2 style="margin: 0; font-size: 1.3rem; color: var(--text-primary);">📖 ${
                        this.activeTabType === 'guild' ? '公會劇情' :
                        this.activeTabType === 'chara' ? `${this.activeCharaName ? this.escapeHtml(this.activeCharaName) + ' 的' : ''}角色劇情` :
                        this.activeTabType === 'extra' ? `${currentExtraCategory ? this.escapeHtml(currentExtraCategory.title) : '額外劇情'}` :
                        this.activeTabType === 'tower' ? '額外劇情' : '登場角色'
                    }</h2>
                </div>
                `}

                <div class="part-selector secondary-nav-group" style="display: ${this.activeTabType === 'main' ? 'flex' : 'none'};">
                    <button class="part-btn secondary-pill ${this.currentPart === 1 ? 'active' : ''}" onclick="QuestMapModule.switchPart(1)">第一部</button>
                    <button class="part-btn secondary-pill ${this.currentPart === 2 ? 'active' : ''}" onclick="QuestMapModule.switchPart(2)">第二部</button>
                    <button class="part-btn secondary-pill ${this.currentPart === 3 ? 'active' : ''}" onclick="QuestMapModule.switchPart(3)">第三部</button>
                </div>
            </div>

            <div class="map-layout">
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
                            <div class="summary-section" style="flex: 1; display: flex; flex-direction: column; margin-top: 15px;">
                                <div class="summary-tabs" style="display: flex; margin-bottom: 6px; gap: 8px;">
                                    <div style="font-weight: 700; font-size: 0.92rem; color: var(--text-primary); display: flex; align-items: center; gap: 6px; padding: 4px 0;">
                                        <span>📌 故事大綱</span>
                                    </div>
                                </div>
                                <div id="cinema-summary" class="summary-text" style="flex: 1; display: flex; flex-direction: column;">
                                    點擊右側章節清單，即刻載入大綱與對白文本。
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="map-control-panel">
                    <div class="panel-section-title">
                        📖 ${
                            this.activeTabType === 'main' ? '章節與話數' : 
                            this.activeTabType === 'event' ? '活動與話數' :
                            this.activeTabType === 'guild' ? '公會劇情目錄' :
                            this.activeTabType === 'chara' ? `${this.activeCharaName} 的個人劇情目錄` :
                            this.activeTabType === 'extra' ? `${currentExtraCategory ? this.escapeHtml(currentExtraCategory.title) + ' 目錄' : '額外劇情目錄'}` :
                            this.activeTabType === 'tower' ? '露娜塔/系統劇情目錄' : '目錄'
                        }
                    </div>
                    <div class="directory-shell" style="flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden;">
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
        return this.safeRender(() => this._render(skipAutoSelect));
    },

    switchPart(part) {
        this.teardownPlayback({ invalidateAsync: true });
        window.ReaderNavigation?.left();
        this.currentPart = part;
        this.activeStoryId = null;
        this.expandedChapter = null;
        this.directoryLevel = 'level1';
        this.directoryLevel1ScrollTop = 0;

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

    /**
     * 解析活動各話副標題 (Episode Subtitle)
     * 依據單一優先級解析：
     * 1. official metadata.subtitle (非空且 meaningful)
     * 2. story.title (DB event_story_detail.sub_title / extra_events.title，非空且 meaningful)
     * 3. 兩者皆非 meaningful 則返回空字串 (不捏造假標題)
     * @param {Object} story - 話數物件
     * @param {string} chapterLabel - 章節標籤 (如 "第1話")
     * @returns {string} 各話副標題
     */
    resolveEventEpisodeSubtitle(story, chapterLabel) {
        if (!story) return "";

        const normalizeKey = (str) => {
            if (!str) return "";
            return String(str).replace(/[\s\u3000]+/g, "").trim();
        };

        const isMeaningful = (subtitle, label) => {
            if (!subtitle || typeof subtitle !== 'string') return false;
            const cleanSub = subtitle.trim();
            if (!cleanSub) return false;
            const subNorm = normalizeKey(cleanSub);
            const labelNorm = normalizeKey(label);
            if (subNorm && labelNorm && subNorm === labelNorm) return false;
            if (/^第\d+話$/.test(subNorm) || subNorm === "序幕" || subNorm === "終幕") return false;
            return true;
        };

        // 1. 優先從 StoryDataService 快取取得官方 metadata subtitle
        if (window.StoryDataService && typeof window.StoryDataService.getSubtitleSync === 'function') {
            const officialSub = window.StoryDataService.getSubtitleSync(story.id);
            if (officialSub && isMeaningful(officialSub, chapterLabel)) {
                return officialSub.trim();
            }
        }

        // 2. 次選 story.title (來自 DB event_story_detail 或 extra_events)
        if (story.title && isMeaningful(story.title, chapterLabel)) {
            return story.title.trim();
        }

        // 3. 兩者皆無 meaningful 副標題，回傳空字串
        return "";
    },

    renderDirectorySecondaryHtml(chKey) {
        if (!this.chapters || !chKey || !this.chapters[chKey]) {
            return `<div style="padding: 20px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">暫無話數</div>`;
        }
        const childStories = this.chapters[chKey] || [];
        return childStories.map(s => {
            let displayChapterName = "";
            let episodeSubtitle = s.title;
            if (this.activeTabType === 'main') {
                displayChapterName = s.chapter.replace(/^(第\d+部\s*)?([^\s]+章\s*|[^\s]+序章\s*|[^\s]+幕間[^\s]*\s*)/, '');
                if (!displayChapterName) displayChapterName = s.chapter;
            } else if (this.activeTabType === 'event') {
                const cleanEventTitle = chKey.substring(chKey.indexOf('』') + 1 || chKey.indexOf('】') + 1 || chKey.indexOf('」') + 1).trim();
                displayChapterName = s.chapter.replace(cleanEventTitle, '').trim();
                if (!displayChapterName) displayChapterName = s.chapter;
                episodeSubtitle = this.resolveEventEpisodeSubtitle(s, displayChapterName);
            } else if (this.activeTabType === 'guild') {
                const match = s.chapter ? s.chapter.match(/第\d+話/) : null;
                displayChapterName = match ? match[0] : (s.chapter || "公會故事");
            } else {
                displayChapterName = s.chapter || "特別故事";
            }
            return this.getStoryItemHtml(s, displayChapterName, episodeSubtitle);
        }).join('');
    },

    selectDirectoryGroup(chKey) {
        if (!this.chapters || !this.chapters[chKey]) return;

        // 1. 記錄 Level 1 目前滾動位置
        const l1 = document.getElementById('directory-primary-list');
        if (l1) {
            this.directoryLevel1ScrollTop = l1.scrollTop;
        }

        this.expandedChapter = chKey;
        this.directoryLevel = 'level2';

        // 2. 更新 Level 2 的內容 (標題、話數列表)
        this.updateDirectoryUI(chKey);

        // 3. 原地切換 view
        const v1 = document.getElementById('directory-primary-list');
        const v2 = document.getElementById('directory-secondary-view');
        if (v1 && v2) {
            v1.style.display = 'none';
            v2.style.display = 'flex';
        }
        const l2 = document.getElementById('directory-secondary-list');
        if (l2) l2.scrollTop = 0;

        // 絕對不切換 Reader、不載入話數、不滾動 Reader、不跳視窗
    },

    backToLevel1() {
        this.directoryLevel = 'level1';
        const v1 = document.getElementById('directory-primary-list');
        const v2 = document.getElementById('directory-secondary-view');
        if (v1 && v2) {
            v2.style.display = 'none';
            v1.style.display = 'flex';
            if (typeof this.directoryLevel1ScrollTop === 'number') {
                v1.scrollTop = this.directoryLevel1ScrollTop;
            }
        }
        // 同步第一層 active 樣式 (高亮當前話數所屬章節)
        if (this.activeStoryId) {
            const activeChKey = this.getChapterKeyForStory(this.activeStoryId);
            if (activeChKey) {
                const chapterKeys = Object.keys(this.chapters);
                chapterKeys.forEach((key, idx) => {
                    const card = document.getElementById(`dir-group-${idx}`);
                    if (card) {
                        if (key === activeChKey) card.classList.add('active');
                        else card.classList.remove('active');
                    }
                });
            }
        }
        // 絕對不切換 Reader、不影響視窗滾動
    },

    updateDirectoryUI(targetChKey) {
        const chKey = targetChKey || this.expandedChapter;
        if (!chKey || !this.chapters) return;

        // 1. 同步第一層卡片 active 樣式並確保可見
        const chapterKeys = Object.keys(this.chapters);
        chapterKeys.forEach((key, idx) => {
            const card = document.getElementById(`dir-group-${idx}`);
            if (card) {
                if (key === chKey) {
                    card.classList.add('active');
                    card.scrollIntoView({ block: 'nearest', behavior: 'auto' });
                } else {
                    card.classList.remove('active');
                }
            }
        });

        // 2. 同步第二層標題與計數
        const childStories = this.chapters[chKey] || [];
        const titleEl = document.getElementById('directory-secondary-title');
        const countEl = document.getElementById('directory-secondary-count');
        const listEl = document.getElementById('directory-secondary-list');

        if (titleEl) {
            let currentGroupDisplayTitle = chKey;
            if (this.activeTabType === 'main' && childStories.length > 0) {
                const firstStory = childStories[0];
                const groupId = firstStory ? firstStory.groupId : null;
                const info = firstStory ? ChapterDataService.getChapterInfo(this.currentPart, groupId) : null;
                const chTitle = info?.title ? ` - ${info.title}` : "";
                currentGroupDisplayTitle = `${chKey}${chTitle}`;
            }
            const cleanTitle = this.normalizeDisplayTitle(currentGroupDisplayTitle);
            titleEl.innerText = cleanTitle;
            titleEl.title = cleanTitle;
        }

        if (countEl) {
            countEl.innerText = `${childStories.length} 話`;
        }

        if (listEl) {
            listEl.innerHTML = this.renderDirectorySecondaryHtml(chKey);
            if (this.activeStoryId) {
                this.syncSecondLevelActiveStory(this.activeStoryId);
            }
        }
    },

    getChapterKeyForStory(storyId) {
        if (!this.chapters) return null;
        for (const [chKey, stories] of Object.entries(this.chapters)) {
            if (Array.isArray(stories) && stories.some(s => s.id === storyId)) {
                return chKey;
            }
        }
        return null;
    },

    getAllActiveTabStories() {
        if (!this.chapters) return [];
        // Keep reader prev/next within one Anniversary series; the official
        // UI treats each of the ten series as an independent replay list.
        if (this.activeTabType === 'extra' && this.activeExtraCategory === 'anniversary_countdown'
            && this.expandedChapter && Array.isArray(this.chapters[this.expandedChapter])) {
            return [...this.chapters[this.expandedChapter]];
        }
        const all = [];
        for (const chKey of Object.keys(this.chapters)) {
            const list = this.chapters[chKey];
            if (Array.isArray(list)) {
                for (const s of list) {
                    all.push(s);
                }
            }
        }
        return all;
    },

    syncSecondLevelActiveStory(storyId) {
        document.querySelectorAll('.story-item').forEach(el => el.classList.remove('active'));
        const activeItem = document.getElementById(`story-item-${storyId}`);
        if (activeItem) {
            activeItem.classList.add('active');
            activeItem.scrollIntoView({ block: 'nearest', behavior: 'auto' });
        }
    },

    toggleChapter(chIndex) {
        const chapterKeys = Object.keys(this.chapters);
        const chKey = chapterKeys[chIndex];
        if (chKey) this.selectDirectoryGroup(chKey);
    },

    getStoryById(storyId) {
        return this.stories.find(s => s.id === storyId) || this.eventStories.find(s => s.id === storyId);
    },

    async selectStory(storyId) {
        // Same-story re-selection is a strict no-op: keep AUTO/manual playback
        // and the current scroll position intact.
        if (this.activeStoryId === storyId) {
            return;
        }
        this._stopStoryPlayback();
        if (!this.getStoryById(storyId)) return;
        window.ReaderNavigation?.beforeSelect();
        this.activeStoryId = storyId;
        // A failed new request must never leave the preceding story playable.
        this.currentDialogueList = [];
        this.autoVoiceStartIndex = null;
        const currentBoard = document.getElementById('dialogue-board');
        if (currentBoard && window.DialogueView) {
            window.DialogueView.clearAutoStartSelection(currentBoard);
            window.DialogueView.clearDialogueHighlight(currentBoard);
        }

        // 雙向狀態同步：若該話屬於另一個 group (例如上一話/下一話跨章節)
        const targetChKey = this.getChapterKeyForStory(storyId);
        if (targetChKey && targetChKey !== this.expandedChapter) {
            this.expandedChapter = targetChKey;
            this.updateDirectoryUI(targetChKey);
        }
        this.syncSecondLevelActiveStory(storyId);

        this._storyRenderToken = (this._storyRenderToken || 0) + 1;
        const currentToken = this._storyRenderToken;

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
            } else if (this.activeTabType === 'tower' || this.activeTabType === 'extra') {
                chTag.innerText = "其他";
            } else {
                const match = story.chapter.match(/^(第\d+部\s*)?([^\s]+)/);
                chTag.innerText = match ? match[2] : "主線";
            }
            titleEl.innerText = this.normalizeDisplayTitle(story.title || "話標題");
        }

        // 1. 同步建立 shell 與對白容器 (零阻塞)
        this.updateSummaryContent(currentToken);

        // 2. 立即啟動對白文本載入 (不等待任何 metadata 非同步請求)
        if (this.isDialogueExpanded) {
            this.loadDialogue(storyId, currentToken);
        }
        this.updateNavigationButtons();
        this.updateReaderState();

        // 3. 話數切換後回到頁面最頂部 (避免停留在上一話底部或 Reader 區域，使頂部導航完整可見)
        window.ReaderNavigation?.selected(storyId);
        setTimeout(() => {
            if (this.activeStoryId === storyId && this._storyRenderToken === currentToken) {
                window.scrollTo({ top: 0, behavior: 'auto' });
            }
        }, 0);
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
        const allStories = this.getAllActiveTabStories();
        const index = allStories.findIndex(s => s.id === this.activeStoryId);
        return index > 0 ? allStories[index - 1].id : null;
    },

    getNextStoryId() {
        const allStories = this.getAllActiveTabStories();
        const index = allStories.findIndex(s => s.id === this.activeStoryId);
        return (index !== -1 && index < allStories.length - 1) ? allStories[index + 1].id : null;
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
        this.teardownPlayback({ invalidateAsync: true });
        window.ReaderNavigation?.left();
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
            } else if (this.activeTabType === 'extra' && this.activeExtraCategory) {
                this.clearActiveExtraCategory();
            } else {
                this.goBackToMenu();
            }
        }
    },

    scrollReaderToTop(behavior = 'auto') {
        const target = document.querySelector('.cinema-panel') || document.querySelector('.map-visual-area');
        if (target) {
            const navOffset = 80; // 64px global navbar + 16px spacing
            const targetY = Math.max(0, Math.round(target.getBoundingClientRect().top + window.scrollY - navOffset));
            if (behavior === 'smooth') {
                const startY = window.scrollY;
                const diff = targetY - startY;
                if (Math.abs(diff) < 2) {
                    window.scrollTo({ top: targetY, behavior: 'auto' });
                    return;
                }
                const duration = 240;
                const startTime = performance.now();
                const step = () => {
                    const elapsed = performance.now() - startTime;
                    const progress = Math.min(elapsed / duration, 1);
                    const ease = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;
                    window.scrollTo(0, Math.round(startY + diff * ease));
                    if (progress < 1) {
                        setTimeout(step, 16);
                    } else {
                        window.scrollTo(0, targetY);
                    }
                };
                setTimeout(step, 16);
            } else {
                window.scrollTo({ top: targetY, behavior: 'auto' });
            }
        }
    },

    scrollToTop() {
        this.scrollReaderToTop('smooth');
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
        // 安全門禁：暫時隱藏 Legacy AI Summary，禁止非行動端進入 chapter/ai-summary
        const isMobile = window.innerWidth <= 768;
        if (tabType === 'ai-summary' || (!isMobile && tabType === 'chapter')) {
            tabType = 'episode';
        }
        this.activeSummaryTab = tabType;
        this.updateSummaryTabsUI();
        this.updateSummaryContent();
    },

    updateSummaryTabsUI() {
        const isMobile = window.innerWidth <= 768;
        const tabsContainer = document.querySelector('.summary-tabs');
        if (!tabsContainer) return;

        if (!isMobile) {
            // 桌機版：乾淨靜態大綱標題，無 fake tab 與底線點擊提示
            tabsContainer.style.borderBottom = 'none';
            tabsContainer.style.marginBottom = '6px';
            tabsContainer.innerHTML = `
                <div style="font-weight: 700; font-size: 0.92rem; color: var(--text-primary); display: flex; align-items: center; gap: 6px; padding: 4px 0;">
                    <span>📌 故事大綱</span>
                </div>
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

    updateSummaryContent(token) {
        const summaryEl = document.getElementById('cinema-summary');
        if (!summaryEl || !this.activeStoryId) return;

        const story = this.getStoryById(this.activeStoryId);
        if (!story) return;

        const currentStoryId = this.activeStoryId;
        const currentToken = token || this._storyRenderToken;
        const isMobile = window.innerWidth <= 768;

        // 安全防護：若處於 hidden tab 狀態，強制回退至 'episode'
        if (this.activeSummaryTab === 'ai-summary' || (!isMobile && this.activeSummaryTab === 'chapter')) {
            this.activeSummaryTab = 'episode';
        }

        if (this.activeSummaryTab === 'episode' || isMobile) {
            try {
                let topDirOrSummaryHtml = "";
                if (isMobile) {
                    topDirOrSummaryHtml = this.getQuickDirectoryHtml() + `
                        <details class="mobile-official-synopsis" ontoggle="if(this.open) QuestMapModule.refreshOfficialSynopsis(${currentStoryId}, ${currentToken})">
                            <summary>📌 官方大綱（點擊展開）</summary>
                            <p id="official-synopsis-content" aria-live="polite">正在載入官方大綱…</p>
                        </details>`;
                } else {
                    topDirOrSummaryHtml = `
                        <div id="official-synopsis-box" style="
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
                            <p id="official-synopsis-content" style="margin:0; color: var(--text-secondary); font-size: 0.88rem;">正在載入官方大綱…</p>
                        </div>
                    `;
                }

                summaryEl.innerHTML = `
                    <div style="display: flex; flex-direction: column; gap: 14px; text-align: left;">
                        ${topDirOrSummaryHtml}

                        <div class="dialogue-section">
                            <div class="game-dialogue-panel">
                                <div class="game-dialogue-header" style="border-radius: 12px 12px 0 0; display: flex; align-items: center; justify-content: space-between; padding: 10px 16px;">
                                    <div style="font-weight: 700;">✦ 劇情全文 ✦</div>
                                    <div class="auto-voice-control-bar" role="toolbar" aria-label="語音連播控制列">
                                        <span class="auto-voice-label">AUTO</span>
                                        <button id="btn-auto-voice" class="auto-voice-play-toggle" type="button" onclick="QuestMapModule.toggleAutoVoice()" aria-label="開始 AUTO" title="播放 / 暫停 (Space)">
                                            <span class="auto-voice-icon">▶</span>
                                        </button>
                                        <button id="btn-stop-voice" class="auto-voice-stop" type="button" onclick="QuestMapModule.stopAutoVoice()" aria-label="停止 AUTO" title="停止連播 (Esc)" disabled>
                                            <span class="auto-voice-icon">■</span>
                                        </button>
                                    </div>
                                </div>
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
                                    <button type="button" id="btn-prev-story" class="game-footer-btn close" style="display: none;" onclick="QuestMapModule.toPrevStory()">⬅ 上一話</button>
                                    <button type="button" class="game-footer-btn close" onclick="QuestMapModule.scrollToTop()">⬆ 回到頂端</button>
                                    <button type="button" id="btn-next-story" class="game-footer-btn skip" style="display: none;" onclick="QuestMapModule.toNextStory()">➡️ 下一話</button>
                                </div>
                            </div>
                        </div>

                    </div>
                `;
                this.updateSummaryTabsUI();

                // 桌機版非同步載入官方大綱 (完全不阻塞對白文本載入)
                if (!isMobile) {
                    this.refreshOfficialSynopsis(currentStoryId, currentToken);
                }
            } catch (e) {
                console.error(e);
                summaryEl.innerHTML = `<div style="color: #ff6b6b;">無法載入大綱與劇情視圖。</div>`;
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

    async refreshOfficialSynopsis(storyId, token) {
        let officialSynopsis = null;
        if (window.StoryDataService) {
            try {
                officialSynopsis = await window.StoryDataService.getOfficialSynopsis(storyId);
            } catch (err) {
                console.warn('[QuestMapModule] 取得官方大綱失敗:', err);
            }
        }

        // Stale Story Race Guard: 若使用者已切換至其他話數，忽略此延遲回傳之大綱
        if (token !== this._storyRenderToken || this.activeStoryId !== storyId) {
            return;
        }

        const synopsisEl = document.getElementById('official-synopsis-content');
        if (!synopsisEl) return;

        if (officialSynopsis && typeof officialSynopsis === 'string' && officialSynopsis.trim()) {
            const rawText = officialSynopsis.trim();
            const normalizedSynopsis = (window.DialogueView && typeof window.DialogueView.normalizePlayerName === 'function')
                ? window.DialogueView.normalizePlayerName(rawText)
                : rawText.replace(/\{player\}|\{0\}|\{player_name\}|\([Oo]\)|（[Oo]）/g, "佑樹");
            synopsisEl.textContent = normalizedSynopsis;
            synopsisEl.style.color = 'var(--text-primary)';
            synopsisEl.style.lineHeight = '1.7';
            synopsisEl.style.fontSize = '0.9rem';
        } else {
            synopsisEl.textContent = '本話暫無官方大綱';
            synopsisEl.style.color = 'var(--text-secondary)';
            synopsisEl.style.fontSize = '0.88rem';
        }
    },

    async loadDialogue(storyId, token) {
        const currentToken = token || this._storyRenderToken;
        const isCurrentStory = () => (
            currentToken === this._storyRenderToken &&
            this.activeStoryId === storyId
        );

        if (!isCurrentStory()) return;

        const initialBoard = document.getElementById('dialogue-board');
        if (!initialBoard) return;
        if (this._dialogueLoadingToken === currentToken) return;

        this._dialogueLoadingToken = currentToken;
        this.isLoadingDialogue = true;
        window.DialogueView.renderLoading(initialBoard);

        try {
            let dialogueList;
            let speakerNames;
            const cached = this._dialogueCache.get(storyId);

            if (cached) {
                dialogueList = cached.dialogueList;
                speakerNames = cached.speakerNames;
            } else {
                const ver = window.PCRD_DATA_VERSION || (window.PCRDatabase && window.PCRDatabase.dbVersion) || 'dev';
                const response = await fetch(`story/${storyId}.json?v=${ver}`);
                if (!response.ok) throw new Error("HTTP " + response.status);

                const rawDialogueList = await response.json();
                if (!isCurrentStory()) return;

                if (!rawDialogueList || rawDialogueList.length === 0) {
                    const liveBoard = document.getElementById('dialogue-board');
                    if (liveBoard && isCurrentStory()) {
                        window.DialogueView.renderEmpty(liveBoard);
                    }
                    return;
                }

                const normalized = window.DialogueNormalizer.normalize(rawDialogueList);
                dialogueList = normalized.dialogueList;
                speakerNames = normalized.speakerNames;

                if (this._dialogueCache.size >= 30) {
                    const oldestKey = this._dialogueCache.keys().next().value;
                    this._dialogueCache.delete(oldestKey);
                }
                this._dialogueCache.set(storyId, { dialogueList, speakerNames });
            }

            await this.loadDialogueAvatars(speakerNames);
            if (!isCurrentStory()) return;

            // Final commit barrier: resolve live DOM targets after the last await,
            // never write into a board captured for an older render.
            const liveBoard = document.getElementById('dialogue-board');
            if (!liveBoard || !isCurrentStory()) return;

            const badgesBar = document.getElementById('chara-badges-bar');
            const cinemaPanel = document.querySelector('.cinema-panel');
            const currentStoryObj = this.getStoryById(storyId);

            window.DialogueView.renderDialogue({
                boardEl: liveBoard,
                badgesBarEl: badgesBar,
                cinemaPanelEl: cinemaPanel,
                storyId,
                dialogueList,
                speakerNames,
                speakerAvatars: this.speakerAvatars,
                currentStoryObj,
                resolveRealName: this.getCharaRealName.bind(this),
                escapeHtml: this.escapeHtml.bind(this)
            });

            if (!isCurrentStory()) return;
            this.currentDialogueList = dialogueList;
            this.updateAutoVoiceUI();
            window.ReaderNavigation?.dialogueReady(storyId);

            if (this.autoVoiceStartIndex !== null && window.DialogueView && typeof window.DialogueView.setAutoStartSelection === 'function') {
                window.DialogueView.setAutoStartSelection(liveBoard, this.autoVoiceStartIndex);
            }
        } catch (err) {
            if (isCurrentStory()) {
                console.error("加載台詞失敗:", err);
                const liveBoard = document.getElementById('dialogue-board');
                if (liveBoard && isCurrentStory()) {
                    window.DialogueView.renderError(liveBoard, storyId);
                }
            }
        } finally {
            if (this._dialogueLoadingToken === currentToken) {
                this._dialogueLoadingToken = null;
                this.isLoadingDialogue = false;
            }
        }
    },

    openStillPopup(event) {
        return window.MediaService.openStillPopup(event);
    },

    closeStillPopup() {
        return window.MediaService.closeStillPopup();
    },

    playVoice(voiceName) {
        if (window.AutoVoiceController && typeof window.AutoVoiceController.onManualVoicePlay === 'function') {
            window.AutoVoiceController.onManualVoicePlay();
        }
        return window.MediaService.playVoice(voiceName);
    },

    /**
     * 處理點擊對白行以選取或取消 AUTO 播放起點
     * @param {number} index - 對白行索引
     * @param {MouseEvent} event - 點擊事件
     */
    handleDialogueLineClick(index, event) {
        // 1. 若非 IDLE 狀態 (PLAYING 或 PAUSED)，忽略起點切換
        if (window.AutoVoiceController && window.AutoVoiceController.state !== 'IDLE') {
            return;
        }

        // 2. 忽略子元素點擊 (語音按鈕、角色頭像、角色名稱連結等)
        if (event) {
            const target = event.target;
            if (target && typeof target.closest === 'function') {
                if (target.closest('.dialogue-voice-btn') || 
                    target.closest('.game-chara-avatar-wrapper') || 
                    target.closest('.game-dialogue-speaker')) {
                    return;
                }
            }
        }

        // 3. 忽略使用者正在反白拖曳選取文字
        const selection = window.getSelection ? window.getSelection() : null;
        if (selection && selection.toString().trim().length > 0) {
            return;
        }

        // 4. Same Line Toggle: 若點擊目前已選取的同一個對話行，取消選取
        const board = document.getElementById('dialogue-board');
        if (this.autoVoiceStartIndex === index) {
            this.autoVoiceStartIndex = null;
            if (window.DialogueView && board) {
                window.DialogueView.clearAutoStartSelection(board);
            }
        } else {
            this.autoVoiceStartIndex = index;
            if (window.DialogueView && board) {
                window.DialogueView.setAutoStartSelection(board, index);
            }
        }
    },

    handleReaderKeydown(event) {
        if (event.defaultPrevented || event.repeat || event.isComposing || event.keyCode === 229 ||
            event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
        if (!this.activeStoryId || this.isLoadingDialogue || !this.currentDialogueList?.length) return;
        const tab = document.getElementById('map-tab');
        if (!tab?.classList.contains('active') || !document.getElementById('dialogue-board')) return;
        const target = event.target;
        if (target?.isContentEditable || target?.closest('input, textarea, select, button, a, summary, [role="button"], [role="textbox"], [contenteditable]:not([contenteditable="false"])')) return;
        // Dialogs own their keys. Escape must close a popup before stopping AUTO.
        if (document.body.style.overflow === 'hidden' || document.querySelector('.modal-overlay.active, [role="dialog"][open], dialog[open]')) return;
        if (event.code === 'Space' || event.key === ' ') {
            event.preventDefault();
            this.toggleAutoVoice();
        } else if (event.key === 'Escape' && window.AutoVoiceController?.isActive()) {
            event.preventDefault();
            this.stopAutoVoice();
        }
    },

    toggleAutoVoice() {
        if (!window.AutoVoiceController) return;

        // 綁定狀態監聽回呼以同步按鈕 UI
        window.AutoVoiceController.onStateChange = (state) => {
            this.updateAutoVoiceUI(state);
        };

        if (window.AutoVoiceController.state === 'IDLE') {
            if (!this.currentDialogueList || this.currentDialogueList.length === 0) {
                console.warn('[QuestMapModule] 尚無載入完成之對白清單');
                return;
            }
            const board = document.getElementById('dialogue-board');
            const startIndex = (typeof this.autoVoiceStartIndex === 'number' && this.autoVoiceStartIndex >= 0)
                ? this.autoVoiceStartIndex
                : 0;
            window.AutoVoiceController.start(this.currentDialogueList, this.activeStoryId, board, startIndex);
        } else if (window.AutoVoiceController.state === 'PLAYING') {
            window.AutoVoiceController.pause();
        } else if (window.AutoVoiceController.state === 'PAUSED') {
            window.AutoVoiceController.resume();
        }
    },

    stopAutoVoice() {
        if (window.AutoVoiceController) {
            window.AutoVoiceController.stop();
        }
    },

    updateAutoVoiceUI(state) {
        const bar = document.querySelector('.auto-voice-control-bar');
        const btnToggle = document.getElementById('btn-auto-voice');
        const btnStop = document.getElementById('btn-stop-voice');
        if (!btnToggle || !btnStop) return;

        const currentState = state || (window.AutoVoiceController ? window.AutoVoiceController.state : 'IDLE');
        const iconEl = btnToggle.querySelector('.auto-voice-icon') || btnToggle;

        if (currentState === 'PLAYING') {
            iconEl.textContent = '⏸';
            btnToggle.setAttribute('aria-label', '暫停 AUTO');
            btnToggle.title = '暫停 (Space)';
            btnToggle.classList.add('is-playing');
            btnToggle.classList.remove('is-paused');
            btnStop.disabled = false;
            btnStop.setAttribute('aria-label', '停止 AUTO');
            if (bar) bar.classList.add('is-playing');
        } else if (currentState === 'PAUSED') {
            iconEl.textContent = '▶';
            btnToggle.setAttribute('aria-label', '繼續 AUTO');
            btnToggle.title = '繼續播放 (Space)';
            btnToggle.classList.remove('is-playing');
            btnToggle.classList.add('is-paused');
            btnStop.disabled = false;
            btnStop.setAttribute('aria-label', '停止 AUTO');
            if (bar) bar.classList.remove('is-playing');
        } else {
            iconEl.textContent = '▶';
            btnToggle.setAttribute('aria-label', '開始 AUTO');
            btnToggle.title = '播放 (Space)';
            btnToggle.classList.remove('is-playing', 'is-paused');
            btnStop.disabled = true;
            btnStop.setAttribute('aria-label', '停止 AUTO (已停止)');
            if (bar) bar.classList.remove('is-playing');
        }

        const board = document.getElementById('dialogue-board');
        if (board) {
            if (currentState === 'PLAYING' || currentState === 'PAUSED') {
                board.classList.add('auto-voice-running');
            } else {
                board.classList.remove('auto-voice-running');
                if (this.autoVoiceStartIndex !== null && window.DialogueView && typeof window.DialogueView.setAutoStartSelection === 'function') {
                    window.DialogueView.setAutoStartSelection(board, this.autoVoiceStartIndex);
                }
            }
        }
    },

    async openMoviePopup(movieId) {
        if (!movieId) return;
        await this.ensureMovieLinks();
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

    async showCharaModal(charaName, unitId = null) {
        const realCharaName = this.getCharaRealName(charaName);
        const numericUnitId = Number(unitId);
        const explicitUnitId = Number.isInteger(numericUnitId) && numericUnitId > 0
            ? numericUnitId
            : null;
        await this.ensureAppearanceMap();

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
            explicitUnitId,
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
        const extraMembership = this.getExtraMembership(story);

        if (extraMembership) {
            // Extra membership 優先導向 Extra 分頁與對應分類 (Phase 3 Part F)
            this.activeTabType = 'extra';
            this.activeExtraCategory = extraMembership.categoryId;
            this.groupExtraStories();
        } else if (isEvent) {
            if (this.activeTabType !== 'event') this.activeTabType = 'event';
            this.groupEventStories();
        } else {
            // 根據 story.type 正確導向對應的分頁
            if (storyType && ['chara', 'guild', 'tower'].includes(storyType)) {
                this.activeTabType = storyType;
            } else {
                this.activeTabType = 'main';
                if (story.part) this.currentPart = story.part;
            }

            if (storyType === 'chara') {
                this.groupCharaStories();
            } else if (storyType === 'guild') {
                this.groupGuildStories();
            } else if (storyType === 'tower') {
                this.groupTowerStories();
            } else {
                this.groupStories();
            }
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
            this.directoryLevel = 'level2';
            if (storyType === 'chara') {
                this.activeCharaName = targetChKey;
            }
        }

        return this.safeRender(async () => {
            await this._render(true);
            // Rebuilding the shell needs a fresh selection even for the same ID.
            this.activeStoryId = null;
            await this.selectStory(storyId);
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

window.QuestMapModule = QuestMapModule;

if (typeof window.addEventListener === 'function') {
    window.addEventListener('pagehide', () => {
        QuestMapModule.teardownPlayback({ invalidateAsync: true });
    });
}
