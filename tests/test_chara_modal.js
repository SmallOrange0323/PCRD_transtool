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

let passed = 0;
function test(name, fn) {
    try {
        fn();
        console.log(`  [PASS] ${name}`);
        passed++;
    } catch (error) {
        console.error(`  [FAIL] ${name}:`, error);
        process.exit(1);
    }
}

console.log('=== Testing CharaModalView avatar resolution ===');

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
    global.window.StoryDataService = {
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

    // Case 4: empty titles fallback to '劇情 {storyId}'
    const res4 = mockMapModule.resolveAppearanceStoryMeta(10004);
    assert.deepStrictEqual(res4.path, ['其他／未編目劇情']);
    assert.strictEqual(res4.label, '劇情 10004');
    assert.strictEqual(res4.canNavigate, false);

    // Case 5: no official metadata at all -> '無法識別'
    const res5 = mockMapModule.resolveAppearanceStoryMeta(99999);
    assert.deepStrictEqual(res5.path, ['無法識別']);
    assert.strictEqual(res5.label, 'ID: 99999');
    assert.strictEqual(res5.fullLabel, '無法識別・ID: 99999');
    assert.strictEqual(res5.searchText, 'ID 99999');
    assert.strictEqual(res5.sortKey, '99-000099999');
    assert.strictEqual(res5.canNavigate, false);
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

console.log(`\n✅ All ${passed} CharaModalView tests passed successfully!`);
