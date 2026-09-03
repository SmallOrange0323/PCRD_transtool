console.log("chapter-data.js loaded");
/**
 * PCRD Data Hub - 章節資料服務 (ChapterDataService)
 * 載入並提供章節標題、摘要、順序等中繼資料
 * 以及第 3 部分支劇情補充元數據 (branch_stories.json) 的載入與轉換
 * 資料來源：dashboard/data/chapters.json, branch_stories.json
 */

(function() {
    const ChapterDataService = {
        data: null,
        storySummaries: null,
        branchStories: [],
        loaded: false,

        /**
         * 將 branch_stories.json 資料轉換為 Story Map 的統一 story 物件陣列
         * 嚴格執行 Runtime Schema 與契約驗證 (Fail Loudly)
         * @param {Object} branchData - branch_stories.json 的根物件
         * @returns {Array} 統一 story 結構列表
         */
        transformBranchStories(branchData) {
            if (!branchData) return [];
            if (
                typeof branchData !== 'object' ||
                branchData.version !== 1 ||
                branchData.part !== 3 ||
                !Array.isArray(branchData.stories)
            ) {
                throw new Error("[ChapterDataService] branch_stories.json 結構格式不符合預期 (Schema Error)");
            }

            const seenIds = new Set();
            return branchData.stories.map((s, idx) => {
                // 1. story_id 型別與正整數檢查
                if (!Number.isInteger(s.story_id) || s.story_id <= 0) {
                    throw new Error(`[ChapterDataService] 第 ${idx} 筆分支劇情 story_id 必須為正整數: ${s.story_id}`);
                }
                if (seenIds.has(s.story_id)) {
                    throw new Error(`[ChapterDataService] 發現重複的 story_id: ${s.story_id}`);
                }
                seenIds.add(s.story_id);

                // 2. chapter 範圍與整數檢查 (嚴格限定 1 ~ 16)
                if (!Number.isInteger(s.chapter) || s.chapter < 1 || s.chapter > 16) {
                    throw new Error(`[ChapterDataService] 第 ${idx} 筆分支劇情 chapter 必須為 1~16 之整數: ${s.chapter}`);
                }

                // 3. metadata_status 契約檢查
                const status = s.metadata_status;
                const isResolved = status === "resolved_official_bundle" || status === "resolved_official_screenshot";
                if (!isResolved && status !== "unresolved") {
                    throw new Error(`[ChapterDataService] 第 ${idx} 筆分支劇情 metadata_status 不合法: ${status}`);
                }

                let chapterDisplay = "";
                let titleDisplay = "";

                // 4. Resolved 契約檢查：必須完整包含非空之 branch_label, title, subtitle
                if (isResolved) {
                    if (
                        typeof s.branch_label !== 'string' || !s.branch_label.trim() ||
                        typeof s.title !== 'string' || !s.title.trim() ||
                        typeof s.subtitle !== 'string' || !s.subtitle.trim()
                    ) {
                        throw new Error(`[ChapterDataService] 第 ${idx} 筆 resolved 分支劇情 (${s.story_id}) 缺少必要之描述性欄位`);
                    }
                    chapterDisplay = s.title;
                    titleDisplay = s.subtitle;
                }

                // 5. Unresolved 契約檢查：branch_label, title, subtitle 必須嚴格為 null
                if (status === "unresolved") {
                    if (s.branch_label !== null || s.title !== null || s.subtitle !== null) {
                        throw new Error(`[ChapterDataService] 第 ${idx} 筆 unresolved 分支劇情 (${s.story_id}) 混入了非 null 描述性欄位`);
                    }
                    const branchIdx = (s.story_id % 100);
                    chapterDisplay = `分支劇情 ${branchIdx}`;
                    titleDisplay = `分支劇情 ${branchIdx}`;
                }

                const groupId = 2200 + s.chapter;

                return {
                    id: s.story_id,
                    chapter: chapterDisplay,
                    title: titleDisplay,
                    groupId: groupId,
                    part: 3,
                    isEvent: false,
                    type: 'main',
                    isBranch: true,
                    branchLabel: s.branch_label || null,
                    metadataStatus: status
                };
            });
        },

        async load() {
            if (this.loaded) return this.data;
            try {
                console.log('[ChapterDataService] 開始載入資料檔...');
                const [resp, respSum, respBranch] = await Promise.all([
                    fetch('data/chapters.json?v=' + Date.now()),
                    fetch('data/main_story_chapter_summaries.json?v=' + Date.now()).catch(e => {
                        console.error('[ChapterDataService] 載入單話摘要 fetch 失敗:', e);
                        return null;
                    }),
                    fetch('data/branch_stories.json?v=' + Date.now()).catch(e => {
                        console.warn('[ChapterDataService] 載入分支劇情 fetch 失敗 (optional):', e);
                        return null;
                    })
                ]);

                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                this.data = await resp.json();

                if (respSum && respSum.ok) {
                    this.storySummaries = await respSum.json();
                    console.log(`[ChapterDataService] 成功載入單話摘要，共 ${Object.keys(this.storySummaries).length} 筆`);
                } else {
                    console.warn('[ChapterDataService] 單話摘要載入失敗，respSum ok為 false 或未找到檔案。');
                    this.storySummaries = {};
                }

                if (respBranch && respBranch.ok) {
                    const branchJson = await respBranch.json();
                    this.branchStories = this.transformBranchStories(branchJson);
                    console.log(`[ChapterDataService] 成功載入第 3 部分支劇情元數據，共 ${this.branchStories.length} 篇`);
                } else {
                    this.branchStories = [];
                }

                this.loaded = true;
                console.log('[ChapterDataService] 成功載入章節主資料');
            } catch (e) {
                console.error('[ChapterDataService] 載入失敗:', e);
                this.data = { 1: {}, 2: {}, 3: {} };
                this.storySummaries = {};
                this.branchStories = [];
                this.loaded = true;
                throw e; // Fail loudly on malformed data / network failure of core files
            }
            return this.data;
        },

        // 取得章節資訊
        // part: 1|2|3, groupId: story_group_id (如 2001, 2007, 2201, 3001)
        getChapterInfo(part, groupId) {
            if (!this.data) return null;
            const partData = this.data[String(part)] || {};
            const gid = String(groupId);
            // 不分部別，均自 game_world 與 interlude 中尋找對應的群組資料
            return partData.game_world?.[gid] || partData.interlude?.[gid] || partData[gid] || null;
        },

        // 取得章節標題
        getChapterTitle(part, groupId) {
            const info = this.getChapterInfo(part, groupId);
            return info ? info.title : "";
        },

        // 取得章節標題
        getTitle(part, groupId) {
            const info = this.getChapterInfo(part, groupId);
            return info?.title || null;
        },

        // 取得章節摘要
        getSummary(part, groupId) {
            const info = this.getChapterInfo(part, groupId);
            return info?.summary || null;
        },

        // 取得單話資訊
        getStoryInfo(part, groupId, storyId) {
            const info = this.getChapterInfo(part, groupId);
            if (!info || !info.stories) return null;
            return info.stories.find(s => String(s.story_id) === String(storyId)) || null;
        },

        // 取得單話摘要
        getStorySummary(part, groupId, storyId) {
            console.log(`[ChapterDataService] 正在尋找單話摘要, storyId: ${storyId}`);
            if (this.storySummaries && this.storySummaries[String(storyId)]) {
                console.log(`[ChapterDataService] 成功在 main_story_chapter_summaries.json 找到摘要: ${this.storySummaries[String(storyId)].substring(0, 20)}...`);
                return this.storySummaries[String(storyId)];
            }
            const storyInfo = this.getStoryInfo(part, groupId, storyId);
            console.log(`[ChapterDataService] 未能在單話摘要檔中找到，回退使用 chapters.json 大綱: ${storyInfo?.summary ? storyInfo.summary.substring(0, 20) + '...' : '無'}`);
            return storyInfo?.summary || null;
        },

        // 取得章節顯示順序（用於排序）
        getOrder(part, groupId) {
            const info = this.getChapterInfo(part, groupId);
            return info?.order ?? 999;
        },

        // 取得所有章節
        getAllChapters(part) {
            if (!this.data) return [];
            const partData = this.data[String(part)] || {};
            let entries = [];
            
            // 提取 game_world 與 interlude 下的項目
            const gw = Object.entries(partData.game_world || {}).map(([gid, info]) => ({ groupId: parseInt(gid), ...info }));
            const il = Object.entries(partData.interlude || {}).map(([gid, info]) => ({ groupId: parseInt(gid), ...info }));
            
            // 如果外層有直接定義的 flat 資料，也一併提取作為相容性支援
            const flat = Object.entries(partData)
                .filter(([k]) => k !== 'game_world' && k !== 'interlude')
                .map(([gid, info]) => ({ groupId: parseInt(gid), ...info }));

            entries = [...gw, ...il, ...flat];
            return entries.sort((a, b) => a.order - b.order);
        },

        // 由 groupId 推斷部別
        // 2000-2015 → Part 1, 2101-2116 → Part 2, 2201-2230 → Part 3, 3000+ → Part 3
        getPartFromGroupId(groupId) {
            if (groupId >= 2201 && groupId <= 2230) return 3;
            if (groupId >= 2101 && groupId <= 2116) return 2;
            if (groupId >= 3000) return 3;
            if (groupId >= 2000 && groupId <= 2015) return 1;
            return 1;
        },

        // 由 groupId 取得章節鍵名（用於 chapters 物件的 key）
        getChapterKey(part, groupId, fallbackTitle) {
            const info = this.getChapterInfo(part, groupId);
            if (info?.key) return info.key;

            // 回退：依規則生成
            if (part === 1) {
                if (groupId === 2000) return "序章";
                return `第${groupId - 2000}章`;
            }
            if (part === 2) {
                return `第${groupId - 2100}章`;
            }
            if (part === 3) {
                if (groupId >= 2201 && groupId <= 2230) return `第${groupId - 2200}章`;
                if (groupId >= 3001 && groupId <= 3022) return `幕間 ${groupId - 3000}`;
                if (groupId >= 4000) return `幕間 ${groupId - 4000}`;
                return fallbackTitle || `群組 ${groupId}`;
            }
            return fallbackTitle || `群組 ${groupId}`;
        }
    };

    if (typeof window !== 'undefined') {
        window.ChapterDataService = ChapterDataService;
    } else if (typeof global !== 'undefined') {
        global.ChapterDataService = ChapterDataService;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = ChapterDataService;
    }
})();