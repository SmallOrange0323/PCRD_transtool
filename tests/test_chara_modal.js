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

console.log(`\n✅ All ${passed} CharaModalView tests passed successfully!`);
