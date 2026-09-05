/**
 * tests/test_chapter_titles_runtime.js
 * 主線劇情章節標題前端 Runtime 契約與渲染行為測試
 *
 * 驗證範圍：
 * 1. 載入真實 dashboard/data/chapters.json 與 dashboard/chapter-data.js
 * 2. 驗證 ChapterDataService.getTitle(3, groupId) 結果：
 *    - 2213: null
 *    - 2214: "阿爾莎特的誘惑"
 *    - 2215: "響導幼君" (嚴格官方字樣)
 *    - 2216: "三方爭霸"
 * 3. 驗證 map.js 實機條件契約：title ? ` - ${title}` : ""
 *    - 第13章 (無 ' - null'，無 '-')
 *    - 第14章 - 阿爾莎特的誘惑
 *    - 第15章 - 響導幼君
 *    - 第16章 - 三方爭霸
 * 4. 驗證 legacy_title 不洩漏至 getTitle()
 */

const assert = require('assert');
const path = require('path');
const fs = require('fs');

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

console.log("=== Testing Chapter Titles Runtime Behavior ===");

// 載入真實檔案
const rawChaptersPath = path.join(__dirname, '../dashboard/data/chapters.json');
const chaptersData = JSON.parse(fs.readFileSync(rawChaptersPath, 'utf-8'));

// 注入真實 chapters 資料至 ChapterDataService
ChapterDataService.data = chaptersData;

test("Test 1: Official titles for 2214, 2215, 2216 and unresolved 2213 via ChapterDataService", () => {
    assert.strictEqual(ChapterDataService.getTitle(3, '2213'), null, "2213 getTitle() must be null");
    assert.strictEqual(ChapterDataService.getTitle(3, '2214'), '阿爾莎特的誘惑', "2214 getTitle() mismatch");
    assert.strictEqual(ChapterDataService.getTitle(3, '2215'), '響導幼君', "2215 getTitle() mismatch (must strictly be 響導)");
    assert.strictEqual(ChapterDataService.getTitle(3, '2216'), '三方爭霸', "2216 getTitle() mismatch");
});

test("Test 2: Legacy title does not leak into ChapterDataService getTitle() for unresolved chapters", () => {
    const info2213 = ChapterDataService.getChapterInfo(3, '2213');
    assert(info2213.legacy_title, "2213 should preserve legacy_title in raw json");
    assert.strictEqual(ChapterDataService.getTitle(3, '2213'), null, "getTitle() must ignore legacy_title and return null");
});

test("Test 3: Display behavior contract for 2213 (unresolved) -> 第13章", () => {
    const info = ChapterDataService.getChapterInfo(3, '2213');
    const chKey = info?.key || '第13章';
    const chTitle = info?.title ? ` - ${info.title}` : "";
    const renderedHeader = `${chKey}${chTitle}`;
    assert.strictEqual(renderedHeader, '第13章');
    assert(!renderedHeader.includes('null'), "Rendered header should not contain 'null'");
    assert(!renderedHeader.includes('-'), "Rendered header for unresolved should not contain '-' separator");
});

test("Test 4: Display behavior contract for 2214 (official) -> 第14章 - 阿爾莎特的誘惑", () => {
    const info = ChapterDataService.getChapterInfo(3, '2214');
    const chKey = info?.key || '第14章';
    const chTitle = info?.title ? ` - ${info.title}` : "";
    const renderedHeader = `${chKey}${chTitle}`;
    assert.strictEqual(renderedHeader, '第14章 - 阿爾莎特的誘惑');
});

test("Test 5: Display behavior contract for 2215 (official) -> 第15章 - 響導幼君", () => {
    const info = ChapterDataService.getChapterInfo(3, '2215');
    const chKey = info?.key || '第15章';
    const chTitle = info?.title ? ` - ${info.title}` : "";
    const renderedHeader = `${chKey}${chTitle}`;
    assert.strictEqual(renderedHeader, '第15章 - 響導幼君');
});

test("Test 6: Display behavior contract for 2216 (official) -> 第16章 - 三方爭霸", () => {
    const info = ChapterDataService.getChapterInfo(3, '2216');
    const chKey = info?.key || '第16章';
    const chTitle = info?.title ? ` - ${info.title}` : "";
    const renderedHeader = `${chKey}${chTitle}`;
    assert.strictEqual(renderedHeader, '第16章 - 三方爭霸');
});

console.log(`All ${testsPassed} chapter titles runtime tests passed.`);
