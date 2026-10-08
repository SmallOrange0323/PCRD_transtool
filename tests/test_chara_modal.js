/**
 * tests/test_chara_modal.js
 * 角色檔案 modal 頭像契約測試：
 * - 目前對白有唯一 explicit unit_id 時，modal 必須沿用 exact canonical avatar。
 * - 同名角色在本話有多個 unit_id 時，不得自行猜測變體。
 * - 沒有 explicit unit_id 時，保留既有 name-based fallback。
 */

const assert = require('assert');
const path = require('path');

global.window = global;

global.QuestMapModule = {
    currentDialogueList: [],
    getCharaRealName(name) {
        return name;
    }
};

require(path.join(__dirname, '../dashboard/chara-modal.js'));
const CharaModalView = global.CharaModalView;
require(path.join(__dirname, '../dashboard/story-data-service.js'));
const realStoryDataService = global.window.StoryDataService;

let passed = 0;
const testQueue = [];
function test(name, fn) {
    testQueue.push({ name, fn });
}

async function runTests() {
    console.log('=== Testing CharaModalView avatar resolution ===');
    for (const { name, fn } of testQueue) {
        try {
            await fn();
            console.log(`  [PASS] ${name}`);
            passed++;
        } catch (error) {
            console.error(`  [FAIL] ${name}:`, error);
            process.exit(1);
        }
    }
    console.log(`\n✅ All ${passed} CharaModalView tests passed successfully!`);
}

test('Test 1 — unique explicit dialogue unit_id is resolved', () => {
    global.QuestMapModule.currentDialogueList = [
        { name: '秘書', words: '承知しました。', unit_id: 6111 },
        { name: '克蕾琪塔', words: 'ごきげんよう。', unit_id: 118011 }
    ];

    assert.strictEqual(
        CharaModalView.resolveCurrentDialogueUnitId('秘書'),
        6111,
        '秘書 should resolve to the exact dialogue unit_id 6111'
    );
});

test('Test 2 — ambiguous same-name variants fail closed to null', () => {
    global.QuestMapModule.currentDialogueList = [
        { name: '秘書', words: '通常服', unit_id: 6111 },
        { name: '秘書', words: '別衣装', unit_id: 6112 }
    ];

    assert.strictEqual(
        CharaModalView.resolveCurrentDialogueUnitId('秘書'),
        null,
        'Modal must not guess when one name maps to multiple explicit unit_ids'
    );
});

test('Test 3 — renderModal prefers exact avatar when dialogue identity is unique', () => {
    global.QuestMapModule.currentDialogueList = [
        { name: '秘書', words: '承知しました。', unit_id: 6111 }
    ];

    const originalGetCharaModal = CharaModalView.getCharaModal;
    const fakeModal = {
        innerHTML: '',
        classList: {
            added: [],
            add(name) { this.added.push(name); }
        }
    };
    CharaModalView.getCharaModal = () => fakeModal;

    let exactCall = null;
    let fallbackCalls = 0;
    const avatarService = {
        getAvatarHtmlByUnitId(unitId, charaName, speakerAvatars) {
            exactCall = { unitId, charaName, speakerAvatars };
            return `<img data-exact-unit-id="${unitId}">`;
        },
        getAvatarHtml() {
            fallbackCalls++;
            return '<div>fallback</div>';
        }
    };

    try {
        CharaModalView.renderModal({
            realCharaName: '秘書',
            profile: null,
            appearances: [],
            speakerAvatars: {},
            avatarService,
            resolveStoryLabel: null,
            escapeHtml: null
        });

        assert(exactCall, 'Exact avatar resolver should be called');
        assert.strictEqual(exactCall.unitId, 6111);
        assert.strictEqual(exactCall.charaName, '秘書');
        assert.strictEqual(fallbackCalls, 0, 'Name-based fallback must not run when exact identity is available');
        assert(fakeModal.innerHTML.includes('data-exact-unit-id="6111"'));
        assert(fakeModal.classList.added.includes('active'));
    } finally {
        CharaModalView.getCharaModal = originalGetCharaModal;
    }
});

test('Test 4 — renderModal preserves name fallback without unique explicit identity', () => {
    global.QuestMapModule.currentDialogueList = [];

    const originalGetCharaModal = CharaModalView.getCharaModal;
    const fakeModal = {
        innerHTML: '',
        classList: { add() {} }
    };
    CharaModalView.getCharaModal = () => fakeModal;

    let exactCalls = 0;
    let fallbackCalls = 0;
    const avatarService = {
        getAvatarHtmlByUnitId() {
            exactCalls++;
            return '<div>unexpected exact</div>';
        },
        getAvatarHtml(charaName) {
            fallbackCalls++;
            return `<div data-fallback-name="${charaName}">fallback</div>`;
        }
    };

    try {
        CharaModalView.renderModal({
            realCharaName: '克蕾琪塔',
            profile: null,
            appearances: [],
            speakerAvatars: { '克蕾琪塔': 118011 },
            avatarService,
            resolveStoryLabel: null,
            escapeHtml: null
        });

        assert.strictEqual(exactCalls, 0);
        assert.strictEqual(fallbackCalls, 1);
        assert(fakeModal.innerHTML.includes('data-fallback-name="克蕾琪塔"'));
    } finally {
        CharaModalView.getCharaModal = originalGetCharaModal;
    }
});


test('Test 5 — appearance directory renders hierarchical context without truncating titles', () => {
    const html = CharaModalView.renderAppearancesHtml(
        [2217001, 5215005],
        (storyId) => {
            if (storyId === 2217001) {
                return {
                    storyId,
                    path: ['主線劇情', '第3部', '第17章'],
                    label: '第1話｜「第二型態」',
                    fullLabel: '主線劇情・第3部・第17章・第1話｜「第二型態」',
                    searchText: '主線劇情 第3部 第17章 第1話 第二型態 2217001',
                    sortKey: '10-002217001',
                    canNavigate: true
                };
            }
            return {
                storyId,
                path: ['活動劇情', '2026年', 'VILLAINESS 避開吧！鏡華的變疑分子毀滅結局'],
                label: '第5話｜測試標題',
                fullLabel: '活動劇情・2026年・VILLAINESS 避開吧！鏡華的變疑分子毀滅結局・第5話｜測試標題',
                searchText: '活動劇情 2026 VILLAINESS 第5話 測試標題 5215005',
                sortKey: '20-005215005',
                canNavigate: true
            };
        },
        null,
        null
    );

    assert(html.includes('chara-appearance-search'), 'Directory should provide a search field');
    assert(html.includes('主線劇情'));
    assert(html.includes('第3部'));
    assert(html.includes('第17章'));
    assert(html.includes('第1話｜「第二型態」'));
    assert(html.includes('VILLAINESS 避開吧！鏡華的變疑分子毀滅結局'), 'Long event title must not be cut to 15 characters');
    assert(html.includes('QuestMapModule.jumpToStory(2217001'));
});

test('Test 6 — unresolved story IDs are isolated under an explicit fallback group', () => {
    const html = CharaModalView.renderAppearancesHtml(
        [9876543],
        () => null,
        null,
        null
    );

    assert(html.includes('其他／無法分類'));
    assert(html.includes('ID: 9876543'));
    assert(html.includes('is-unresolved'));
    assert(!html.includes('QuestMapModule.jumpToStory(9876543'), 'Unresolved IDs should not render a dead navigation button');
});

test('Test 7 — resolveAppearanceStoryMeta resolves official metadata fallback when story is unindexed', () => {
    // Setup QuestMapModule with resolveAppearanceStoryMeta
    const mockMapModule = {
        getStoryById(id) {
            return null; // unindexed story
        },
        normalizeDisplayTitle(val) {
            return String(val || '').trim();
        }
    };

    // Load resolveAppearanceStoryMeta implementation onto mockMapModule
    const mapCode = require('fs').readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
    // Extract resolveAppearanceStoryMeta definition
    const match = mapCode.match(/resolveAppearanceStoryMeta\(storyId\)\s*\{[\s\S]*?\n    \},/);
    assert(match, 'Must find resolveAppearanceStoryMeta in map.js');
    const fnBody = match[0].replace(/resolveAppearanceStoryMeta\(storyId\)\s*\{/, '').replace(/\},\s*$/, '');
    mockMapModule.resolveAppearanceStoryMeta = new Function('storyId', fnBody);

    // Mock StoryDataService
    let mockMetadataLoaded = true;
    global.window.StoryDataService = {
        hasMetadataLoaded() {
            return mockMetadataLoaded;
        },
        getMetadataSync(storyId) {
            if (storyId === 10001) {
                return { chapter_title: '第1章', subtitle: '冒險的開始' };
            }
            if (storyId === 10002) {
                return { chapter_title: '第2章', subtitle: null };
            }
            if (storyId === 10003) {
                return { chapter_title: '', subtitle: '只有副標題' };
            }
            if (storyId === 10004) {
                return { chapter_title: null, subtitle: null };
            }
            return null;
        }
    };

    // Case 1: both chapter_title and subtitle
    const res1 = mockMapModule.resolveAppearanceStoryMeta(10001);
    assert.deepStrictEqual(res1.path, ['其他／未編目劇情']);
    assert.strictEqual(res1.label, '第1章｜冒險的開始');
    assert.strictEqual(res1.fullLabel, '其他／未編目劇情・第1章｜冒險的開始');
    assert(res1.searchText.includes('第1章｜冒險的開始'));
    assert(res1.searchText.includes('10001'));
    assert.strictEqual(res1.canNavigate, false);
    assert.strictEqual(res1.sortKey, '98-000010001');

    // Case 2: only chapter_title
    const res2 = mockMapModule.resolveAppearanceStoryMeta(10002);
    assert.deepStrictEqual(res2.path, ['其他／未編目劇情']);
    assert.strictEqual(res2.label, '第2章');
    assert.strictEqual(res2.fullLabel, '其他／未編目劇情・第2章');
    assert.strictEqual(res2.canNavigate, false);

    // Case 3: only subtitle
    const res3 = mockMapModule.resolveAppearanceStoryMeta(10003);
    assert.deepStrictEqual(res3.path, ['其他／未編目劇情']);
    assert.strictEqual(res3.label, '只有副標題');
    assert.strictEqual(res3.canNavigate, false);

    // Case 4: empty titles fallback to '未命名劇情（ID: {storyId}）'
    const res4 = mockMapModule.resolveAppearanceStoryMeta(10004);
    assert.deepStrictEqual(res4.path, ['其他／未編目劇情']);
    assert.strictEqual(res4.label, '未命名劇情（ID: 10004）');
    assert.strictEqual(res4.canNavigate, false);

    // Case 5: metadata loaded, but ID absent -> '無法識別'
    const res5 = mockMapModule.resolveAppearanceStoryMeta(99999);
    assert.deepStrictEqual(res5.path, ['無法識別']);
    assert.strictEqual(res5.label, 'ID: 99999');
    assert.strictEqual(res5.fullLabel, '無法識別・ID: 99999');
    assert.strictEqual(res5.searchText, 'ID 99999');
    assert.strictEqual(res5.sortKey, '99-000099999');
    assert.strictEqual(res5.canNavigate, false);

    // Case 6: metadata NOT loaded yet -> '載入名稱中…（ID: {storyId}）'
    mockMetadataLoaded = false;
    const res6 = mockMapModule.resolveAppearanceStoryMeta(99999);
    assert.deepStrictEqual(res6.path, ['其他／未編目劇情']);
    assert.strictEqual(res6.label, '載入名稱中…（ID: 99999）');
    assert.strictEqual(res6.fullLabel, '其他／未編目劇情・載入名稱中…（ID: 99999）');
    assert(res6.searchText.includes('載入名稱中…'));
    assert.strictEqual(res6.canNavigate, false);
});

test('Test 8 — appearance directory renders metadata fallback items and prevents navigation', () => {
    const metaResolver = (storyId) => {
        if (storyId === 10001) {
            return {
                storyId: 10001,
                path: ['其他／未編目劇情'],
                label: '第1章｜冒險的開始',
                fullLabel: '其他／未編目劇情・第1章｜冒險的開始',
                searchText: '其他／未編目劇情・第1章｜冒險的開始 10001',
                sortKey: '98-000010001',
                canNavigate: false
            };
        }
        if (storyId === 99999) {
            return {
                storyId: 99999,
                path: ['無法識別'],
                label: 'ID: 99999',
                fullLabel: '無法識別・ID: 99999',
                searchText: 'ID 99999',
                sortKey: '99-000099999',
                canNavigate: false
            };
        }
        return null;
    };

    const html = CharaModalView.renderAppearancesHtml(
        [10001, 99999],
        metaResolver,
        null,
        null
    );

    assert(html.includes('其他／未編目劇情'), 'Should contain unindexed metadata section');
    assert(html.includes('第1章｜冒險的開始'), 'Should render human-readable chapter and subtitle');
    assert(html.includes('無法識別'), 'Should contain unidentifiable fallback section');
    assert(html.includes('ID: 99999'), 'Should show raw ID under unidentifiable section');
    assert(!html.includes('QuestMapModule.jumpToStory(10001'), 'Must not render navigation click handler for unindexed stories');
    assert(!html.includes('QuestMapModule.jumpToStory(99999'), 'Must not render navigation click handler for unidentifiable stories');
});

test('Test 9 — showCharaModal opens synchronously without awaiting metadata fetch', async () => {
    let metadataFetched = false;
    let modalOpened = false;

    const fakeSection = {
        innerHTML: '',
        querySelector(selector) {
            return null;
        }
    };

    const fakeModal = {
        className: 'game-modal-overlay',
        classList: {
            contains(cls) { return this.classListInternal ? this.classListInternal.has(cls) : false; },
            add(cls) {
                if (!this.classListInternal) this.classListInternal = new Set();
                this.classListInternal.add(cls);
                if (cls === 'active') modalOpened = true;
            },
            remove(cls) {
                if (!this.classListInternal) this.classListInternal = new Set();
                this.classListInternal.delete(cls);
            }
        },
        innerHTML: '',
        querySelector(selector) {
            if (selector === '.chara-appearance-section') return fakeSection;
            return null;
        }
    };

    const originalGetCharaModal = CharaModalView.getCharaModal;
    CharaModalView.getCharaModal = () => fakeModal;

    let resolveFetch;
    const pendingPromise = new Promise((resolve) => {
        resolveFetch = () => {
            metadataFetched = true;
            resolve();
        };
    });

    global.window.StoryDataService = {
        _metadataCache: null,
        hasMetadataLoaded() { return false; },
        ensureMetadataLoaded() {
            return pendingPromise;
        },
        getMetadataSync() { return null; }
    };

    global.window.PCRDatabase = {
        runQuery: async () => []
    };

    const testModule = {
        _charaModalRequestId: 0,
        appearanceMap: { '可可蘿': [10001] },
        charaDetailCache: { '可可蘿': { guild: '美食殿堂' } },
        speakerAvatars: {},
        getCharaRealName: (n) => n,
        getStoryById: (id) => null, // unindexed -> needsMetadata is true
        ensureAppearanceMap: async () => {},
        getCharaModal: () => fakeModal,
        resolveAppearanceStoryMeta: (id) => ({
            storyId: id,
            path: ['其他／未編目劇情'],
            label: `載入名稱中…（ID: ${id}）`,
            fullLabel: `其他／未編目劇情・載入名稱中…（ID: ${id}）`,
            searchText: `ID ${id}`,
            sortKey: `98-${id}`,
            canNavigate: false
        }),
        escapeHtml: (s) => s
    };

    // Load showCharaModal definition from map.js
    const mapCode = require('fs').readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
    const match = mapCode.match(/async showCharaModal\(charaName, unitId = null\)\s*\{[\s\S]*?\n    \},/);
    assert(match, 'Must find showCharaModal in map.js');
    const fnBody = match[0].replace(/async showCharaModal\(charaName, unitId = null\)\s*\{/, '').replace(/\},\s*$/, '');
    testModule.showCharaModal = new Function('charaName', 'unitId = null', `return (async () => { ${fnBody} })()`);

    // Call showCharaModal
    const openPromise = testModule.showCharaModal('可可蘿');
    await openPromise;

    // The modal must open immediately BEFORE metadata promise resolves
    assert.strictEqual(modalOpened, true, 'Modal must open immediately');
    assert.strictEqual(metadataFetched, false, 'Modal opened without awaiting metadata completion');
    assert(fakeModal.innerHTML.includes('載入名稱中…'), 'Initially renders "載入名稱中…" before metadata is available');

    // Clean up
    resolveFetch();
    await pendingPromise;
    await new Promise(r => setTimeout(r, 10));
    CharaModalView.getCharaModal = originalGetCharaModal;
});

test('Test 10 — updateAppearancesSection preserves search query and only updates appearance DOM', () => {
    let innerHtml = `
        <div class="game-modal-content">
            <div class="chara-profile-header">頭像與資料保持不變</div>
            <div class="chara-appearance-section">
                <h4>📖 登場劇情目錄</h4>
                <div class="chara-appearance-directory">
                    <div class="chara-appearance-toolbar">
                        <input type="search" class="chara-appearance-search" value="關鍵字搜尋" />
                        <span class="chara-appearance-search-status">1 話</span>
                    </div>
                    <div class="chara-appearance-tree">
                        <div class="chara-appearance-item">舊項目</div>
                    </div>
                </div>
            </div>
        </div>
    `;

    const fakeSection = {
        innerHTML: '',
        querySelector(selector) {
            if (selector === '.chara-appearance-search') {
                return { value: '關鍵字搜尋' };
            }
            return null;
        }
    };

    const fakeModal = {
        querySelector(selector) {
            if (selector === '.chara-appearance-section') return fakeSection;
            return null;
        }
    };

    const originalGetCharaModal = CharaModalView.getCharaModal;
    CharaModalView.getCharaModal = () => fakeModal;

    try {
        let filterCalledWith = null;
        const origFilter = CharaModalView.filterAppearanceDirectory;
        CharaModalView.filterAppearanceDirectory = (inputEl) => {
            filterCalledWith = inputEl.value;
        };

        CharaModalView.updateAppearancesSection(
            [2217001],
            (id) => ({
                storyId: id,
                path: ['主線劇情'],
                label: '第1話',
                fullLabel: '主線劇情・第1話',
                searchText: '主線劇情 第1話',
                sortKey: id,
                canNavigate: true
            }),
            (s) => s
        );

        assert(fakeSection.innerHTML.includes('<h4>📖 登場劇情目錄</h4>'));
        assert(fakeSection.innerHTML.includes('主線劇情'));
        CharaModalView.filterAppearanceDirectory = origFilter;
    } finally {
        CharaModalView.getCharaModal = originalGetCharaModal;
    }
});

test('Test 11 — stale requestId or inactive modal drops background metadata update', async () => {
    let partialUpdateCalled = false;
    let resolveMetadata;
    const metadataPromise = new Promise(r => { resolveMetadata = r; });

    global.window.StoryDataService = {
        _metadataCache: null,
        hasMetadataLoaded() { return false; },
        ensureMetadataLoaded() { return metadataPromise; },
        getMetadataSync() { return null; }
    };

    const fakeModal = {
        innerHTML: '',
        classList: {
            contains(cls) { return cls === 'active' ? false : false; }, // Closed modal
            add(cls) {},
            remove(cls) {}
        }
    };

    const origUpdate = CharaModalView.updateAppearancesSection;
    const origGetCharaModal = CharaModalView.getCharaModal;
    CharaModalView.getCharaModal = () => fakeModal;
    CharaModalView.updateAppearancesSection = () => {
        partialUpdateCalled = true;
    };

    const testModule = {
        _charaModalRequestId: 0,
        appearanceMap: { '佩可': [10001] },
        charaDetailCache: { '佩可': { guild: '美食殿堂' } },
        speakerAvatars: {},
        getCharaRealName: (n) => n,
        getStoryById: (id) => null,
        ensureAppearanceMap: async () => {},
        getCharaModal: () => fakeModal,
        resolveAppearanceStoryMeta: (id) => ({
            storyId: id,
            path: ['其他'],
            label: `ID: ${id}`,
            fullLabel: `ID: ${id}`,
            searchText: `${id}`,
            sortKey: `${id}`,
            canNavigate: false
        }),
        escapeHtml: (s) => s
    };

    const mapCode = require('fs').readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
    const match = mapCode.match(/async showCharaModal\(charaName, unitId = null\)\s*\{[\s\S]*?\n    \},/);
    const fnBody = match[0].replace(/async showCharaModal\(charaName, unitId = null\)\s*\{/, '').replace(/\},\s*$/, '');
    testModule.showCharaModal = new Function('charaName', 'unitId = null', `return (async () => { ${fnBody} })()`);

    // Call modal, which initiates background load
    await testModule.showCharaModal('佩可');

    // Simulate modal closed or new character clicked
    testModule._charaModalRequestId++; // Token advance (e.g. clicked another character)

    // Resolve metadata fetch
    resolveMetadata();
    await metadataPromise;
    // Let event loop drain microtasks
    await new Promise(r => setTimeout(r, 10));

    assert.strictEqual(partialUpdateCalled, false, 'Should not perform update when token advanced or modal closed');

    CharaModalView.updateAppearancesSection = origUpdate;
    CharaModalView.getCharaModal = origGetCharaModal;
});

test('Test 12 — all canonical appearances do NOT trigger ensureMetadataLoaded', async () => {
    let ensureMetadataCalled = false;
    global.window.StoryDataService = {
        hasMetadataLoaded() { return false; },
        ensureMetadataLoaded() {
            ensureMetadataCalled = true;
            return Promise.resolve({});
        },
        getMetadataSync() { return null; }
    };

    const fakeModal = {
        innerHTML: '',
        classList: {
            contains(cls) { return true; },
            add(cls) {},
            remove(cls) {}
        }
    };
    const origGet = CharaModalView.getCharaModal;
    CharaModalView.getCharaModal = () => fakeModal;

    const testModule = {
        _charaModalRequestId: 0,
        appearanceMap: { '凱留': [100101, 100102] },
        charaDetailCache: { '凱留': { guild: '美食殿堂' } },
        speakerAvatars: {},
        getCharaRealName: (n) => n,
        // All stories exist in canonical index
        getStoryById: (id) => ({ id, chapter: '第1章', title: '測試' }),
        ensureAppearanceMap: async () => {},
        getCharaModal: () => fakeModal,
        resolveAppearanceStoryMeta: (id) => ({
            storyId: id,
            path: ['主線劇情'],
            label: '第1話',
            fullLabel: '主線劇情・第1話',
            searchText: '100101',
            sortKey: id,
            canNavigate: true
        }),
        escapeHtml: (s) => s
    };

    const mapCode = require('fs').readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
    const match = mapCode.match(/async showCharaModal\(charaName, unitId = null\)\s*\{[\s\S]*?\n    \},/);
    const fnBody = match[0].replace(/async showCharaModal\(charaName, unitId = null\)\s*\{/, '').replace(/\},\s*$/, '');
    testModule.showCharaModal = new Function('charaName', 'unitId = null', `return (async () => { ${fnBody} })()`);

    await testModule.showCharaModal('凱留');

    assert.strictEqual(ensureMetadataCalled, false, 'Should not trigger ensureMetadataLoaded when all stories are canonical');
    CharaModalView.getCharaModal = origGet;
});

test('Test 13 — unindexed appearance triggers ensureMetadataLoaded once in background', async () => {
    let ensureMetadataCalls = 0;
    global.window.StoryDataService = {
        hasMetadataLoaded() { return false; },
        ensureMetadataLoaded() {
            ensureMetadataCalls++;
            return Promise.resolve({});
        },
        getMetadataSync() { return null; }
    };

    const fakeModal = {
        innerHTML: '',
        classList: {
            contains(cls) { return true; },
            add(cls) {},
            remove(cls) {}
        },
        querySelector(selector) {
            return null;
        }
    };
    const origGet = CharaModalView.getCharaModal;
    CharaModalView.getCharaModal = () => fakeModal;

    const testModule = {
        _charaModalRequestId: 0,
        appearanceMap: { '可可蘿': [100101, 99999] },
        charaDetailCache: { '可可蘿': { guild: '美食殿堂' } },
        speakerAvatars: {},
        getCharaRealName: (n) => n,
        // 99999 is unindexed
        getStoryById: (id) => (id === 100101 ? { id, chapter: '第1章', title: '測試' } : null),
        ensureAppearanceMap: async () => {},
        getCharaModal: () => fakeModal,
        resolveAppearanceStoryMeta: (id) => ({
            storyId: id,
            path: ['其他'],
            label: `${id}`,
            fullLabel: `${id}`,
            searchText: `${id}`,
            sortKey: id,
            canNavigate: false
        }),
        escapeHtml: (s) => s
    };

    const mapCode = require('fs').readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
    const match = mapCode.match(/async showCharaModal\(charaName, unitId = null\)\s*\{[\s\S]*?\n    \},/);
    const fnBody = match[0].replace(/async showCharaModal\(charaName, unitId = null\)\s*\{/, '').replace(/\},\s*$/, '');
    testModule.showCharaModal = new Function('charaName', 'unitId = null', `return (async () => { ${fnBody} })()`);

    await testModule.showCharaModal('可可蘿');

    assert.strictEqual(ensureMetadataCalls, 1, 'Should trigger ensureMetadataLoaded once for unindexed story');
    CharaModalView.getCharaModal = origGet;
});

test('Test 14 — updateAppearancesSection preserves focus, caret, scroll, and open details state', () => {
    let focusCalled = false;
    let selectionRangeCalled = false;
    let selectedRange = null;

    const oldInput = {
        value: '',
        selectionStart: 4,
        selectionEnd: 4
    };

    const newInput = {
        value: '',
        focus() { focusCalled = true; },
        setSelectionRange(s, e) {
            selectionRangeCalled = true;
            selectedRange = [s, e];
        }
    };

    const oldDetailsGroup = {
        getAttribute(attr) {
            return attr === 'data-group-path' ? '主線劇情 / 第1部' : null;
        },
        open: true
    };

    const newDetailsGroup1 = {
        getAttribute(attr) {
            return attr === 'data-group-path' ? '主線劇情 / 第1部' : null;
        },
        open: false
    };

    const newDetailsGroup2 = {
        getAttribute(attr) {
            return attr === 'data-group-path' ? '活動劇情 / 2026年' : null;
        },
        open: false
    };

    const oldTree = { scrollTop: 128 };
    const newTree = { scrollTop: 0 };

    let currentInput = oldInput;
    let currentTree = oldTree;
    let currentGroups = [oldDetailsGroup];

    const fakeSection = {
        innerHTML: '',
        querySelector(selector) {
            if (selector === '.chara-appearance-search') return currentInput;
            if (selector === '.chara-appearance-tree') return currentTree;
            return null;
        },
        querySelectorAll(selector) {
            if (selector === '.chara-appearance-group[open]') {
                return currentGroups.filter(g => g.open);
            }
            if (selector === '.chara-appearance-group') {
                return currentGroups;
            }
            return [];
        }
    };

    const fakeModal = {
        querySelector(selector) {
            if (selector === '.chara-appearance-section') return fakeSection;
            return null;
        }
    };

    const origGet = CharaModalView.getCharaModal;
    CharaModalView.getCharaModal = () => fakeModal;

    // Simulate activeElement being oldInput
    const origDoc = global.document;
    global.document = {
        activeElement: oldInput,
        getElementById() { return fakeModal; }
    };

    try {
        // Hook into innerHTML setter to simulate new DOM creation upon rendering
        Object.defineProperty(fakeSection, 'innerHTML', {
            set(val) {
                currentInput = newInput;
                currentTree = newTree;
                currentGroups = [newDetailsGroup1, newDetailsGroup2];
            },
            get() { return ''; }
        });

        CharaModalView.updateAppearancesSection(
            [100101],
            (id) => ({
                storyId: id,
                path: ['主線劇情', '第1部'],
                label: '第1話',
                fullLabel: '主線劇情・第1部・第1話',
                searchText: '100101',
                sortKey: id,
                canNavigate: true
            }),
            (s) => s
        );

        assert.strictEqual(focusCalled, true, 'Search input focus must be restored');
        assert.strictEqual(selectionRangeCalled, true, 'Search caret must be restored');
        assert.deepStrictEqual(selectedRange, [4, 4], 'Caret range must match snapshot');
        assert.strictEqual(newTree.scrollTop, 128, 'Tree scrollTop must be restored');
        assert.strictEqual(newDetailsGroup1.open, true, 'Previously opened group must remain open');
        assert.strictEqual(newDetailsGroup2.open, false, 'Previously closed group must remain closed');
    } finally {
        global.document = origDoc;
        CharaModalView.getCharaModal = origGet;
    }
});

test('Test 15 — metadata failure handling, explicit error label, and safe retry', async () => {
    // 1. 驗證 StoryDataService 失敗標記
    const service = realStoryDataService;
    service._metadataCache = null;
    service._loadingPromise = null;
    service._loadFailed = false;
    assert.strictEqual(service.hasMetadataFailed(), false);

    // Mock fetch failure
    const origFetch = global.fetch;
    global.fetch = async () => ({ ok: false, status: 500 });

    try {
        const res = await service.ensureMetadataLoaded();
        assert.strictEqual(res, null);
        assert.strictEqual(service.hasMetadataFailed(), true);

        // 2. 驗證 resolveAppearanceStoryMeta 在 failure 時產生明確錯誤狀態
        global.window.StoryDataService = service;
        const mockMapModule = {
            getStoryById: () => null,
            normalizeDisplayTitle: (s) => s
        };
        const mapCode = require('fs').readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
        const match = mapCode.match(/resolveAppearanceStoryMeta\(storyId\)\s*\{[\s\S]*?\n    \},/);
        const fnBody = match[0].replace(/resolveAppearanceStoryMeta\(storyId\)\s*\{/, '').replace(/\},\s*$/, '');
        mockMapModule.resolveAppearanceStoryMeta = new Function('storyId', fnBody);

        const failMeta = mockMapModule.resolveAppearanceStoryMeta(99999);
        assert.deepStrictEqual(failMeta.path, ['其他／未編目劇情']);
        assert.strictEqual(failMeta.label, '名稱載入失敗（ID: 99999）');
        assert.strictEqual(failMeta.canNavigate, false);

        // 3. 驗證 renderAppearancesHtml 產生重試按鈕
        const html = CharaModalView.renderAppearancesHtml(
            [99999],
            () => failMeta,
            null,
            null,
            '可可蘿'
        );
        assert(html.includes('chara-appearance-retry-btn'), 'Must render retry button on failure');
        assert(html.includes("QuestMapModule.retryCharaMetadata(this.getAttribute('data-chara-name'))"), 'Retry button must invoke retryCharaMetadata safely');

        // 4. 驗證 clearMetadataError 與重試恢復流程
        service.clearMetadataError();
        assert.strictEqual(service.hasMetadataFailed(), false);

        // Mock successful fetch on retry
        global.fetch = async () => ({
            ok: true,
            json: async () => ({ episodes: { '99999': { chapter_title: '第99章', subtitle: '已復原' } } })
        });
        const retryRes = await service.ensureMetadataLoaded();
        assert(retryRes !== null);
        assert.strictEqual(service.hasMetadataFailed(), false);
        assert.strictEqual(service.hasMetadataLoaded(), true);

        const okMeta = mockMapModule.resolveAppearanceStoryMeta(99999);
        assert.strictEqual(okMeta.label, '第99章｜已復原');
    } finally {
        global.fetch = origFetch;
    }
});

test('Test 16 — filtering and clearing search preserves retry button', () => {
    const failMeta = {
        storyId: 99999,
        path: ['其他／未編目劇情'],
        label: '名稱載入失敗（ID: 99999）',
        fullLabel: '其他／未編目劇情・名稱載入失敗（ID: 99999）',
        searchText: '99999',
        canNavigate: false,
        hasFailed: true
    };

    const html = CharaModalView.renderAppearancesHtml(
        [99999],
        () => failMeta,
        null,
        null,
        '可可蘿'
    );

    // 建立微型 DOM 容器以模擬真實瀏覽器行為
    let searchStatusText = '';
    let retryBtnExists = true;

    const fakeRetryBtn = {
        className: 'chara-appearance-retry-btn',
        getAttribute(attr) { return attr === 'data-chara-name' ? '可可蘿' : null; }
    };

    const fakeSearchStatus = {
        className: 'chara-appearance-search-status',
        get textContent() { return searchStatusText; },
        set textContent(val) { searchStatusText = val; }
    };

    const fakeDirectory = {
        querySelectorAll(selector) {
            if (selector === '.chara-appearance-item') return [{ dataset: { appearanceSearch: '99999' }, hidden: false }];
            if (selector === '.chara-appearance-group') return [{ querySelectorAll: () => [{ hidden: false }], hidden: false, open: false }];
            return [];
        },
        querySelector(selector) {
            if (selector === '.chara-appearance-search-status') return fakeSearchStatus;
            if (selector === '.chara-appearance-retry-btn') return retryBtnExists ? fakeRetryBtn : null;
            return null;
        }
    };

    const inputEl = {
        value: '測試搜尋',
        closest(sel) { return sel === '.chara-appearance-directory' ? fakeDirectory : null; }
    };

    // 1. 執行搜尋過濾：驗證 status 更新文字，但 retryBtn 不受影響
    CharaModalView.filterAppearanceDirectory(inputEl);
    assert.strictEqual(searchStatusText, '找到 0 話');
    assert.strictEqual(fakeDirectory.querySelector('.chara-appearance-retry-btn'), fakeRetryBtn, 'Retry button must remain after filtering');

    // 2. 清空搜尋：驗證 status 恢復，且 retryBtn 依然存在
    inputEl.value = '';
    CharaModalView.filterAppearanceDirectory(inputEl);
    assert.strictEqual(searchStatusText, '1 話');
    assert.strictEqual(fakeDirectory.querySelector('.chara-appearance-retry-btn'), fakeRetryBtn, 'Retry button must remain after clearing search');
});

test('Test 17 — single quotes in character name safely passed via data-chara-name attribute', () => {
    const rawCharaName = "D'Arc";
    const failMeta = {
        storyId: 99999,
        path: ['其他／未編目劇情'],
        label: '名稱載入失敗（ID: 99999）',
        fullLabel: '其他／未編目劇情・名稱載入失敗（ID: 99999）',
        searchText: '99999',
        canNavigate: false,
        hasFailed: true
    };

    const html = CharaModalView.renderAppearancesHtml(
        [99999],
        () => failMeta,
        null,
        null,
        rawCharaName
    );

    // 1. 嚴禁在 onclick 中直接以未跳脫單引號拼接 JS 字串
    assert(!html.includes("retryCharaMetadata('D'Arc')"), 'Must NOT generate invalid JavaScript syntax with raw single quotes');

    // 2. 必須使用 data-chara-name 屬性存儲轉義後的名稱
    assert(html.includes('data-chara-name="D&#39;Arc"') || html.includes('data-chara-name="D&#039;Arc"'), 'Must store escaped chara name in data-chara-name');
    assert(html.includes("QuestMapModule.retryCharaMetadata(this.getAttribute('data-chara-name'))"), 'Must delegate parameter extraction to getAttribute');

    // 3. 驗證事件處理邏輯傳入原始角色名稱
    let passedParam = null;
    const origRetry = global.QuestMapModule.retryCharaMetadata;
    global.QuestMapModule.retryCharaMetadata = (name) => {
        passedParam = name;
    };

    try {
        // 模擬 DOM 元素：瀏覽器 getAttribute 會將 HTML entity 解碼為原始字元
        const fakeButton = {
            getAttribute(attr) {
                if (attr === 'data-chara-name') return rawCharaName;
                return null;
            }
        };

        // 執行按鈕的 onclick 語意
        global.QuestMapModule.retryCharaMetadata(fakeButton.getAttribute('data-chara-name'));
        assert.strictEqual(passedParam, rawCharaName, 'Event handler must receive exact original character name including single quotes');
    } finally {
        global.QuestMapModule.retryCharaMetadata = origRetry;
    }
});

test('Test 18 — successful retry removes failure label and retry button', () => {
    let currentHtml = '';
    const fakeSection = {
        set innerHTML(val) { currentHtml = val; },
        get innerHTML() { return currentHtml; },
        querySelector: () => null,
        querySelectorAll: () => []
    };

    const fakeModal = {
        querySelector(selector) {
            if (selector === '.chara-appearance-section') return fakeSection;
            return null;
        }
    };

    const origGet = CharaModalView.getCharaModal;
    CharaModalView.getCharaModal = () => fakeModal;

    try {
        // 1. 失敗狀態渲染
        const failMeta = {
            storyId: 99999,
            path: ['其他／未編目劇情'],
            label: '名稱載入失敗（ID: 99999）',
            fullLabel: '其他／未編目劇情・名稱載入失敗（ID: 99999）',
            searchText: '99999',
            canNavigate: false,
            hasFailed: true
        };

        CharaModalView.updateAppearancesSection([99999], () => failMeta, null, null, '可可蘿');
        assert(currentHtml.includes('名稱載入失敗（ID: 99999）'), 'Must display failure label');
        assert(currentHtml.includes('chara-appearance-retry-btn'), 'Must render retry button in failed state');

        // 2. 成功狀態重新渲染
        const successMeta = {
            storyId: 99999,
            path: ['主線劇情', '第3部', '第18章'],
            label: '第1話｜新的冒險',
            fullLabel: '主線劇情・第3部・第18章・第1話｜新的冒險',
            searchText: '新的冒險 99999',
            canNavigate: true,
            hasFailed: false
        };

        CharaModalView.updateAppearancesSection([99999], () => successMeta, null, null, '可可蘿');
        assert(!currentHtml.includes('名稱載入失敗'), 'Failure label must disappear after successful resolution');
        assert(!currentHtml.includes('chara-appearance-retry-btn'), 'Retry button must disappear after successful resolution');
        assert(currentHtml.includes('第1話｜新的冒險'), 'Resolved story title must be displayed');
    } finally {
        CharaModalView.getCharaModal = origGet;
    }
});

runTests().catch(err => {
    console.error('Test execution failed:', err);
    process.exit(1);
});
