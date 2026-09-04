/**
 * tests/test_avatar_service.js
 * 角色頭像服務 (AvatarService) 專屬單元測試 — Phase 6 Exact-ID-First 規範
 * 驗證：
 * 1. 顯式對白 unit_id 走 Exact-ID-First 渲染，絕不進行 base+11/31 規整化
 * 2. 11 個高風險 fixtures 覆蓋 (133118, 101421, 125821, 106914, 105812, 105913, 106012, 106412, 106831, 107331, 107031)
 * 3. 3 個 placeholder-only identities 覆蓋 (105921, 106913, 190813)
 * 4. 未登錄 ID 嚴格 Fail-Closed 顯示文字佔位符
 * 5. 顯式對白專用 handleExactDialogueError 阻斷外部 CDN
 * 6. 通用 / 名稱推斷 UI 向後相容 (getAvatarHtml prefers +11)
 * 7. DialogueView 整合合約（exact active 與 placeholder-only）
 * 8. Special Stories 優先級 (Explicit ID > Story Overrides)
 * 9. Manifest 網路失敗非致命 Fail-Closed 合約 (Never Rejects, 0 CDN, 0 base guessing)
 * 10. 單次 Fetch 快取與並發調用合約 (Fetch count == 1)
 */

const assert = require('assert');
const path = require('path');
const fs = require('fs');

// 模擬最小全域瀏覽器環境
global.window = global;

// 載入 AvatarService 源碼 (內部會自動於 Node 環境載入 avatar_assets.json)
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

async function asyncTest(name, fn) {
    try {
        await fn();
        console.log(`  [PASS] ${name}`);
        testsPassed++;
    } catch (e) {
        console.error(`  [FAIL] ${name}:`, e);
        process.exit(1);
    }
}

(async () => {
console.log("=== Testing AvatarService Phase 6: Exact-ID-First Rules ===");

// Test 1 — Ordinary canonical unit: 105813 strictly preserves exact 105813 (NO base+11 normalization)
test("Test 1 — Ordinary canonical unit: 105813 strictly preserves exact 105813", () => {
    const resolved = AvatarService.resolveExactDialoguePortrait(105813);
    assert(resolved, "resolveExactDialoguePortrait(105813) must not be null");
    assert.strictEqual(resolved.status, "active", "105813 must be active in manifest");
    assert.strictEqual(resolved.filename, "105813.png", "105813 filename must be 105813.png");

    const ids = AvatarService.resolveDialoguePortraitIds(105813);
    assert.deepStrictEqual(ids, [105813], "105813 must resolve strictly to [105813], NOT [105811, 105831]");

    const html = AvatarService.getAvatarHtmlByUnitId(105813, "貪吃佩可");
    assert(html.includes("icon/unit/105813.png"), "HTML must point to exact icon/unit/105813.png");
    assert(!html.includes("105811.png"), "HTML must NOT be normalized to 105811.png");
    assert(html.includes("AvatarService.handleExactDialogueError"), "Must use handleExactDialogueError for explicit dialogue rows");
});

// Test 2 — Costume variants preserve exact identity (107512 Summer Peco & 121011 Overload Peco)
test("Test 2 — Costume variants preserve exact identity (107512 & 121011)", () => {
    const resolvedSummer = AvatarService.resolveExactDialoguePortrait(107512);
    assert.strictEqual(resolvedSummer.status, "active");
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(107512), [107512]);
    const htmlSummer = AvatarService.getAvatarHtmlByUnitId(107512, "貪吃佩可（夏日）");
    assert(htmlSummer.includes("icon/unit/107512.png"), "Summer Peco must render exact 107512.png");
    assert(!htmlSummer.includes("107511.png"), "Summer Peco 107512 must NOT be normalized to 107511.png");

    const resolvedOverload = AvatarService.resolveExactDialoguePortrait(121011);
    assert.strictEqual(resolvedOverload.status, "active");
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(121011), [121011]);
    const htmlOverload = AvatarService.getAvatarHtmlByUnitId(121011, "貪吃佩可（超載）");
    assert(htmlOverload.includes("icon/unit/121011.png"), "Overload Peco must render exact 121011.png");
});

// Test 3 — 11 High-Risk Fixtures Exact-ID Coverage
test("Test 3 — 11 High-Risk Fixtures Exact-ID Coverage", () => {
    const highRiskFixtures = [
        { id: 133118, name: "愛爾梅達利亞" },
        { id: 101421, name: "胡桃" },
        { id: 125821, name: "伊莉亞" },
        { id: 106914, name: "矛依未" },
        { id: 105812, name: "貪吃佩可" },
        { id: 105913, name: "可可蘿" },
        { id: 106012, name: "凱留" },
        { id: 106412, name: "優衣" },
        { id: 106831, name: "霸瞳皇帝" },
        { id: 107331, name: "拉比林斯達" },
        { id: 107031, name: "似似花" }
    ];

    for (const fixture of highRiskFixtures) {
        const resolved = AvatarService.resolveExactDialoguePortrait(fixture.id);
        assert(resolved, `Fixture ${fixture.id} must be resolvable`);
        assert.strictEqual(resolved.status, "active", `Fixture ${fixture.id} must be active`);
        assert.strictEqual(resolved.filename, `${fixture.id}.png`, `Fixture ${fixture.id} filename must match`);

        const ids = AvatarService.resolveDialoguePortraitIds(fixture.id);
        assert.deepStrictEqual(ids, [fixture.id], `Fixture ${fixture.id} must resolve to [${fixture.id}]`);

        const html = AvatarService.getAvatarHtmlByUnitId(fixture.id, fixture.name);
        assert(html.includes(`icon/unit/${fixture.id}.png`), `Fixture ${fixture.id} HTML must reference ${fixture.id}.png`);
        assert(html.includes("AvatarService.handleExactDialogueError"), `Fixture ${fixture.id} must wire handleExactDialogueError`);
    }
});

// Test 4 — 3 Verified Placeholder-Only Identities (105921, 106913, 190813)
test("Test 4 — 3 Verified Placeholder-Only Identities (105921, 106913, 190813)", () => {
    const placeholders = [
        { id: 105921, name: "可可蘿" },
        { id: 106913, name: "矛依未" },
        { id: 190813, name: "拉吉拉吉" }
    ];

    for (const p of placeholders) {
        const resolved = AvatarService.resolveExactDialoguePortrait(p.id);
        assert(resolved, `Placeholder identity ${p.id} must be recognized`);
        assert.strictEqual(resolved.status, "placeholder_only", `Identity ${p.id} must have status 'placeholder_only'`);
        assert.strictEqual(resolved.filename, null, `Identity ${p.id} must have null filename`);

        const ids = AvatarService.resolveDialoguePortraitIds(p.id);
        assert.deepStrictEqual(ids, [p.id], `Identity ${p.id} must preserve exact id in candidate list`);

        const html = AvatarService.getAvatarHtmlByUnitId(p.id, p.name);
        assert(!html.includes("<img"), `Placeholder identity ${p.id} must NOT emit an <img> tag`);
        assert(html.includes("npc-avatar-placeholder"), `Identity ${p.id} must render text placeholder`);
        assert(html.includes(p.name.substring(0, 2)), `Identity ${p.id} placeholder text should match name prefix`);
    }
});

// Test 5 — Unmanifested ID Fail-Closed to Placeholder
test("Test 5 — Unmanifested ID Fail-Closed to Placeholder", () => {
    const unmanifestedId = 999888;
    const resolved = AvatarService.resolveExactDialoguePortrait(unmanifestedId, { warnIfAbsent: false });
    assert(resolved, "Unmanifested ID should resolve to placeholder object");
    assert.strictEqual(resolved.status, "unknown_placeholder", "Status must be unknown_placeholder");
    assert.strictEqual(resolved.filename, null, "Filename must be null");

    const html = AvatarService.getAvatarHtmlByUnitId(unmanifestedId, "神秘人物", {});
    assert(!html.includes("<img"), "Unmanifested ID must NOT emit <img> tag");
    assert(html.includes("npc-avatar-placeholder"), "Unmanifested ID must render text placeholder");
    assert(html.includes("神秘"), "Placeholder should use character name initials");
});

// Test 6 — handleExactDialogueError Fail-Closed Contract (No CDN retry)
test("Test 6 — handleExactDialogueError Fail-Closed Contract (No CDN retry)", () => {
    let currentSrc = "icon/unit/105813.png";
    let displayStyle = "";
    let parentInnerHtml = "";

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

    AvatarService.handleExactDialogueError(mockImg, "貪吃佩可", 105813);
    assert.strictEqual(displayStyle, "none", "Image element must be hidden immediately");
    assert(parentInnerHtml.includes("npc-avatar-placeholder"), "Parent element must be replaced by text placeholder");
    assert(parentInnerHtml.includes("貪吃"), "Placeholder text must contain name prefix");
    assert.strictEqual(currentSrc, "icon/unit/105813.png", "Must NOT modify img.src to retry remote CDNs");
});

// Test 7 — Generic Name-Based Resolution (Inferred UI preserves +11 preference)
test("Test 7 — Generic Name-Based Resolution preserves +11 preference", () => {
    const defaultIds = AvatarService.resolveDefaultPortraitIds(105901);
    assert.deepStrictEqual(defaultIds, [105911, 105931], "Default portrait IDs for 105901 must be [105911, 105931]");

    const speakerAvatars = { "可可蘿": 105901 };
    const html = AvatarService.getAvatarHtml("可可蘿", speakerAvatars);
    assert(html.includes("icon/unit/105911.png"), `Ordinary name-based avatar should use 105911.png, got: ${html}`);
    assert(html.includes("AvatarService.handleError"), "Generic avatar HTML should wire generic handleError");
});

// Test 8 — handleError multi-step fallback chain for generic UI
test("Test 8 — handleError() multi-step fallback chain (+11 remote -> +31 fallback -> placeholder)", () => {
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

// Test 9 — NPC >= 190000 & Special Characters
test("Test 9 — NPC >= 190000 & Special Characters exact behavior", () => {
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(193631), [193631]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(190011), [190011]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(107411), [107411]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(107412), [107412]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(107431), [107431]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(138331), [138331, 138311]);
    assert.deepStrictEqual(AvatarService.resolveDialoguePortraitIds(139231), [139231]);
});

// Test 10 — Unknown or empty unitId fallback
test("Test 10 — Unknown or empty unitId fallback", () => {
    const html1 = AvatarService.getAvatarHtml("未知路人ABC");
    assert(html1.includes("npc-avatar-placeholder"), "Unknown name should render text placeholder");
    assert(html1.includes("未知"), "Placeholder text should contain '未知'");

    const html2 = AvatarService.getAvatarHtmlByUnitId(null, "路人乙");
    assert(html2.includes("npc-avatar-placeholder"), "Null unitId should render text placeholder");
});

// Test 11 — DialogueView integration: adjacent distinct dialogue unit_ids & placeholder_only
test("Test 11 — DialogueView integration: distinct unit_ids on same character name produce distinct variant avatar paths", () => {
    // 載入 StoryAssetService stub
    global.StoryAssetService = {
        getStillHtml: (s) => `<img>`,
        getBackgroundHtml: (b) => `<img>`
    };
    const DialogueView = require(path.join(__dirname, '../dashboard/dialogue-view.js'));

    const dialogueList = [
        { name: "貪吃佩可", words: "平時的佩可！", unit_id: 105813 },
        { name: "貪吃佩可", words: "夏日的佩可！", unit_id: 107512 },
        { name: "貪吃佩可", words: "超載的佩可！", unit_id: 121011 },
        { name: "可可蘿", words: "特殊形態可可蘿", unit_id: 105921 }
    ];

    const { html } = DialogueView.generateDialogueHtml({
        storyId: 2001001,
        dialogueList: dialogueList,
        speakerAvatars: { "貪吃佩可": 105801, "可可蘿": 105901 },
        resolveRealName: (n) => n
    });

    assert(html.includes("icon/unit/105813.png"), "First bubble must render exact 105813.png");
    assert(html.includes("icon/unit/107512.png"), "Second bubble must render summer exact 107512.png");
    assert(html.includes("icon/unit/121011.png"), "Third bubble must render overload exact 121011.png");
    assert(!html.includes("105811.png"), "Must NOT rewrite 105813 to 105811");
    assert(!html.includes("107511.png"), "Must NOT rewrite 107512 to 107511");

    // 驗證 105921 (placeholder_only) 在 DialogueView 中直接輸出文字佔位符，無 <img>
    assert(html.includes("npc-avatar-placeholder"), "Fourth bubble (105921) must render text placeholder");
});

// Test 12 — DialogueView Special Stories: Explicit ID wins over realityAvatarMap & 13830* overrides
test("Test 12 — DialogueView Special Stories: Explicit ID wins unconditionally over story overrides", () => {
    const DialogueView = require(path.join(__dirname, '../dashboard/dialogue-view.js'));

    // A. Reality story with explicit unit_id 105913 (realityAvatarMap would want 105932)
    const { html: realityExplicitHtml } = DialogueView.generateDialogueHtml({
        storyId: 2213104,
        dialogueList: [{ name: "可可蘿", words: "主人，早安。", unit_id: 105913 }],
        speakerAvatars: { "可可蘿": 105901 },
        resolveRealName: (n) => n
    });
    assert(realityExplicitHtml.includes("icon/unit/105913.png"), "Reality story explicit unit_id 105913 must render exact 105913.png");
    assert(!realityExplicitHtml.includes("105932.png"), "Reality story explicit unit_id must NOT be overridden by realityAvatarMap 105932");

    // B. 13830* story with explicit unit_id 105812 (story override would want 138331)
    const { html: pecoExplicitHtml } = DialogueView.generateDialogueHtml({
        storyId: 1383001,
        dialogueList: [{ name: "貪吃佩可", words: "這是我本來的樣子！", unit_id: 105812 }],
        speakerAvatars: { "貪吃佩可": 105801 },
        resolveRealName: (n) => n
    });
    assert(pecoExplicitHtml.includes("icon/unit/105812.png"), "Story 13830* explicit unit_id 105812 must render exact 105812.png");
    assert(!pecoExplicitHtml.includes("138331.png"), "Story 13830* explicit unit_id must NOT be overridden by 138331");

    // C. Reality story with NO explicit unit_id preserves realityAvatarMap fallback
    const { html: realityFallbackHtml } = DialogueView.generateDialogueHtml({
        storyId: 2213104,
        dialogueList: [{ name: "可可蘿", words: "現實相遇。" }],
        speakerAvatars: { "可可蘿": 105901 },
        resolveRealName: (n) => n
    });
    assert(realityFallbackHtml.includes("icon/unit/105932.png"), "Reality story without explicit ID must fall back to realityAvatarMap 105932");

    // D. 13830* story with NO explicit unit_id preserves 138331 fallback
    const { html: pecoFallbackHtml } = DialogueView.generateDialogueHtml({
        storyId: 1383001,
        dialogueList: [{ name: "貪吃佩可", words: "好香的味道！" }],
        speakerAvatars: { "貪吃佩可": 105801 },
        resolveRealName: (n) => n
    });
    assert(pecoFallbackHtml.includes("icon/unit/138331.png"), "Story 13830* without explicit ID must fall back to 138331");
});

// Test 13 — Manifest fetch failure: non-fatal, safe resolution, fails closed to placeholder
await asyncTest("Test 13 — Manifest fetch failure: non-fatal, safe resolution, fails closed to placeholder", async () => {
    const savedMap = new Map(AvatarService.manifestMap);
    const savedLoaded = AvatarService.manifestLoaded;
    const savedUnavailable = AvatarService.manifestUnavailable;
    const savedPromise = AvatarService._manifestPromise;
    const origFetch = global.fetch;

    try {
        AvatarService.manifestMap.clear();
        AvatarService.manifestLoaded = false;
        AvatarService.manifestUnavailable = false;
        AvatarService._manifestPromise = null;
        global.fetch = () => Promise.reject(new Error("Network Error 404: avatar_assets.json not found"));

        let threw = false;
        try {
            await AvatarService.ensureManifestLoaded();
        } catch (e) {
            threw = true;
        }
        assert.strictEqual(threw, false, "ensureManifestLoaded must NEVER reject on fetch failure");
        assert.strictEqual(AvatarService.manifestLoaded, true, "manifestLoaded must be set to true on failure");
        assert.strictEqual(AvatarService.manifestUnavailable, true, "manifestUnavailable must be set to true on failure");

        const resolved = AvatarService.resolveExactDialoguePortrait(105813, { warnIfAbsent: false });
        assert(resolved, "Resolution object must exist");
        assert.strictEqual(resolved.status, "manifest_unavailable", "Status must be 'manifest_unavailable'");
        assert.strictEqual(resolved.filename, null, "Filename must be null");

        const html = AvatarService.getAvatarHtmlByUnitId(105813, "貪吃佩可");
        assert(!html.includes("<img"), "Must NOT emit <img> tag when manifest is unavailable");
        assert(html.includes("npc-avatar-placeholder"), "Must fail closed to text placeholder");
        assert(!html.includes("105811"), "Must NOT guess base+11 on manifest failure");
        assert(!html.includes("105831"), "Must NOT guess base+31 on manifest failure");
        assert(!html.includes("estertion") && !html.includes("so-net"), "Must NOT contact external CDN on manifest failure");
    } finally {
        AvatarService.manifestMap = savedMap;
        AvatarService.manifestLoaded = savedLoaded;
        AvatarService.manifestUnavailable = savedUnavailable;
        AvatarService._manifestPromise = savedPromise;
        global.fetch = origFetch;
    }
});

// Test 14 — Concurrent ensureManifestLoaded calls execute exactly 1 fetch
await asyncTest("Test 14 — Concurrent ensureManifestLoaded calls execute exactly 1 fetch", async () => {
    const savedMap = new Map(AvatarService.manifestMap);
    const savedLoaded = AvatarService.manifestLoaded;
    const savedUnavailable = AvatarService.manifestUnavailable;
    const savedPromise = AvatarService._manifestPromise;
    const origFetch = global.fetch;

    try {
        AvatarService.manifestMap.clear();
        AvatarService.manifestLoaded = false;
        AvatarService.manifestUnavailable = false;
        AvatarService._manifestPromise = null;

        let fetchCount = 0;
        global.fetch = () => {
            fetchCount++;
            return new Promise(resolve => {
                setTimeout(() => {
                    resolve({
                        ok: true,
                        json: async () => ({
                            schema_version: "1.0.0",
                            assets: [{ unit_id: 105813, filename: "105813.png", status: "active" }]
                        })
                    });
                }, 20);
            });
        };

        // 並發調用 3 次
        await Promise.all([
            AvatarService.ensureManifestLoaded(),
            AvatarService.ensureManifestLoaded(),
            AvatarService.ensureManifestLoaded()
        ]);

        assert.strictEqual(fetchCount, 1, `Fetch count must be exactly 1, got ${fetchCount}`);
        assert.strictEqual(AvatarService.manifestLoaded, true, "manifestLoaded must be true");
        assert.strictEqual(AvatarService.manifestUnavailable, false, "manifestUnavailable must be false");
        assert.strictEqual(AvatarService.manifestMap.size, 1, "manifestMap must have 1 entry");
    } finally {
        AvatarService.manifestMap = savedMap;
        AvatarService.manifestLoaded = savedLoaded;
        AvatarService.manifestUnavailable = savedUnavailable;
        AvatarService._manifestPromise = savedPromise;
        global.fetch = origFetch;
    }
});

// Test 15 — Generic Manifest-Active ID: Full inference ladder and secondary fallback preserved
test("Test 15 — Generic Manifest-Active ID: Full inference ladder and secondary fallback preserved", () => {
    // 105811 佩可（在 Manifest 中為 active）
    // 通用解析必須包含 [105811, 105831]，絕不能被 Manifest active 截斷為單一 [105811]
    const defaultIds = AvatarService.resolveDefaultPortraitIds(105811);
    assert.deepStrictEqual(defaultIds, [105811, 105831], "resolveDefaultPortraitIds(105811) must return [105811, 105831]");

    // 模擬 handleError 流程：即使 105811 在 manifest active，通用錯誤降級依然能在 Step 4 轉進 Step 5 嘗試 secondary 105831
    let currentSrc = "";
    let displayStyle = "";
    let parentInnerHtml = "";
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

    AvatarService.handleError(mockImg, "貪吃佩可", 105811); // step 1 -> step 2
    assert.strictEqual(mockImg.dataset.step, "2");
    assert(mockImg.src.includes("105811.png") && mockImg.src.includes("00500012"));

    AvatarService.handleError(mockImg, "貪吃佩可", 105811); // step 2 -> step 3
    assert.strictEqual(mockImg.dataset.step, "3");
    assert(mockImg.src.includes("105811.png") && mockImg.src.includes("00500015"));

    AvatarService.handleError(mockImg, "貪吃佩可", 105811); // step 3 -> step 4
    assert.strictEqual(mockImg.dataset.step, "4");
    assert(mockImg.src.includes("105811.webp") && mockImg.src.includes("estertion"));

    AvatarService.handleError(mockImg, "貪吃佩可", 105811); // step 4 -> step 5 (secondary fallback)
    assert.strictEqual(mockImg.dataset.step, "5");
    assert(mockImg.src.includes("105831.png"), "Step 5 must fallback to secondary 105831.png");

    AvatarService.handleError(mockImg, "貪吃佩可", 105811); // step 5 -> step 6
    assert.strictEqual(mockImg.dataset.step, "6");
    assert(mockImg.src.includes("105831.webp") && mockImg.src.includes("estertion"));

    // 139231 西住美穗 (exactFirstWithBaseFallback, manifest active)
    const mihoIds = AvatarService.resolveDefaultPortraitIds(139231);
    assert.deepStrictEqual(mihoIds, [139231, 139211], "resolveDefaultPortraitIds(139231) must return [139231, 139211]");
});

// Test 16 — Generic getUrlCandidates & getAvatarUrl derive from resolveDefaultPortraitIds
test("Test 16 — Generic getUrlCandidates & getAvatarUrl derive from resolveDefaultPortraitIds", () => {
    // 105811 候選陣列必須涵蓋 primary (105811) 與 secondary (105831)
    const candidates = AvatarService.getUrlCandidates(105811);
    assert(candidates.length > 0, "getUrlCandidates must return candidates");
    const hasPrimary = candidates.some(c => c.includes("105811"));
    const hasSecondary = candidates.some(c => c.includes("105831"));
    assert(hasPrimary, "Candidates must include primary 105811");
    assert(hasSecondary, "Candidates must include secondary 105831 even if 105811 is manifest-active");

    const avatarUrl = AvatarService.getAvatarUrl(105811);
    assert.strictEqual(avatarUrl, "icon/unit/105811.png", "getAvatarUrl should use primary ID from default ladder");
});

console.log(`\n✅ All ${testsPassed} AvatarService Phase 6 tests passed successfully!`);
})();
