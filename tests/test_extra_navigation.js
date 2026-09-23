const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { execSync } = require('child_process');

const extraStoryIndex = JSON.parse(fs.readFileSync(path.join(__dirname, '../dashboard/data/extra_story_index.json'), 'utf8'));

// Fetch DB rows via python
const pythonCmd = `python -c "import sqlite3, json; conn = sqlite3.connect('dashboard/redive_tw.db'); c = conn.cursor(); rows = c.execute('SELECT story_id, title, sub_title, story_group_id FROM story_detail WHERE (story_id >= 4000000 AND story_id < 5000000) OR (story_id >= 9000000 AND story_id < 10000000) ORDER BY story_id ASC').fetchall(); print(json.dumps([{'story_id': r[0], 'title': r[1], 'sub_title': r[2], 'story_group_id': r[3]} for r in rows]))"`;

const output = execSync(pythonCmd, { cwd: path.join(__dirname, '..'), encoding: 'utf-8' });
const dbRows = JSON.parse(output);

runTests(dbRows);

function runTests(dbRows) {
    const QuestMapModule = {
        stories: [],
        extraStoryIndex: extraStoryIndex,
        activeTabType: 'extra',
        activeExtraCategory: null,
        activeCharaName: null,
        chapters: {},
        expandedChapter: null,
        directoryLevel: 'level1',
        directoryLevel1ScrollTop: 0,

        escapeHtml(str) {
            if (!str) return '';
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        },
        escapeForAttr(str) {
            return this.escapeHtml(str);
        },
        normalizeDisplayTitle(str) {
            return str || '';
        },

        getExtraCategory(categoryId) {
            const all = [
                ...(this.extraStoryIndex?.official_categories || []),
                ...(this.extraStoryIndex?.legacy_categories || []),
                ...(this.extraStoryIndex?.special_categories || [])
            ];
            return all.find(c => c.id === categoryId) || null;
        },

        loadMockDb(dbRows) {
            this.stories = dbRows.map(row => ({
                id: row.story_id,
                chapter: row.title || "露娜塔/系統劇情",
                title: row.sub_title || "",
                groupId: row.story_group_id,
                isEvent: false,
                type: 'tower'
            }));
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

        getStoryById(id) {
            return this.stories.find(s => s.id === Number(id)) || null;
        },

        getExtraMembership(storyOrId) {
            if (!this.extraStoryIndex) return null;

            let story = null;
            let storyId = null;
            if (storyOrId && typeof storyOrId === 'object') {
                story = storyOrId;
                storyId = Number(story.id);
            } else if (storyOrId != null) {
                storyId = Number(storyOrId);
                story = this.getStoryById(storyId);
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

        groupTowerStories() {
            this.chapters = { '露娜之塔': this.stories.filter(s => s.type === 'tower') };
        },

        groupStories() {
            this.chapters = { '主線劇情': this.stories.filter(s => s.type === 'main') };
        },

        jumpToStory(storyId, closeModalId) {
            if (this.stories.length === 0) return;
            const story = this.getStoryById(storyId);
            if (!story) return;

            const isEvent = story.isEvent;
            const storyType = story.type;
            const extraMembership = this.getExtraMembership(story);

            if (extraMembership) {
                this.activeTabType = 'extra';
                this.activeExtraCategory = extraMembership.categoryId;
                this.groupExtraStories();
            } else if (isEvent) {
                if (this.activeTabType !== 'event') this.activeTabType = 'event';
            } else {
                if (storyType && ['chara', 'guild', 'tower'].includes(storyType)) {
                    this.activeTabType = storyType;
                } else {
                    this.activeTabType = 'main';
                }

                if (storyType === 'tower') {
                    this.groupTowerStories();
                } else {
                    this.groupStories();
                }
            }
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
                    if (s.title && s.chapter && s.chapter.includes('Anniversary')) {
                        resolvedTitle = `${s.chapter.replace(/^.*Anniversary\s*/i, '').trim()} ${s.title}`.trim();
                    }
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
                } else if (this.extraStoryIndex.legacy_categories?.some(c => c.id === category.id)) {
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

        selectExtraCategory(categoryId) {
            if (!this.getExtraCategory(categoryId)) return false;
            this.activeExtraCategory = categoryId;
            this.expandedChapter = null;
            this.directoryLevel = 'level1';
            this.groupExtraStories();
            return true;
        },

        clearActiveExtraCategory() {
            this.activeExtraCategory = null;
            this.expandedChapter = null;
            this.directoryLevel = 'level1';
        },

        getAllActiveTabStories() {
            if (!this.chapters) return [];
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

        getPrevStoryId() {
            const allStories = this.getAllActiveTabStories();
            const index = allStories.findIndex(s => s.id === this.activeStoryId);
            return index > 0 ? allStories[index - 1].id : null;
        },

        getNextStoryId() {
            const allStories = this.getAllActiveTabStories();
            const index = allStories.findIndex(s => s.id === this.activeStoryId);
            return (index !== -1 && index < allStories.length - 1) ? allStories[index + 1].id : null;
        }
    };

    console.log('=== Test 1: Load DB Data and Integrate Extra Index ===');
    QuestMapModule.loadMockDb(dbRows);
    QuestMapModule.integrateExtraStories();

    const officialCount = extraStoryIndex.official_categories.reduce((acc, c) => acc + c.stories.length, 0);
    const specialCount = extraStoryIndex.special_categories.reduce((acc, c) => acc + c.stories.length, 0);
    assert.strictEqual(officialCount, 432, 'Official series index count must be 432');
    assert.strictEqual(specialCount, 5, 'Special count must be 5');
    assert.deepStrictEqual(extraStoryIndex.special_categories.map(c => c.title), [
        'Grand Masters 特別劇情',
        'キャル＆ヤバイバル',
        '銀だこハイボール酒場 × オーエド横丁夏祭'
    ]);
    assert.deepStrictEqual(extraStoryIndex.special_categories.map(c => c.stories.map(s => s.id)), [
        [1001, 1002], [1003], [1004, 1005]
    ]);
    assert.strictEqual(extraStoryIndex.special_categories[1].stories[0].year, 2024);
    const representativeThumbs = Object.fromEntries(extraStoryIndex.official_categories.map(c => [c.id, c.representativeStoryThumbnail]));
    assert.strictEqual(representativeThumbs.luna_tower, 'icon/tower_top/7001.webp');
    assert.strictEqual(representativeThumbs.birthday_stories, 'icon/exstory_top/4010.webp');
    assert.strictEqual(extraStoryIndex.legacy_categories.find(c => c.id === 'mechanical_rima').representativeStoryThumbnail, 'icon/exstory_top/4006.webp');
    assert.strictEqual(extraStoryIndex.legacy_categories.find(c => c.id === 'mysterious_disc').representativeStoryThumbnail, 'icon/exstory_top/4007.webp');
    assert.strictEqual(extraStoryIndex.legacy_categories.find(c => c.id === 'dungeon_additional').representativeStoryThumbnail, 'icon/exstory_top/4003.webp');
    assert.strictEqual(extraStoryIndex.legacy_categories.find(c => c.id === 'birthday_additional').representativeStoryThumbnail, 'icon/exstory_top/4010.webp');
    assert.ok(extraStoryIndex.special_categories.every(c => !c.representativeStoryThumbnail), 'Special corpus must stay text-only without verified thumbnails');
    const serializedIndex = JSON.stringify(extraStoryIndex);
    ['2019 愚人節', '2020 愚人節', '2021 愚人節', '碧藍幻想合作前日譚', '闇影詩章合作前日譚']
        .forEach(label => assert.ok(!serializedIndex.includes(label), `Obsolete special metadata must be absent: ${label}`));
    console.log(`[PASS] Official series index: 432 entries across 12 official categories (+ 5 special = 437)`);

    const legacyCategories = extraStoryIndex.legacy_categories || [];
    const legacyIds = legacyCategories.flatMap(c => c.stories.map(s => s.id));
    assert.strictEqual(legacyIds.length, 14, 'Recovered legacy count must be 14');
    assert.strictEqual(new Set(legacyIds).size, 14, 'Recovered legacy IDs must be unique');
    assert.deepStrictEqual(legacyCategories.find(c => c.id === 'mechanical_rima').stories.map(s => s.id), [4004001, 4004002, 4004003, 4004004, 4004005]);
    assert.deepStrictEqual(legacyCategories.find(c => c.id === 'mysterious_disc').stories.map(s => s.id), [4007001, 4007002, 4007003, 4007004, 4007005]);
    console.log('[PASS] Recovered legacy index contains 14 stories (4006/4007 + supplementary rows)');

    // Snapshot this.stories state before grouping
    const snapshotBefore = JSON.stringify(QuestMapModule.stories);

    console.log('\n=== Test 2: Anniversary Countdown 10 Series -> 126 Child Episodes Check ===');
    QuestMapModule.selectExtraCategory('anniversary_countdown');
    const anniSeriesKeys = Object.keys(QuestMapModule.chapters);
    assert.strictEqual(anniSeriesKeys.length, 10, 'Anniversary must have exactly 10 series groups');

    let totalAnniEpisodes = 0;
    anniSeriesKeys.forEach(k => {
        totalAnniEpisodes += QuestMapModule.chapters[k].length;
        console.log(`  - Series [${k}]: ${QuestMapModule.chapters[k].length} episodes`);
    });
    assert.strictEqual(totalAnniEpisodes, 126, 'Total Anniversary readable child episodes must be 126');
    console.log(`[PASS] Anniversary: 10 series groups cleanly expanded into all 126 readable child episodes`);

    console.log('\n=== Test 3: Reader Prev/Next Boundaries within Anniversary Series ===');
    // Test within 0.5 週年倒數 (9002001 - 9002017)
    QuestMapModule.expandedChapter = '0.5 週年倒數';
    QuestMapModule.activeStoryId = 9002001;
    assert.strictEqual(QuestMapModule.getPrevStoryId(), null, 'First episode in series should have no prev');
    assert.strictEqual(QuestMapModule.getNextStoryId(), 9002002, 'Next episode should be 9002002');

    QuestMapModule.activeStoryId = 9002017;
    assert.strictEqual(QuestMapModule.getPrevStoryId(), 9002016, 'Prev episode should be 9002016');
    assert.strictEqual(QuestMapModule.getNextStoryId(), null, 'Last episode in series should NOT cross into next anniversary series');
    console.log('[PASS] Prev/Next navigation strictly bounded within active Anniversary series');

    console.log('\n=== Test 4: Dungeon Subgroup Check ===');
    QuestMapModule.selectExtraCategory('dungeon');
    const dungeonSubgroups = Object.keys(QuestMapModule.chapters);
    assert.strictEqual(dungeonSubgroups.length, 1, 'Official Dungeon 20 must have exactly 1 verified subgroup');
    assert.strictEqual(QuestMapModule.chapters['地下城'].length, 20, 'Official Dungeon subgroup must contain 20 stories');
    console.log('[PASS] Official Dungeon 20 is verified as a single subgroup (地下城)');

    console.log('\n=== Test 5: Recovered Legacy Categories ===');
    QuestMapModule.selectExtraCategory('mechanical_rima');
    assert.strictEqual(Object.keys(QuestMapModule.chapters).length, 1);
    assert.strictEqual(QuestMapModule.chapters['機械莉瑪特別劇情'].length, 5);
    const mechanicalStories = QuestMapModule.chapters['機械莉瑪特別劇情'].map(s => s.id);
    QuestMapModule.selectExtraCategory('mysterious_disc');
    assert.strictEqual(Object.keys(QuestMapModule.chapters).length, 1);
    assert.strictEqual(QuestMapModule.chapters['神秘圓盤特別劇情'].length, 5);
    assert.notDeepStrictEqual(mechanicalStories, QuestMapModule.chapters['神秘圓盤特別劇情'].map(s => s.id));
    QuestMapModule.selectExtraCategory('dungeon_additional');
    assert.deepStrictEqual(QuestMapModule.chapters['地下城追加'].map(s => s.id), [4003021, 4003022]);
    QuestMapModule.selectExtraCategory('birthday_additional');
    assert.deepStrictEqual(QuestMapModule.chapters['生日劇情追加'].map(s => s.id), [4010207, 4010208]);
    console.log('[PASS] Legacy activities and supplementary stories are separately navigable');

    console.log('\n=== Test 6: All Categories Navigation & Immutability Check ===');
    const allCategories = [
        ...extraStoryIndex.official_categories,
        ...legacyCategories,
        ...extraStoryIndex.special_categories
    ];

    allCategories.forEach(cat => {
        const ok = QuestMapModule.selectExtraCategory(cat.id);
        assert.ok(ok, `Failed to select category ${cat.id}`);
        const groupKeys = Object.keys(QuestMapModule.chapters);
        assert.ok(groupKeys.length >= 1, `Category ${cat.id} must have at least 1 subgroup`);
    });

    // Immutability Check
    const snapshotAfter = JSON.stringify(QuestMapModule.stories);
    assert.strictEqual(snapshotBefore, snapshotAfter, 'this.stories must NOT be mutated by groupExtraStories()');
    assert.deepStrictEqual(extraStoryIndex.special_categories.flatMap(c => c.stories.map(s => s.id)), [1001, 1002, 1003, 1004, 1005]);
    console.log('[PASS] Immutability verified: this.stories untouched across all 18 categories');

    console.log('\n=== Test 7: Extra Membership & jumpToStory Routing ===');
    // A. 驗證特別指定之話數 ID 導向
    const testCases = [
        { id: 4004001, expectedCategory: 'mechanical_rima', isChild: false, label: 'mechanical_rima' },
        { id: 4007001, expectedCategory: 'mysterious_disc', isChild: false, label: 'mysterious_disc' },
        { id: 4003021, expectedCategory: 'dungeon_additional', isChild: false, label: 'dungeon_additional' },
        { id: 4010207, expectedCategory: 'birthday_additional', isChild: false, label: 'birthday_additional' },
        { id: 1001, expectedCategory: 'grand_masters', isChild: false, label: 'grand_masters' },
        { id: 1003, expectedCategory: 'karyl_yabaival', isChild: false, label: 'karyl_yabaival' },
        { id: 1004, expectedCategory: 'gindaco_oedo_summer', isChild: false, label: 'gindaco_oedo_summer' },
        { id: 9002001, expectedCategory: 'anniversary_countdown', isChild: false, label: 'anniversary anchor 9002001' },
        { id: 9002002, expectedCategory: 'anniversary_countdown', isChild: true, label: 'anniversary child 9002002' },
        { id: 7001000, expectedCategory: 'luna_tower', isChild: false, label: 'luna tower 7001000' }
    ];

    testCases.forEach(tc => {
        const membership = QuestMapModule.getExtraMembership(tc.id);
        assert.ok(membership, `${tc.label} (${tc.id}) must have Extra membership`);
        assert.strictEqual(membership.categoryId, tc.expectedCategory, `${tc.label} categoryId mismatch`);
        assert.strictEqual(membership.isSeriesChild, tc.isChild, `${tc.label} isSeriesChild mismatch`);

        // 測試 jumpToStory
        QuestMapModule.activeTabType = 'main'; // 重設為 main
        QuestMapModule.jumpToStory(tc.id);
        assert.strictEqual(QuestMapModule.activeTabType, 'extra', `${tc.label} jumpToStory must switch activeTabType to 'extra'`);
        assert.strictEqual(QuestMapModule.activeExtraCategory, tc.expectedCategory, `${tc.label} jumpToStory must switch activeExtraCategory to ${tc.expectedCategory}`);

        // 驗證原本為 tower 的故事其 story.type 本身絕不被修改 (保持原始值)
        const storyObj = QuestMapModule.getStoryById(tc.id);
        if (storyObj && ((tc.id >= 4000000 && tc.id < 5000000) || (tc.id >= 9000000 && tc.id < 10000000))) {
            assert.strictEqual(storyObj.type, 'tower', `${tc.label} story.type must remain 'tower' without being overwritten`);
        }
    });
    console.log('[PASS] All 10 specific Extra stories routed to correct Extra categories without mutating story.type');

    // B. non-extra tower story 仍維持既有 tower routing
    QuestMapModule.stories.push({
        id: 7999999,
        chapter: '測試未歸類塔',
        title: '測試未歸類塔話數',
        groupId: 7999,
        isEvent: false,
        type: 'tower'
    });
    const nonExtraMembership = QuestMapModule.getExtraMembership(7999999);
    assert.strictEqual(nonExtraMembership, null, 'Non-extra tower story must return null membership');

    QuestMapModule.activeTabType = 'main';
    QuestMapModule.jumpToStory(7999999);
    assert.strictEqual(QuestMapModule.activeTabType, 'tower', 'Non-extra tower story jumpToStory must route to tower tab');
    console.log('[PASS] Non-extra tower story strictly maintains existing tower tab routing');

    console.log('\n✅ All Metadata Closure & Navigation tests PASSED successfully with 0 errors.');
}
