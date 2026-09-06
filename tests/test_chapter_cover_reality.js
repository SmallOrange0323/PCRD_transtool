/**
 * tests/test_chapter_cover_reality.js
 * 主線章節封面實體素材驗證 (LOCAL RELEASE GATE)
 * 
 * 驗證本地開發環境中 2214, 2215, 2216 等關鍵章節之 storyEnd 實體代表縮圖是否存在且大小大於 0。
 * 注意：本測試依賴未追蹤之本地二進位資產 (dashboard/icon/story/)，僅於本地發布前執行。
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

console.log("=== Testing Chapter Cover Local Reality (Release Gate) ===");

test("Chapter Cover Reality: 2214, 2215, 2216 local thumbnail existence and non-zero size", () => {
    const storyIconDir = path.join(__dirname, '../dashboard/icon/story');
    const keyStories = [
        { group: 2214, expectedEndStory: 2214099, desc: "第3部第14章終章" },
        { group: 2215, expectedEndStory: 2215004, desc: "第3部第15章第4話" },
        { group: 2216, expectedEndStory: 2216004, desc: "第3部第16章第4話" }
    ];

    assert(fs.existsSync(storyIconDir), `dashboard/icon/story 目錄必須存在於本地環境: ${storyIconDir}`);

    for (const item of keyStories) {
        const thumbPath = path.join(storyIconDir, `${item.expectedEndStory}.webp`);
        assert(fs.existsSync(thumbPath), `關鍵代表話數縮圖 ${item.expectedEndStory}.webp (${item.desc}) 必須存在於本地`);
        const stat = fs.statSync(thumbPath);
        assert(stat.size > 0, `關鍵代表話數縮圖 ${item.expectedEndStory}.webp 檔案大小必須大於 0 (實際: ${stat.size} bytes)`);
        console.log(`    ✓ ${item.group} -> ${item.expectedEndStory}.webp (${stat.size} bytes)`);
    }
});

console.log(`\n🎉 All ${testsPassed} Chapter Cover Reality tests passed!`);
