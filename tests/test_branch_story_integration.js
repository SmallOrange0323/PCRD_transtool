/**
 * tests/test_branch_story_integration.js
 * 第 3 部分支劇情 (Branch Story) 整合單元測試
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

console.log("=== Testing Branch Story Integration ===");

// 載入真實的 branch_stories.json
const rawBranchJsonPath = path.join(__dirname, '../dashboard/data/branch_stories.json');
const branchData = JSON.parse(fs.readFileSync(rawBranchJsonPath, 'utf-8'));

// Test 1 — 63 supplemental entries transformed correctly
test("Test 1 — 63 supplemental entries transformed correctly", () => {
    const transformed = ChapterDataService.transformBranchStories(branchData);
    assert.strictEqual(transformed.length, 63, "Should transform all 63 stories");
    assert(transformed.every(s => s.part === 3 && s.type === 'main' && s.isBranch === true), "All must be Part 3 main branch");
});

// Test 2 — Chapter counts (Ch 1: 3, Ch 9: 8, Ch 16: 1)
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

// Test 3 — Resolved entries use verified descriptive metadata
test("Test 3 — Resolved entries use verified metadata", () => {
    const transformed = ChapterDataService.transformBranchStories(branchData);
    const s2213101 = transformed.find(s => s.id === 2213101);
    const s2213104 = transformed.find(s => s.id === 2213104);

    assert(s2213101, "2213101 must exist");
    assert.strictEqual(s2213101.chapter, "分支劇情 L I", "2213101 chapter label must match official verified title");
    assert.strictEqual(s2213101.title, "死者的世界裡最臭的東西", "2213101 title must match official subtitle");
    assert.strictEqual(s2213101.metadataStatus, "resolved_official_screenshot");

    assert(s2213104, "2213104 must exist");
    assert.strictEqual(s2213104.chapter, "分支劇情 R V", "2213104 chapter label must match official verified title");
    assert.strictEqual(s2213104.title, "錢與豐滿與現實", "2213104 title must match official subtitle");
});

// Test 4 — Unresolved entries use runtime fallback label
test("Test 4 — Unresolved entries use runtime fallback label", () => {
    const transformed = ChapterDataService.transformBranchStories(branchData);
    const s2201101 = transformed.find(s => s.id === 2201101);
    const s2201102 = transformed.find(s => s.id === 2201102);

    assert(s2201101, "2201101 must exist");
    assert.strictEqual(s2201101.chapter, "分支劇情 1", "2201101 fallback chapter");
    assert.strictEqual(s2201101.title, "分支劇情 1", "2201101 fallback title");
    assert.strictEqual(s2201101.metadataStatus, "unresolved");

    assert(s2201102, "2201102 must exist");
    assert.strictEqual(s2201102.chapter, "分支劇情 2", "2201102 fallback chapter");
});

// Test 5 — Source object is NOT mutated
test("Test 5 — Source data object is not mutated", () => {
    const originalEntry = branchData.stories.find(s => s.story_id === 2201101);
    assert.strictEqual(originalEntry.title, null, "Source title must remain null");
    assert.strictEqual(originalEntry.subtitle, null, "Source subtitle must remain null");
    assert.strictEqual(originalEntry.branch_label, null, "Source branch_label must remain null");
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
                { story_id: 2201101, chapter: 1, metadata_status: "unresolved" },
                { story_id: 2201101, chapter: 1, metadata_status: "unresolved" }
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

console.log(`\n✅ All ${testsPassed} branch story integration tests passed successfully!`);
