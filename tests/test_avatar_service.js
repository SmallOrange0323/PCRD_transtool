/**
 * tests/test_avatar_service.js
 * 角色頭像服務 (AvatarService) 專屬單元測試
 * 驗證 Dialogue Portrait Tier (+11 優先)、Costume Variant Identity、NPC Exact ID、
 * 特殊 Exact Mappings (1074xx, 138331, GuP)、降級階梯與 DialogueView 整合合約。
 */

const assert = require('assert');
const path = require('path');
const fs = require('fs');

// 模擬最小全域瀏覽器環境
global.window = global;

// 載入 AvatarService 源碼
require(path.join(__dirname, '../dashboard/avatar-service.js'));
const AvatarService = window.AvatarService;

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

console.log("=== Testing AvatarService & Dialogue Portrait Tier Rules ===");

// Test 1 — Ordinary original unit ID resolution
test("Test 1 — Ordinary original unit: 105813 prefers 105811 over 105831", () => {
    const ids = AvatarService.resolveDialoguePortraitIds(105813);
    assert.deepStrictEqual(ids, [105811, 105831], "105813 should resolve to [105811, 105831]");
});

// Test 2 — Ordinary costume variant base preservation
test("Test 2 — Ordinary costume variant: 107513 preserves variant base and prefers 107511 (NOT 105811)", () => {
    const ids = AvatarService.resolveDialoguePortraitIds(107513);
    assert.deepStrictEqual(ids, [107511, 107531], "107513 should resolve to [107511, 107531]");
    assert.notStrictEqual(ids[0], 105811, "Must NOT collapse variant base to original 105811");
});

// Test 3 — Another costume variant base preservation
test("Test 3 — Another costume variant: 121013 prefers 121011 (Overload Peco)", () => {
    const ids = AvatarService.resolveDialoguePortraitIds(121013);
    assert.deepStrictEqual(ids, [121011, 121031], "121013 should resolve to [121011, 121031]");
});

// Test 4 — URL Candidates fallback order
test("Test 4 — Ordinary unit candidate URLs place +11 before +31", () => {
    const candidates = AvatarService.getUrlCandidates(105901); // Kokkoro
    assert(candidates.length > 0, "Candidates should not be empty");
    const firstCandidate = candidates[0];
    assert(firstCandidate.includes("105911.webp"), `First candidate should be 105911.webp, got ${firstCandidate}`);
    
    // 驗證 +11 出現在 +31 之前
    const idx11 = candidates.findIndex(c => c.includes("105911"));
    const idx31 = candidates.findIndex(c => c.includes("105931"));
    assert(idx11 !== -1 && idx31 !== -1, "Both 105911 and 105931 must be present in candidates");
    assert(idx11 < idx31, "+11 candidate must appear before +31 candidate");
});

// Test 5 — NPC >= 190000 exact ID unchanged
test("Test 5 — NPC >= 190000 preserves exact ID with no base normalization", () => {
    const ids1 = AvatarService.resolveDialoguePortraitIds(193631);
    assert.deepStrictEqual(ids1, [193631], "NPC 193631 should resolve strictly to [193631]");
    
    const ids2 = AvatarService.resolveDialoguePortraitIds(190011);
    assert.deepStrictEqual(ids2, [190011], "NPC 190011 (Ames) should resolve strictly to [190011]");

    const html = AvatarService.getAvatarHtmlByUnitId(193631, "八斗神局長");
    assert(html.includes("icon/unit/193631.png"), "NPC HTML must use exact 193631.png");
});

// Test 6 — Special 107411 / 107412 / 107431 exact behavior
test("Test 6 — Special 107411/107412/107431 preserves exact ID", () => {
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(107411), [107411]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(107412), [107412]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(107431), [107431]);

    const html = AvatarService.getAvatarHtmlByUnitId(107411, "幻境龍后");
    assert(html.includes("icon/unit/107411.png"), "107411 must use exact 107411.png");
});

// Test 7 — Special 138331 exact override behavior (Peco Astraea override)
test("Test 7 — Special 138331 exact override preserves 138331 as first portrait ID", () => {
    const ids = AvatarService.resolveDialoguePortraitIds(138331);
    assert.strictEqual(ids[0], 138331, "138331 first portrait ID must be 138331");
    assert.deepStrictEqual(ids, [138331, 138311], "138331 should resolve to [138331, 138311]");

    const html = AvatarService.getAvatarHtmlByUnitId(138331, "貪吃佩可");
    assert(html.includes("icon/unit/138331.png"), "Initial src for 138331 must be 138331.png");
    assert(!html.includes("icon/unit/138311.png"), "Initial src for 138331 must NOT be normalized to 138311.png");
});

// Test 8 — GuP Collaboration canonical mappings
test("Test 8 — GuP collaboration (139231, 139331, 139431) preserves canonical 31 mapping first", () => {
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(139231), [139231, 139211]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(139331), [139331, 139311]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(139431), [139431, 139411]);

    const htmlMiho = AvatarService.getAvatarHtml("美穗");
    assert(htmlMiho.includes("icon/unit/139231.png"), "Miho should resolve to canonical 139231.png");
});

// Test 9 — getAvatarHtml name-based resolution prefers +11
test("Test 9 — getAvatarHtml() ordinary name-based resolution prefers +11", () => {
    const speakerAvatars = { "可可蘿": 105901 };
    const html = AvatarService.getAvatarHtml("可可蘿", speakerAvatars);
    assert(html.includes("icon/unit/105911.png"), `Ordinary name-based avatar should use 105911.png, got: ${html}`);
});

// Test 10 — getAvatarHtmlByUnitId unit-aware resolution prefers same-variant +11
test("Test 10 — getAvatarHtmlByUnitId() unit-aware resolution prefers same-variant +11", () => {
    const htmlNormal = AvatarService.getAvatarHtmlByUnitId(105801, "貪吃佩可");
    assert(htmlNormal.includes("icon/unit/105811.png"), "Normal Peco should use 105811.png");

    const htmlSummer = AvatarService.getAvatarHtmlByUnitId(107501, "貪吃佩可（夏日）");
    assert(htmlSummer.includes("icon/unit/107511.png"), "Summer Peco should use 107511.png");

    const htmlOverload = AvatarService.getAvatarHtmlByUnitId(121001, "貪吃佩可（超載）");
    assert(htmlOverload.includes("icon/unit/121011.png"), "Overload Peco should use 121011.png");
});

// Test 11 — handleError multi-step fallback chain
test("Test 11 — handleError() multi-step fallback chain (+11 remote -> +31 fallback -> placeholder)", () => {
    let currentSrc = "icon/unit/105911.png";
    let parentInnerHtml = "";
    let displayStyle = "";
    
    const mockImg = {
        dataset: {},
        get src() { return currentSrc; },
        set src(v) { currentSrc = v; },
        style: {
            set display(val) { displayStyle = val; },
            get display() { return displayStyle; }
        },
        parentNode: {
            set innerHTML(val) { parentInnerHtml = val; },
            get innerHTML() { return parentInnerHtml; }
        }
    };

    // Step 1 fail -> Step 2: So-net 00500012 +11
    AvatarService.handleError(mockImg, "可可蘿", 105901);
    assert.strictEqual(mockImg.dataset.step, "2");
    assert(mockImg.src.includes("105911.png") && mockImg.src.includes("00500012"), "Step 2 should try So-net 00500012 primary 105911");

    // Step 2 fail -> Step 3: So-net 00500015 +11
    AvatarService.handleError(mockImg, "可可蘿", 105901);
    assert.strictEqual(mockImg.dataset.step, "3");
    assert(mockImg.src.includes("105911.png") && mockImg.src.includes("00500015"), "Step 3 should try So-net 00500015 primary 105911");

    // Step 3 fail -> Step 4: EsterTion +11 .webp
    AvatarService.handleError(mockImg, "可可蘿", 105901);
    assert.strictEqual(mockImg.dataset.step, "4");
    assert(mockImg.src.includes("105911.webp") && mockImg.src.includes("estertion"), "Step 4 should try EsterTion primary 105911.webp");

    // Step 4 fail -> Step 5: local secondary +31 .png
    AvatarService.handleError(mockImg, "可可蘿", 105901);
    assert.strictEqual(mockImg.dataset.step, "5");
    assert(mockImg.src.includes("105931.png"), "Step 5 should fallback to secondary 105931.png");

    // Step 5 fail -> Step 6: EsterTion secondary +31 .webp
    AvatarService.handleError(mockImg, "可可蘿", 105901);
    assert.strictEqual(mockImg.dataset.step, "6");
    assert(mockImg.src.includes("105931.webp") && mockImg.src.includes("estertion"), "Step 6 should try EsterTion secondary 105931.webp");

    // Step 6 fail -> Final Step: hide img and show placeholder
    AvatarService.handleError(mockImg, "可可蘿", 105901);
    assert.strictEqual(mockImg.style.display, "none", "Image should be hidden on final failure");
    assert(parentInnerHtml.includes("npc-avatar-placeholder"), "Should render text placeholder");
    assert(parentInnerHtml.includes("可可"), "Placeholder text should be first 2 chars of name");
});

// Test 12 — Unknown or empty unitId fallback
test("Test 12 — Unknown/null unitId renders text placeholder", () => {
    const html1 = AvatarService.getAvatarHtml("未知路人ABC");
    assert(html1.includes("npc-avatar-placeholder"), "Unknown name should render text placeholder");
    assert(html1.includes("未知"), "Placeholder text should contain '未知'");

    const html2 = AvatarService.getAvatarHtmlByUnitId(null, "路人乙");
    assert(html2.includes("npc-avatar-placeholder"), "Null unitId without avatar mapping should render text placeholder");
});

// Test 13 — DialogueView integration: adjacent same-name different-variant dialogues
test("Test 13 — DialogueView integration: distinct unit_ids on same character name produce distinct variant avatar paths", () => {
    // 載入 StoryAssetService stub
    global.StoryAssetService = {
        getStillHtml: (s) => `<img>`,
        getBackgroundHtml: (b) => `<img>`
    };
    const DialogueView = require(path.join(__dirname, '../dashboard/dialogue-view.js'));

    const dialogueList = [
        { name: "貪吃佩可", words: "平時的佩可！", unit_id: 105813 },
        { name: "貪吃佩可", words: "夏日的佩可！", unit_id: 107513 },
        { name: "貪吃佩可", words: "超載的佩可！", unit_id: 121013 }
    ];

    const { html } = DialogueView.generateDialogueHtml({
        storyId: 2001001,
        dialogueList: dialogueList,
        speakerAvatars: { "貪吃佩可": 105801 },
        resolveRealName: (n) => n
    });

    assert(html.includes("icon/unit/105811.png"), "First bubble must render regular 105811.png");
    assert(html.includes("icon/unit/107511.png"), "Second bubble must render summer 107511.png");
    assert(html.includes("icon/unit/121011.png"), "Third bubble must render overload 121011.png");
});

console.log(`\n✅ All ${testsPassed} AvatarService & Tier 11 tests passed successfully!`);
