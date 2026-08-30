/**
 * tests/test_dialogue_view.js
 * 劇情對白視圖 (DialogueView) 單元測試
 * 驗證硬依賴 (Hard Dependency)、回歸行為與事件合約
 */

const assert = require('assert');
const path = require('path');

// 模擬最小全域環境
global.window = global;

// 注入 AvatarService 與 StoryAssetService stub
global.AvatarService = {
    getAvatarHtml: (realName, speakerAvatars) => `<img src="icon/unit/${speakerAvatars[realName] || 999999}.png" alt="${realName}">`,
    getAvatarHtmlByUnitId: (unitId, realName, speakerAvatars) => `<img src="icon/unit/${unitId}.png" alt="${realName}">`
};

global.StoryAssetService = {
    getStillHtml: (stillId, className, style) => `<img src="still/scenario/${stillId}.webp" class="${className}">`,
    getBackgroundHtml: (bgId, className, style) => `<img src="still/bg/${bgId}.webp" class="${className}">`
};

// 載入 DialogueView
const DialogueView = require(path.join(__dirname, '../dashboard/dialogue-view.js'));

let testsPassed = 0;
function test(name, fn) {
    try {
        fn();
        console.log(`  [PASS] ${name}`);
        testsPassed++;
    } catch (e) {
        console.error(`  [FAIL] ${name}:`, e);
        process.exit(1);
    }
}

console.log("=== Testing DialogueView ===");

// Test 1 — Speaker badges: order, exclusions, playable filter
test("Test 1 — Speaker badges rendering and exclusions", () => {
    let mockDisplay = "";
    let mockHtml = "";
    const badgesBarEl = {
        style: {
            set display(val) { mockDisplay = val; },
            get display() { return mockDisplay; }
        },
        set innerHTML(val) { mockHtml = val; },
        get innerHTML() { return mockHtml; }
    };

    const options = {
        speakerNames: ["旁白", "貪吃佩可", "【系統】", "凱留", "【選擇肢】1", "可可蘿", "？？？"],
        speakerAvatars: { "貪吃佩可": 105801, "凱留": 105901, "可可蘿": 105701 },
        resolveRealName: (n) => n
    };

    DialogueView.renderSpeakerBadges(badgesBarEl, options);

    assert.strictEqual(mockDisplay, "flex", "Badges bar should be set to flex");
    assert(mockHtml.includes("貪吃佩可"), "Should include 貪吃佩可");
    assert(mockHtml.includes("凱留"), "Should include 凱留");
    assert(mockHtml.includes("可可蘿"), "Should include 可可蘿");
    assert(!mockHtml.includes("旁白"), "Should exclude 旁白");
    assert(!mockHtml.includes("【系統】"), "Should exclude 【系統】");
    assert(!mockHtml.includes("【選擇肢】"), "Should exclude 【選擇肢】");
    assert(!mockHtml.includes("？？？"), "Should exclude ？？？");

    // 驗證 first-seen 順序 (佩可 -> 凱留 -> 可可蘿)
    const idxPeco = mockHtml.indexOf("貪吃佩可");
    const idxKaryl = mockHtml.indexOf("凱留");
    const idxKokkoro = mockHtml.indexOf("可可蘿");
    assert(idxPeco < idxKaryl && idxKaryl < idxKokkoro, "Badges order should be preserved");

    // 驗證無可玩角色時隱藏
    DialogueView.renderSpeakerBadges(badgesBarEl, { speakerNames: ["旁白"], speakerAvatars: {} });
    assert.strictEqual(mockDisplay, "none", "Badges bar should hide when no playable speakers");
});

// Test 2 — Normal dialogue bubble
test("Test 2 — Normal bubble markup", () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [{ name: "可可蘿", words: "主人，請用早餐。", voice: "" }],
        speakerAvatars: { "可可蘿": 105701 },
        resolveRealName: (n) => n
    });

    assert(html.includes("game-dialogue-line"), "Should have dialogue line container");
    assert(html.includes("可可蘿"), "Should have speaker name");
    assert(html.includes("主人，請用早餐。"), "Should have dialogue words");
    assert(html.includes("icon/unit/105701.png"), "Should have avatar markup");
    assert(html.includes('QuestMapModule.showCharaModal(&quot;可可蘿&quot;)'), "Should have chara modal contract");
});

// Test 3 — Voice button wiring
test("Test 3 — Voice button inline contract", () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [{ name: "凱留", words: "才、才沒有特別為你準備呢！", voice: "vo_story_1001001_001" }],
        speakerAvatars: { "凱留": 105901 },
        resolveRealName: (n) => n
    });

    assert(html.includes("dialogue-voice-btn"), "Should have voice button class");
    assert(html.includes("event.stopPropagation()"), "Should contain stopPropagation");
    assert(html.includes("QuestMapModule.playVoice('vo_story_1001001_001')"), "Should call QuestMapModule.playVoice");
});

// Test 4 — Still and background special nodes
test("Test 4 — Still and Background special nodes contract", () => {
    const { html, firstBgUrl } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [
            { type: "background", background_id: "500010" },
            { type: "still", still_id: "1000101" }
        ],
        speakerAvatars: {},
        resolveRealName: (n) => n
    });

    assert(html.includes("game-dialogue-bg-change"), "Should render bg change marker");
    assert(html.includes("500010"), "Should contain bg id");
    assert.strictEqual(firstBgUrl, "https://redive.estertion.win/bg/jpg/500010.jpg", "Should capture firstBgUrl");
    assert(html.includes("game-dialogue-still"), "Should render still wrapper");
    assert(html.includes("QuestMapModule.openStillPopup(event)"), "Should have openStillPopup contract");
    assert(html.includes("still/scenario/1000101.webp"), "Should render still image tag");
});

// Test 5 — Special avatar override for 13830*
test("Test 5 — Special avatar override for story 13830*", () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1383001,
        dialogueList: [{ name: "貪吃佩可", words: "好香的味道！" }],
        speakerAvatars: { "貪吃佩可": 105801 },
        resolveRealName: (n) => n
    });

    assert(html.includes("icon/unit/138331.png"), "Story 13830* should override Peco avatar to 138331");
});

// Test 6 — Player-name substitution and HTML escaping
test("Test 6 — Player-name substitution & escaping", () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [{ name: "<危險人物>", words: "你好，{player}！或者叫你{0}？\n換行測試 & <標籤>" }],
        speakerAvatars: {},
        resolveRealName: (n) => n
    });

    assert(html.includes("&lt;危險人物&gt;"), "Speaker name must be escaped");
    assert(html.includes("你好，佑樹！"), "{player} must be replaced by 佑樹");
    assert(html.includes("或者叫你佑樹？"), "{0} must be replaced by 佑樹");
    assert(html.includes("<br>換行測試 &amp; &lt;標籤&gt;"), "Newline converted to <br> and HTML entities escaped");
});

// Test 7 — Ending still auto-append
test("Test 7 — Ending still auto-append when no still in dialogue", () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [{ name: "佑樹", words: "......" }],
        currentStoryObj: { still_id: "999001" },
        speakerAvatars: {},
        resolveRealName: (n) => n
    });

    assert(html.includes("✨ 劇情插畫"), "Should append ending still label");
    assert(html.includes("still/scenario/999001.webp"), "Should render ending still image");
    assert(html.includes("QuestMapModule.openStillPopup(event)"), "Ending still must have openStillPopup contract");
});

// Test 8 — Error UI retry contract
test("Test 8 — Error UI retry contract", () => {
    let errorHtml = "";
    const containerEl = {
        set innerHTML(val) { errorHtml = val; },
        get innerHTML() { return errorHtml; }
    };

    DialogueView.renderError(containerEl, 1001002);

    assert(errorHtml.includes("⚠️ 台詞文本尚未下載"), "Should render error title");
    assert(errorHtml.includes("QuestMapModule.loadDialogue(1001002)"), "Should include reload button calling QuestMapModule.loadDialogue(storyId)");
});

// Test 9 — Hard dependency enforcement on AvatarService
test("Test 9 — AvatarService hard dependency (fails loudly if missing)", () => {
    const originalService = global.AvatarService;
    global.AvatarService = undefined;
    global.window.AvatarService = undefined;

    let threw = false;
    try {
        DialogueView.generateDialogueHtml({
            storyId: 1001001,
            dialogueList: [{ name: "可可蘿", words: "測試" }],
            speakerAvatars: { "可可蘿": 105701 },
            resolveRealName: (n) => n
        });
    } catch (e) {
        threw = true;
    } finally {
        global.AvatarService = originalService;
        global.window.AvatarService = originalService;
    }

    assert(threw, "generateDialogueHtml must fail loudly when AvatarService is missing");
});

// Test 10 — Hard dependency enforcement on StoryAssetService
test("Test 10 — StoryAssetService hard dependency (fails loudly if missing)", () => {
    const originalService = global.StoryAssetService;
    global.StoryAssetService = undefined;
    global.window.StoryAssetService = undefined;

    let threw = false;
    try {
        DialogueView.generateDialogueHtml({
            storyId: 1001001,
            dialogueList: [{ type: "still", still_id: "1000101" }],
            speakerAvatars: {},
            resolveRealName: (n) => n
        });
    } catch (e) {
        threw = true;
    } finally {
        global.StoryAssetService = originalService;
        global.window.StoryAssetService = originalService;
    }

    assert(threw, "generateDialogueHtml must fail loudly when StoryAssetService is missing");
});

console.log(`\n✅ All ${testsPassed} DialogueView tests passed successfully!`);
