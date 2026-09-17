/**
 * 玩家名稱 placeholder 顯示/身份分離回歸測試。
 *
 * 契約：
 * - {0} 在 UI 顯示為「佑樹」。
 * - avatar / modal / unit_id 查找仍使用原始 {0} identity key。
 * - 沒有 explicit unit_id 時，既有 npc_avatars / speakerAvatars fallback 仍可命中 {0}。
 */

const assert = require('assert');
const path = require('path');

global.window = global;

let exactCalls = [];
let fallbackCalls = [];

global.AvatarService = {
    realityAvatarMap: {},
    getAvatarHtmlByUnitId(unitId, realName, speakerAvatars) {
        exactCalls.push({ unitId, realName, speakerAvatars });
        return `<img src="icon/unit/${String(unitId).padStart(6, '0')}.png" data-real-name="${realName}">`;
    },
    getAvatarHtml(realName, speakerAvatars) {
        fallbackCalls.push({ realName, speakerAvatars });
        const unitId = speakerAvatars && speakerAvatars[realName];
        return unitId
            ? `<img src="icon/unit/${String(unitId).padStart(6, '0')}.png" data-real-name="${realName}">`
            : `<div data-fallback-name="${realName}">${realName}</div>`;
    }
};

global.StoryAssetService = {
    getStillHtml: () => '',
    getBackgroundHtml: () => ''
};

const DialogueView = require(path.join(__dirname, '../dashboard/dialogue-view.js'));
global.DialogueView = DialogueView;

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
    exactCalls = [];
    fallbackCalls = [];
    try {
        fn();
        console.log(`  [PASS] ${name}`);
        passed++;
    } catch (error) {
        console.error(`  [FAIL] ${name}:`, error);
        process.exit(1);
    }
}

console.log('=== Testing player display / identity separation ===');

test('Test 1 — {0} displays as 佑樹 while exact avatar keeps raw identity', () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [{ name: '{0}', words: '你好。', unit_id: 100011 }],
        speakerAvatars: { '{0}': 100011 },
        resolveRealName: (name) => name
    });

    assert(html.includes('佑樹'), 'Speaker display should normalize {0} to 佑樹');
    assert(html.includes('icon/unit/100011.png'), 'Explicit unit_id avatar should render');
    assert(html.includes('QuestMapModule.showCharaModal(&quot;{0}&quot;)'), 'Modal identity must remain raw {0}');
    assert.strictEqual(exactCalls.length, 1);
    assert.strictEqual(exactCalls[0].unitId, 100011);
    assert.strictEqual(exactCalls[0].realName, '{0}', 'Exact avatar lookup must retain raw identity');
});

test('Test 2 — name-based fallback still resolves speakerAvatars[{0}]', () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [{ name: '{0}', words: '沒有 explicit unit_id。' }],
        speakerAvatars: { '{0}': 100011 },
        resolveRealName: (name) => name
    });

    assert(html.includes('佑樹'));
    assert(html.includes('icon/unit/100011.png'));
    assert.strictEqual(exactCalls.length, 0);
    assert.strictEqual(fallbackCalls.length, 1);
    assert.strictEqual(fallbackCalls[0].realName, '{0}', 'Fallback lookup must use raw {0}, not 佑樹');
});

test('Test 3 — speaker badge shows display name but preserves raw identity lookup', () => {
    let html = '';
    const badgesBar = {
        style: { display: '' },
        set innerHTML(value) { html = value; },
        get innerHTML() { return html; }
    };

    DialogueView.renderSpeakerBadges(badgesBar, {
        speakerNames: ['{0}'],
        speakerAvatars: { '{0}': 100011 },
        resolveRealName: (name) => name
    });

    assert.strictEqual(badgesBar.style.display, 'flex');
    assert(html.includes('title="佑樹"'), 'Badge tooltip should use display name');
    assert(html.includes('icon/unit/100011.png'), 'Badge avatar should still resolve from raw key');
    assert(html.includes('QuestMapModule.showCharaModal(&quot;{0}&quot;)'), 'Badge click should preserve raw identity');
    assert.strictEqual(fallbackCalls[0].realName, '{0}');
});

test('Test 4 — modal title displays 佑樹 while exact identity remains {0}', () => {
    global.QuestMapModule.currentDialogueList = [
        { name: '{0}', words: '主人公台詞', unit_id: 100011 }
    ];

    const originalGetCharaModal = CharaModalView.getCharaModal;
    const fakeModal = {
        innerHTML: '',
        classList: { add() {} }
    };
    CharaModalView.getCharaModal = () => fakeModal;

    let modalExactCall = null;
    const avatarService = {
        getAvatarHtmlByUnitId(unitId, realName) {
            modalExactCall = { unitId, realName };
            return `<img data-unit-id="${unitId}" data-real-name="${realName}">`;
        },
        getAvatarHtml() {
            return '<div>fallback</div>';
        }
    };

    try {
        CharaModalView.renderModal({
            realCharaName: '{0}',
            profile: null,
            appearances: [],
            speakerAvatars: { '{0}': 100011 },
            avatarService,
            resolveStoryLabel: null,
            escapeHtml: (text) => String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
        });

        assert(fakeModal.innerHTML.includes('角色檔案：佑樹'), 'Modal title should normalize only the display text');
        assert(!fakeModal.innerHTML.includes('角色檔案：{0}'), 'Raw placeholder must not leak into modal title');
        assert(modalExactCall, 'Modal should use exact current-dialogue unit_id');
        assert.strictEqual(modalExactCall.unitId, 100011);
        assert.strictEqual(modalExactCall.realName, '{0}', 'Modal exact lookup must keep raw identity');
    } finally {
        CharaModalView.getCharaModal = originalGetCharaModal;
        global.QuestMapModule.currentDialogueList = [];
    }
});

console.log(`\n✅ All ${passed} player display / identity tests passed successfully!`);
