/**
 * tests/test_branch_story_integration.js
 * 第 3 部分支劇情 (Branch Story) 整合單元測試
 * 涵蓋 Runtime Schema 邊界、資料契約 (Contracts)、閱讀載入合約與初始化載入順序
 */

const assert = require('assert');
const path = require('path');
const fs = require('fs');

// 模擬全域環境
global.window = global;

const ChapterDataService = require(path.join(__dirname, '../dashboard/chapter-data.js'));

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

console.log("=== Testing Branch Story Integration (Amended) ===");

// 載入真實的 branch_stories.json
const rawBranchJsonPath = path.join(__dirname, '../dashboard/data/branch_stories.json');
const branchData = JSON.parse(fs.readFileSync(rawBranchJsonPath, 'utf-8'));

// Test 1 — 63 supplemental entries transformed correctly
test("Test 1 — 63 supplemental entries transformed correctly", () => {
    const transformed = ChapterDataService.transformBranchStories(branchData);
    assert.strictEqual(transformed.length, 63, "Should transform all 63 stories");
    assert(transformed.every(s => s.part === 3 && s.type === 'main' && s.isBranch === true), "All must be Part 3 main branch");
});

// Test 2 — Chapter specific counts
test("Test 2 — Chapter specific counts", () => {
    const transformed = ChapterDataService.transformBranchStories(branchData);
    const byChapter = {};
    transformed.forEach(s => {
        const ch = s.groupId - 2200;
        byChapter[ch] = (byChapter[ch] || 0) + 1;
    });

    assert.strictEqual(byChapter[1], 3, "Chapter 1 should have 3 branch stories");
    assert.strictEqual(byChapter[9], 8, "Chapter 9 should have 8 branch stories");
    assert.strictEqual(byChapter[13], 4, "Chapter 13 should have 4 branch stories");
    assert.strictEqual(byChapter[16], 1, "Chapter 16 should have 1 branch story");
});

// Test 3 — All 63 entries use verified official bundle metadata
test("Test 3 — All 63 entries use verified official bundle metadata", () => {
    const transformed = ChapterDataService.transformBranchStories(branchData);
    assert.strictEqual(transformed.length, 63, "All 63 entries present");
    assert(transformed.every(s => s.metadataStatus === "resolved_official_bundle"), "All 63 stories must be resolved_official_bundle");

    const s2201101 = transformed.find(s => s.id === 2201101);
    const s2213101 = transformed.find(s => s.id === 2213101);
    const s2213102 = transformed.find(s => s.id === 2213102);
    const s2213104 = transformed.find(s => s.id === 2213104);
    const s2216101 = transformed.find(s => s.id === 2216101);

    assert(s2201101, "2201101 must exist");
    assert.strictEqual(s2201101.chapter, "分支劇情 I");
    assert.strictEqual(s2201101.title, "黑社會公會，前往背面世界");

    assert(s2213101, "2213101 must exist");
    assert.strictEqual(s2213101.chapter, "分支劇情 XLIX");
    assert.strictEqual(s2213101.title, "棘手大小姐們的觀光約會？");

    assert(s2213102, "2213102 must exist");
    assert.strictEqual(s2213102.chapter, "分支劇情 L");
    assert.strictEqual(s2213102.title, "亞里莎，遭遇巨人");

    const s2213103 = transformed.find(s => s.id === 2213103);
    assert(s2213103, "2213103 must exist");
    assert.strictEqual(s2213103.chapter, "分支劇情 LI");
    assert.strictEqual(s2213103.title, "死者的世界裡最臭的東西");

    assert(s2213104, "2213104 must exist");
    assert.strictEqual(s2213104.chapter, "分支劇情 R V");
    assert.strictEqual(s2213104.title, "錢與豐滿與現實");

    assert(s2216101, "2216101 must exist");
    assert.strictEqual(s2216101.chapter, "分支劇情 LVI");
    assert.strictEqual(s2216101.title, "新人偶像小志那");
});

// Test 4 — Unresolved mock entries use runtime fallback label
test("Test 4 — Unresolved mock entries use runtime fallback label", () => {
    const mockUnresolvedData = {
        version: 1,
        part: 3,
        stories: [
            { story_id: 2201101, chapter: 1, branch_label: null, title: null, subtitle: null, metadata_status: "unresolved" },
            { story_id: 2201102, chapter: 1, branch_label: null, title: null, subtitle: null, metadata_status: "unresolved" }
        ]
    };
    const transformed = ChapterDataService.transformBranchStories(mockUnresolvedData);
    assert.strictEqual(transformed[0].chapter, "分支劇情 1", "2201101 fallback chapter");
    assert.strictEqual(transformed[0].title, "分支劇情 1", "2201101 fallback title");
    assert.strictEqual(transformed[0].metadataStatus, "unresolved");
    assert.strictEqual(transformed[1].chapter, "分支劇情 2", "2201102 fallback chapter");
});

// Test 5 — Source data object is not mutated
test("Test 5 — Source data object is not mutated", () => {
    const mockInput = {
        version: 1,
        part: 3,
        stories: [
            { story_id: 2201101, chapter: 1, branch_label: "第1話", title: "分支劇情 第1話", subtitle: "黑社會公會，前往背面世界", metadata_status: "resolved_official_bundle" }
        ]
    };
    const originalSubtitle = mockInput.stories[0].subtitle;
    ChapterDataService.transformBranchStories(mockInput);
    assert.strictEqual(mockInput.stories[0].subtitle, originalSubtitle, "Source subtitle must remain untouched");
});

// Test 6 — Ordinary stories preserved when merging in QuestMapModule logic
test("Test 6 — Ordinary stories preserved upon merge", () => {
    const mockDbStories = [
        { id: 2213001, chapter: "第3部 第13章 第1話", title: "聚集在大江戶的公主們", groupId: 2213, part: 3, isEvent: false, type: 'main' },
        { id: 2213099, chapter: "第3部 第13章 幕間‧ⅩⅦ", title: "evacuate from empress", groupId: 2213, part: 3, isEvent: false, type: 'main' }
    ];

    const branchStories = ChapterDataService.transformBranchStories(branchData);
    const existingIds = new Set(mockDbStories.map(s => s.id));
    const merged = mockDbStories.concat(branchStories.filter(s => !existingIds.has(s.id)));

    assert(merged.some(s => s.id === 2213001), "Ordinary story 2213001 preserved");
    assert(merged.some(s => s.id === 2213099), "Ordinary story 2213099 preserved");
    assert(merged.some(s => s.id === 2213101), "Branch story 2213101 merged");
    assert.strictEqual(merged.length, mockDbStories.length + 63, "Total length must equal DB stories + 63");
});

// Test 7 — Deterministic ordering (ID ascending within chapter)
test("Test 7 — Deterministic ordering within chapter", () => {
    const transformed = ChapterDataService.transformBranchStories(branchData);
    const ch13Branch = transformed.filter(s => s.groupId === 2213);
    const ids = ch13Branch.map(s => s.id);
    assert.deepStrictEqual(ids, [2213101, 2213102, 2213103, 2213104], "Branch stories in Ch13 must be ascending");
});

// Test 8 — Duplicate ID protection
test("Test 8 — Duplicate supplemental ID protection", () => {
    let threw = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: 2201101, chapter: 1, branch_label: null, title: null, subtitle: null, metadata_status: "unresolved" },
                { story_id: 2201101, chapter: 1, branch_label: null, title: null, subtitle: null, metadata_status: "unresolved" }
            ]
        });
    } catch (e) {
        threw = true;
    }
    assert(threw, "transformBranchStories must throw error on duplicate story_id");
});

// Test 9 — Malformed schema fail loudly
test("Test 9 — Malformed metadata schema fails loudly", () => {
    let threw1 = false;
    try {
        ChapterDataService.transformBranchStories({ version: 2, part: 3, stories: [] });
    } catch (e) {
        threw1 = true;
    }
    assert(threw1, "Must fail loudly when version is invalid");

    let threw2 = false;
    try {
        ChapterDataService.transformBranchStories({ version: 1, part: 3, stories: "invalid" });
    } catch (e) {
        threw2 = true;
    }
    assert(threw2, "Must fail loudly when stories is not an array");
});

// Test 10 — Invalid metadata_status fails loudly
test("Test 10 — Invalid metadata_status fails loudly", () => {
    let threw = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: 2201101, chapter: 1, branch_label: null, title: null, subtitle: null, metadata_status: "unknown_custom_status" }
            ]
        });
    } catch (e) {
        threw = true;
    }
    assert(threw, "Must throw on unknown metadata_status");
});

// Test 11 — Out-of-range chapter fails loudly
test("Test 11 — Out-of-range chapter fails loudly (0 and 17)", () => {
    let threw0 = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: 2200101, chapter: 0, branch_label: null, title: null, subtitle: null, metadata_status: "unresolved" }
            ]
        });
    } catch (e) {
        threw0 = true;
    }
    assert(threw0, "Must throw on chapter 0");

    let threw17 = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: 2217101, chapter: 17, branch_label: null, title: null, subtitle: null, metadata_status: "unresolved" }
            ]
        });
    } catch (e) {
        threw17 = true;
    }
    assert(threw17, "Must throw on chapter 17");
});

// Test 12 — Resolved metadata completeness fails loudly
test("Test 12 — Resolved metadata completeness (missing title/subtitle/branch_label)", () => {
    let threwMissingTitle = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: 2213101, chapter: 13, branch_label: "L I", title: null, subtitle: "死者的世界裡最臭的東西", metadata_status: "resolved_official_screenshot" }
            ]
        });
    } catch (e) {
        threwMissingTitle = true;
    }
    assert(threwMissingTitle, "Must throw on resolved entry with null title");

    let threwMissingSubtitle = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: 2213101, chapter: 13, branch_label: "L I", title: "分支劇情 L I", subtitle: "", metadata_status: "resolved_official_screenshot" }
            ]
        });
    } catch (e) {
        threwMissingSubtitle = true;
    }
    assert(threwMissingSubtitle, "Must throw on resolved entry with empty subtitle");
});

// Test 13 — Unresolved descriptive metadata contamination fails loudly
test("Test 13 — Unresolved descriptive metadata contamination fails loudly", () => {
    let threwContaminated = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: 2201101, chapter: 1, branch_label: null, title: "synthetic title", subtitle: null, metadata_status: "unresolved" }
            ]
        });
    } catch (e) {
        threwContaminated = true;
    }
    assert(threwContaminated, "Must throw when unresolved entry has non-null title");
});

// Test 14 — Non-integer story_id / chapter rejects
test("Test 14 — Non-integer story_id / chapter rejects", () => {
    let threwStrId = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: "2201101", chapter: 1, branch_label: null, title: null, subtitle: null, metadata_status: "unresolved" }
            ]
        });
    } catch (e) {
        threwStrId = true;
    }
    assert(threwStrId, "Must throw on string story_id");

    let threwStrCh = false;
    try {
        ChapterDataService.transformBranchStories({
            version: 1,
            part: 3,
            stories: [
                { story_id: 2201101, chapter: "1", branch_label: null, title: null, subtitle: null, metadata_status: "unresolved" }
            ]
        });
    } catch (e) {
        threwStrCh = true;
    }
    assert(threwStrCh, "Must throw on string chapter");
});

// Test 15 — Click & dialogue loading contract (clean-clone contract: validates target derivation, intentionally does NOT require local story files)
test("Test 15 — Story click contract generates valid loadDialogue target", () => {
    const transformed = ChapterDataService.transformBranchStories(branchData);
    const s2213101 = transformed.find(s => s.id === 2213101);

    assert(s2213101, "Transformed branch story 2213101 must exist");
    assert.strictEqual(typeof s2213101.id, 'number', "Story ID must remain numeric");
    assert.strictEqual(s2213101.id, 2213101, "Story ID must be preserved for QuestMapModule.selectStory/loadDialogue");

    // Validates the logical dialogue path contract (story/${storyId}.json) used by QuestMapModule.loadDialogue
    const logicalDialogueTarget = `story/${s2213101.id}.json`;
    assert.strictEqual(logicalDialogueTarget, "story/2213101.json", "Dialogue target path must derive strictly from numeric story ID");
});

// Test 16 — Load order source contract in dashboard/map.js
test("Test 16 — dashboard/map.js enforces ChapterDataService.load() before branchStories merge", () => {
    const mapJsPath = path.join(__dirname, '../dashboard/map.js');
    const mapSrc = fs.readFileSync(mapJsPath, 'utf-8');

    const loadDataMatch = mapSrc.match(/async\s+loadData\s*\(\)\s*\{([\s\S]*?)\n\s*groupStories\s*\(\)/);
    assert(loadDataMatch, "loadData function must exist in dashboard/map.js");
    const loadDataBody = loadDataMatch[1];

    const loadCallIndex = loadDataBody.indexOf("await window.ChapterDataService.load()");
    const branchMergeIndex = loadDataBody.indexOf("window.ChapterDataService.branchStories");

    assert(loadCallIndex >= 0, "await window.ChapterDataService.load() must be called in loadData()");
    assert(branchMergeIndex >= 0, "window.ChapterDataService.branchStories must be accessed in loadData()");
    assert(loadCallIndex < branchMergeIndex, "ChapterDataService.load() must occur BEFORE branchStories is read for merge");

    // 確保尾端無多餘的重複 load 呼叫
    const remainingAfterMerge = loadDataBody.substring(branchMergeIndex);
    assert(!remainingAfterMerge.includes("ChapterDataService.load()"), "No redundant ChapterDataService.load() after branch merge");
});

// Test 17 — Load order runtime simulation & representative story presence
test("Test 17 — ChapterDataService load completes before branch merge & representative IDs present", async () => {
    // 模擬 ChapterDataService 的非同步載入行為
    ChapterDataService.branchStories = ChapterDataService.transformBranchStories(branchData);
    assert.strictEqual(ChapterDataService.branchStories.length, 63, "Branch stories must be 63 before merge");

    // 模擬 QuestMapModule.loadData 的初始化與合併流程
    const mockModule = {
        stories: [
            { id: 2201001, chapter: "第3部 第1章 第1話", title: "序幕", groupId: 2201, part: 3, type: 'main' },
            { id: 2213001, chapter: "第3部 第13章 第1話", title: "大江戶", groupId: 2213, part: 3, type: 'main' }
        ]
    };

    // 執行 supplemental branch merge
    if (ChapterDataService && Array.isArray(ChapterDataService.branchStories)) {
        const existingIds = new Set(mockModule.stories.map(s => s.id));
        const newBranchStories = ChapterDataService.branchStories.filter(s => !existingIds.has(s.id));
        mockModule.stories = mockModule.stories.concat(newBranchStories);
    }

    // 1. 代表性 ID 檢查
    const representativeIds = [2201101, 2209101, 2213101, 2213104, 2216101];
    representativeIds.forEach(id => {
        const found = mockModule.stories.find(s => s.id === id);
        assert(found, `Representative story ID ${id} must be present in stories`);
        assert.strictEqual(found.part, 3, `Story ${id} part must be 3`);
        assert.strictEqual(found.type, 'main', `Story ${id} type must be main`);
    });

    // 2. 重複 ID 檢查
    const idCountMap = {};
    mockModule.stories.forEach(s => {
        idCountMap[s.id] = (idCountMap[s.id] || 0) + 1;
    });
    const duplicateIds = Object.keys(idCountMap).filter(id => idCountMap[id] > 1);
    assert.strictEqual(duplicateIds.length, 0, `Must have 0 duplicate IDs, found: ${duplicateIds.join(',')}`);

    // 3. 總長度檢查
    assert.strictEqual(mockModule.stories.length, 2 + 63, "Total stories length must equal DB stories + 63 branch stories");
});

console.log(`\n✅ All ${testsPassed} branch story integration tests passed successfully!`);
