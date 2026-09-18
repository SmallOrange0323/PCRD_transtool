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
    realityAvatarMap: {
        "佩可": 105831,
        "貪吃佩可": 105831,
        "可可蘿": 105932
    },
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
    assert(!mockHtml.includes("QuestMapModule.showCharaModal(&quot;貪吃佩可&quot;, 105801)"), "Legacy/name-only badge must not pass a unit_id");

    // 驗證 first-seen 順序 (佩可 -> 凱留 -> 可可蘿)
    const idxPeco = mockHtml.indexOf("貪吃佩可");
    const idxKaryl = mockHtml.indexOf("凱留");
    const idxKokkoro = mockHtml.indexOf("可可蘿");
    assert(idxPeco < idxKaryl && idxKaryl < idxKokkoro, "Badges order should be preserved");

    // 驗證無可玩角色時隱藏
    DialogueView.renderSpeakerBadges(badgesBarEl, { speakerNames: ["旁白"], speakerAvatars: {} });
    assert.strictEqual(mockDisplay, "none", "Badges bar should hide when no playable speakers");
});

// Test 1B — Explicit dialogue unit_id bypasses legacy speakerAvatars gate
test("Test 1B — Explicit unit_id renders badge without name registry entry", () => {
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

    DialogueView.renderSpeakerBadges(badgesBarEl, {
        speakerNames: ["秘書"],
        dialogueList: [{ name: "秘書", unit_id: 6112 }],
        speakerAvatars: {},
        resolveRealName: (n) => n
    });

    assert.strictEqual(mockDisplay, "flex", "Explicit-ID speaker badge should be visible");
    assert(mockHtml.includes("icon/unit/6112.png"), "Badge must use exact unit_id 6112");
    assert(mockHtml.includes("QuestMapModule.showCharaModal(&quot;秘書&quot;, 6112)"), "Explicit badge modal must receive unit_id 6112");
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

// Test 3 — Voice button wiring and DOM contract
test("Test 3 — Voice button DOM contract and decoupling", () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [{ name: "凱留", words: "才、才沒有特別為你準備呢！", voice: "vo_story_1001001_001" }],
        speakerAvatars: { "凱留": 105901 },
        resolveRealName: (n) => n
    });

    assert(html.includes("dialogue-voice-btn"), "Should have voice button class");
    assert(html.includes("event.stopPropagation()"), "Should contain stopPropagation");
    assert(html.includes("QuestMapModule.playVoice('vo_story_1001001_001')"), "Should call QuestMapModule.playVoice");

    // DOM contract 嚴格驗證：
    // game-dialogue-speaker-wrap
    // ├── game-dialogue-speaker
    // └── dialogue-voice-btn
    assert(html.includes("game-dialogue-speaker-wrap"), "Must have game-dialogue-speaker-wrap container");

    // 驗證語音按鈕與人名是平級兄弟結構，且按鈕不得被包在 game-dialogue-speaker 內部
    const speakerTagMatch = html.match(/<span class="game-dialogue-speaker"[^>]*>([\s\S]*?)<\/span>/);
    assert(speakerTagMatch, "Must find isolated game-dialogue-speaker element");
    const speakerContent = speakerTagMatch[1];
    assert(!speakerContent.includes("dialogue-voice-btn"), "dialogue-voice-btn must NOT be nested inside game-dialogue-speaker");
    assert(!speakerContent.includes("playVoice"), "playVoice must NOT be triggered from within speaker element");

    // 驗證 wrap 結構內依序包含 speaker 與 voice-btn
    const wrapRegex = /<div class="game-dialogue-speaker-wrap">[\s\S]*?<span class="game-dialogue-speaker"[\s\S]*?<\/span>[\s\S]*?<button[^>]*class="dialogue-voice-btn"/;
    assert(wrapRegex.test(html), "DOM hierarchy contract violated: wrap must contain sibling speaker then voice button");
});

// Test 4 — Still and background special nodes regression
test("Test 4 — Background hidden and Still rendering contract in full text view", () => {
    const { html, firstBgUrl } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [
            { type: "background", bg_id: "500140" },
            { name: "佩可", words: "好吃到要融化了～", voice: "vo_story_1001001_001" },
            { type: "still", still_id: "1000101" }
        ],
        speakerAvatars: { "佩可": 105801 },
        resolveRealName: (n) => n
    });

    // 遊戲實機全文模式不顯示「場景切換」與背景圖
    assert(!html.includes("場景切換"), "Should NOT render 場景切換 label in full text view");
    assert(!html.includes("bg_500140"), "Should NOT render background image in full text view");
    assert(!html.includes("game-dialogue-bg-change"), "Should NOT render bg change marker");
    assert.strictEqual(firstBgUrl, "", "firstBgUrl should be empty string");

    // 仍完整包含對白與角色資訊
    assert(html.includes("佩可"), "Should still include dialogue speaker");
    assert(html.includes("好吃到要融化了～"), "Should still include dialogue line");

    // 劇情插畫 CG 節點仍正常渲染
    assert(html.includes("game-dialogue-still"), "Should render still wrapper");
    assert(html.includes("QuestMapModule.openStillPopup(event)"), "Should have openStillPopup contract");
    assert(html.includes("still/scenario/1000101.webp"), "Should render still image tag");
});

// Test 5A — Reality story explicit unit_id wins unconditionally over realityAvatarMap
test("Test 5A — Reality story explicit unit_id wins unconditionally over realityAvatarMap", () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 2213104,
        dialogueList: [{ name: "可可蘿", words: "主人，早安。", unit_id: 105913 }],
        speakerAvatars: { "可可蘿": 105901 },
        resolveRealName: (n) => n
    });

    assert(html.includes("icon/unit/105913.png"), "Explicit unit_id 105913 must be rendered");
    assert(html.includes('QuestMapModule.showCharaModal(&quot;可可蘿&quot;, 105913)'), "Explicit unit_id must be forwarded to modal click");
    assert(!html.includes("105932.png"), "Must NOT rewrite explicit 105913 to realityAvatarMap 105932");
});

// Test 5B — Story 13830* explicit unit_id wins unconditionally over 138331 override
test("Test 5B — Story 13830* explicit unit_id wins unconditionally over 138331 override", () => {
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1383001,
        dialogueList: [{ name: "貪吃佩可", words: "這是我本來的樣子！", unit_id: 105812 }],
        speakerAvatars: { "貪吃佩可": 105801 },
        resolveRealName: (n) => n
    });

    assert(html.includes("icon/unit/105812.png"), "Explicit unit_id 105812 must be rendered");
    assert(html.includes('QuestMapModule.showCharaModal(&quot;貪吃佩可&quot;, 105812)'), "Explicit unit_id must be forwarded for special variants");
    assert(!html.includes("138331.png"), "Must NOT rewrite explicit 105812 to 138331");
});

// Test 5C — Inference compatibility remains when explicit unit_id is absent
test("Test 5C — Inference compatibility remains when explicit unit_id is absent", () => {
    // 1. Reality story without explicit unit_id falls back to realityAvatarMap
    const { html: realityHtml } = DialogueView.generateDialogueHtml({
        storyId: 2213104,
        dialogueList: [{ name: "可可蘿", words: "現實中的相遇。" }],
        speakerAvatars: { "可可蘿": 105901 },
        resolveRealName: (n) => n
    });
    assert(realityHtml.includes("icon/unit/105932.png"), "Reality story without explicit ID must fall back to realityAvatarMap 105932");

    // 2. Story 13830* without explicit unit_id falls back to 138331
    const { html: pecoHtml } = DialogueView.generateDialogueHtml({
        storyId: 1383001,
        dialogueList: [{ name: "貪吃佩可", words: "好香的味道！" }],
        speakerAvatars: { "貪吃佩可": 105801 },
        resolveRealName: (n) => n
    });
    assert(pecoHtml.includes("icon/unit/138331.png"), "Story 13830* without explicit ID must fall back to 138331");
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

// Test 11 — normalizePlayerName helper across dialogue and summary texts
test("Test 11 — normalizePlayerName helper (player placeholder -> 佑樹)", () => {
    assert(typeof DialogueView.normalizePlayerName === "function", "normalizePlayerName must be a function on DialogueView");

    // 基礎佔位符替換
    assert.strictEqual(DialogueView.normalizePlayerName("{player}，早安！"), "佑樹，早安！");
    assert.strictEqual(DialogueView.normalizePlayerName("去找{0}吧。"), "去找佑樹吧。");
    assert.strictEqual(DialogueView.normalizePlayerName("來到(O)家的貪吃佩可……"), "來到佑樹家的貪吃佩可……");
    assert.strictEqual(DialogueView.normalizePlayerName("來到(o)家的貪吃佩可……"), "來到佑樹家的貪吃佩可……");
    assert.strictEqual(DialogueView.normalizePlayerName("來到（O）家的貪吃佩可……"), "來到佑樹家的貪吃佩可……");
    assert.strictEqual(DialogueView.normalizePlayerName("來到（o）家的貪吃佩可……"), "來到佑樹家的貪吃佩可……");
    assert.strictEqual(DialogueView.normalizePlayerName("多個佔位符：{player}與{0}還有(O)"), "多個佔位符：佑樹與佑樹還有佑樹");

    // 防禦邊界值
    assert.strictEqual(DialogueView.normalizePlayerName(""), "");
    assert.strictEqual(DialogueView.normalizePlayerName(null), "");
    assert.strictEqual(DialogueView.normalizePlayerName(undefined), "");

    // 整合驗證：generateDialogueHtml 中包含 (O) 與 {player} 的對白
    const { html } = DialogueView.generateDialogueHtml({
        storyId: 1001001,
        dialogueList: [
            { name: "佩可", words: "來到(O)家的貪吃佩可向{player}問好！" }
        ],
        speakerAvatars: { "佩可": 105801 },
        resolveRealName: (n) => n
    });
    assert(html.includes("來到佑樹家的貪吃佩可向佑樹問好！"), "generateDialogueHtml must render normalized player name");
    assert(!html.includes("(O)"), "Must not contain (O)");
    assert(!html.includes("{player}"), "Must not contain {player}");
});

console.log(`\n✅ All ${testsPassed} DialogueView tests passed successfully!`);
