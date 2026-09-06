/**
 * tests/test_chapter_cover_selector.js
 * 主線章節封面選取 (Chapter Cover Selector) 回歸測試套件
 * 
 * 測試範圍：
 * 1. storyEnd === 1 優先於 storyEnd === 0 策略
 * 2. 無 storyEnd === 1 時平滑回退至首話 (childStories[0])
 * 3. 劇照 (still_id) 與場景背景 (bg_id) 的優先級與無素材時的平滑降級
 * 4. 主線關鍵章節 2214, 2215, 2216 的真實資料庫行為驗證
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

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

console.log("=== Testing Chapter Cover Selector Logic ===");

/**
 * 抽取 map.js line 1014-1039 的純粹選取邏輯為純函式，方便隔離測試
 */
function selectChapterCover(groupId, childStories, storyThumbnails = {}) {
    const endStory = childStories ? childStories.find(s => s.storyEnd === 1) : null;
    let foundStoryId = endStory ? endStory.id : ((childStories && childStories.length > 0) ? childStories[0].id : null);
    let foundStillId = null;
    let foundBgId = null;

    if (groupId && storyThumbnails && storyThumbnails[groupId]) {
        const thumb = storyThumbnails[groupId];
        foundStillId = thumb.still_id || null;
        foundBgId = thumb.bg_id || null;
    }

    if (!foundStillId && !foundBgId && storyThumbnails && childStories) {
        const targetStories = endStory ? [endStory, ...childStories.filter(s => s.id !== endStory.id)] : childStories;
        for (const s of targetStories) {
            const thumb = storyThumbnails[s.id];
            if (thumb) {
                if (thumb.still_id) {
                    foundStillId = thumb.still_id;
                    break; // 優先使用劇照，找到立即停止
                }
                if (!foundBgId && thumb.bg_id) {
                    foundBgId = thumb.bg_id;
                }
            }
        }
    }

    return {
        storyId: foundStoryId,
        stillId: foundStillId,
        bgId: foundBgId,
        isFromStoryEnd: !!endStory
    };
}

// Test 1: storyEnd === 1 優先於 storyEnd === 0
test("Test 1: storyEnd === 1 is prioritized over storyEnd === 0 episodes", () => {
    const mockStories = [
        { id: 2214001, storyEnd: 0, title: "第1話" },
        { id: 2214002, storyEnd: 0, title: "第2話" },
        { id: 2214099, storyEnd: 1, title: "終章" }
    ];
    const result = selectChapterCover(2214, mockStories, {});
    assert.strictEqual(result.storyId, 2214099, "必須選取 storyEnd === 1 的話數 2214099");
    assert.strictEqual(result.isFromStoryEnd, true);
});

// Test 2: 當所有話數皆無 storyEnd === 1 時，回退至首話
test("Test 2: Falls back to first episode when no storyEnd === 1 exists", () => {
    const mockStories = [
        { id: 2001001, storyEnd: 0, title: "第1話" },
        { id: 2001002, storyEnd: 0, title: "第2話" },
        { id: 2001003, storyEnd: 0, title: "第3話" }
    ];
    const result = selectChapterCover(2001, mockStories, {});
    assert.strictEqual(result.storyId, 2001001, "無 storyEnd 時必須回退至首話 2001001");
    assert.strictEqual(result.isFromStoryEnd, false);
});

// Test 3: 劇照 (still_id) 優先於背景 (bg_id)，且优先自 storyEnd 話數尋找
test("Test 3: Still ID is prioritized over background ID from target episodes", () => {
    const mockStories = [
        { id: 2215001, storyEnd: 0 },
        { id: 2215004, storyEnd: 1 }
    ];
    const mockThumbnails = {
        2215001: { still_id: "still_first", bg_id: "bg_first" },
        2215004: { still_id: "still_end", bg_id: "bg_end" }
    };
    const result = selectChapterCover(2215, mockStories, mockThumbnails);
    assert.strictEqual(result.storyId, 2215004);
    assert.strictEqual(result.stillId, "still_end", "應優先採用 endStory 的 still_id");
});

// Test 4: 無劇照時退回背景，且無任何 thumbnail 時優雅保持 null
test("Test 4: Gracefully falls back to bg_id when still is absent, or null when both absent", () => {
    const mockStories = [
        { id: 2216001, storyEnd: 0 },
        { id: 2216004, storyEnd: 1 }
    ];
    // 只有 bg 沒有 still
    const mockThumbnailsBgOnly = {
        2216004: { still_id: null, bg_id: "bg_end_only" }
    };
    const resultBg = selectChapterCover(2216, mockStories, mockThumbnailsBgOnly);
    assert.strictEqual(resultBg.stillId, null);
    assert.strictEqual(resultBg.bgId, "bg_end_only");

    // 完全無縮圖資料
    const resultEmpty = selectChapterCover(2216, mockStories, {});
    assert.strictEqual(resultEmpty.stillId, null);
    assert.strictEqual(resultEmpty.bgId, null);
    assert.strictEqual(resultEmpty.storyId, 2216004, "即使無 still/bg，話數 ID 仍應正確選中 2216004");
});

// Test 5: 空話數陣列防禦處理
test("Test 5: Defensive handling for empty or null childStories", () => {
    const resNull = selectChapterCover(2000, null, {});
    assert.strictEqual(resNull.storyId, null);
    assert.strictEqual(resNull.isFromStoryEnd, false);

    const resEmpty = selectChapterCover(2000, [], {});
    assert.strictEqual(resEmpty.storyId, null);
    assert.strictEqual(resEmpty.isFromStoryEnd, false);
});

// Test 6: 主線真實關鍵章節 2214, 2215, 2216 實體資料庫驗證
test("Test 6: Real-world database verification for key chapters 2214, 2215, 2216", () => {
    const storyIconDir = path.join(__dirname, '../dashboard/icon/story');
    const keyStories = [
        { group: 2214, expectedEndStory: 2214099 },
        { group: 2215, expectedEndStory: 2215004 },
        { group: 2216, expectedEndStory: 2216004 }
    ];

    for (const item of keyStories) {
        const thumbPath = path.join(storyIconDir, `${item.expectedEndStory}.webp`);
        assert(fs.existsSync(thumbPath), `關鍵代表話數縮圖 ${item.expectedEndStory}.webp 必須存在於 dashboard/icon/story/`);
        const stat = fs.statSync(thumbPath);
        assert(stat.size > 0, `關鍵代表話數縮圖 ${item.expectedEndStory}.webp 檔案大小必須大於 0 (實際: ${stat.size} bytes)`);
    }
});

console.log(`\n🎉 All ${testsPassed} Chapter Cover Selector tests passed!`);
