/**
 * tests/test_chapter_titles_runtime.js
 * 主線劇情章節標題前端 Runtime 契約與渲染行為測試
 *
 * 驗證範圍：
 * 1. 載入真實 dashboard/data/chapters.json 與 dashboard/chapter-data.js
 * 2. 驗證 ChapterDataService.getTitle(3, groupId) 結果：
 *    - 2213: "降臨的幻境" (官方母檔)
 *    - 2214: "阿爾莎特的誘惑"
 *    - 2215: "嚮導幼君" (嚴格官方母檔字樣，首字 U+56AE 嚮，絕非 響導)
 *    - 2216: "三方爭霸"
 * 3. 驗證 map.js 實機條件契約：title ? ` - ${title}` : ""
 *    - 第13章 - 降臨的幻境
 *    - 第14章 - 阿爾莎特的誘惑
 *    - 第15章 - 嚮導幼君
 *    - 第16章 - 三方爭霸
 * 4. 驗證 legacy_title 絕不洩漏至 getTitle()，且 48 個主線章節皆具備官方標題與 zh-TW 語言標籤
 * 5. 抽查第 1 部與第 2 部主線標題之正確性與非空契約
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

test("Test 1: Official canonical titles for Part 3 chapters via ChapterDataService", () => {
    assert.strictEqual(ChapterDataService.getTitle(3, '2213'), '降臨的幻境', "2213 getTitle() mismatch");
    assert.strictEqual(ChapterDataService.getTitle(3, '2214'), '阿爾莎特的誘惑', "2214 getTitle() mismatch");
    assert.strictEqual(ChapterDataService.getTitle(3, '2215'), '嚮導幼君', "2215 getTitle() mismatch (must strictly be 嚮導幼君)");
    assert.notStrictEqual(ChapterDataService.getTitle(3, '2215'), '響導幼君', "2215 must NOT be 響導幼君");
    assert.strictEqual(ChapterDataService.getTitle(3, '2215').charCodeAt(0), 0x56AE, "2215 first char must be U+56AE 嚮");
    assert.strictEqual(ChapterDataService.getTitle(3, '2216'), '三方爭霸', "2216 getTitle() mismatch");
});

test("Test 2: Legacy title does not leak into ChapterDataService getTitle()", () => {
    // 1. 驗證真實資料庫中的 48 個主線章節皆保留 legacy_title 且 getTitle() 回傳官方 title
    const part3Chapters = chaptersData["3"].game_world;
    for (const [gid, ch] of Object.entries(part3Chapters)) {
        assert(ch.legacy_title, `Part 3 Chapter ${gid} should preserve legacy_title`);
        assert.strictEqual(ChapterDataService.getTitle(3, gid), ch.title, `Chapter ${gid} getTitle() must return official title`);
    }

    // 2. 透過孤立 mock 資料驗證：當 title 為 null 時，getTitle() 絕對不能 fallback 到 legacy_title
    const mockBackup = ChapterDataService.data;
    try {
        ChapterDataService.data = {
            "3": {
                game_world: {
                    "9999": {
                        key: "第99章",
                        title: null,
                        legacy_title: "洩漏測試遺留標題"
                    }
                }
            }
        };
        assert.strictEqual(ChapterDataService.getTitle(3, '9999'), null, "getTitle() must return null and never leak legacy_title");
    } finally {
        ChapterDataService.data = mockBackup;
    }
});

test("Test 3: Display behavior contract for 2213 (official) -> 第13章 - 降臨的幻境", () => {
    const info = ChapterDataService.getChapterInfo(3, '2213');
    const chKey = info?.key || '第13章';
    const chTitle = info?.title ? ` - ${info.title}` : "";
    const renderedHeader = `${chKey}${chTitle}`;
    assert.strictEqual(renderedHeader, '第13章 - 降臨的幻境');
});

test("Test 4: Display behavior contract for 2214 (official) -> 第14章 - 阿爾莎特的誘惑", () => {
    const info = ChapterDataService.getChapterInfo(3, '2214');
    const chKey = info?.key || '第14章';
    const chTitle = info?.title ? ` - ${info.title}` : "";
    const renderedHeader = `${chKey}${chTitle}`;
    assert.strictEqual(renderedHeader, '第14章 - 阿爾莎特的誘惑');
});

test("Test 5: Display behavior contract for 2215 (official) -> 第15章 - 嚮導幼君", () => {
    const info = ChapterDataService.getChapterInfo(3, '2215');
    const chKey = info?.key || '第15章';
    const chTitle = info?.title ? ` - ${info.title}` : "";
    const renderedHeader = `${chKey}${chTitle}`;
    assert.strictEqual(renderedHeader, '第15章 - 嚮導幼君');
    assert.notStrictEqual(renderedHeader, '第15章 - 響導幼君');
});

test("Test 6: Display behavior contract for 2216 (official) -> 第16章 - 三方爭霸", () => {
    const info = ChapterDataService.getChapterInfo(3, '2216');
    const chKey = info?.key || '第16章';
    const chTitle = info?.title ? ` - ${info.title}` : "";
    const renderedHeader = `${chKey}${chTitle}`;
    assert.strictEqual(renderedHeader, '第16章 - 三方爭霸');
});

test("Test 7: Spot check official titles for Part 1 & Part 2", () => {
    // Part 1: 2000, 2001 & 2015
    assert.strictEqual(ChapterDataService.getTitle(1, '2000'), '牽起羈絆的人們');
    assert.strictEqual(ChapterDataService.getTitle(1, '2001'), '謎樣少女與記憶之鑰');
    assert.strictEqual(ChapterDataService.getTitle(1, '2015'), 'Re：連結');
    // Part 2: 2101 & 2116
    assert.strictEqual(ChapterDataService.getTitle(2, '2101'), '冒險，再起');
    assert.strictEqual(ChapterDataService.getTitle(2, '2116'), '終結世界');
});

test("Test 8: All 48 main story chapters have official title and valid rendered headers", () => {
    let mainCount = 0;
    for (const part of ["1", "2", "3"]) {
        const gw = chaptersData[part]?.game_world || {};
        for (const [gid, ch] of Object.entries(gw)) {
            mainCount++;
            assert.strictEqual(ch.title_provenance, 'official_tw_localized_asset');
            assert.strictEqual(ch.title_locale, 'zh-TW');
            assert(typeof ch.title === 'string' && ch.title.length > 0, `Chapter ${gid} must have non-empty official title`);
            const title = ChapterDataService.getTitle(part, gid);
            assert.strictEqual(title, ch.title);
            const rendered = `${ch.key} - ${title}`;
            assert(!rendered.includes('null') && !rendered.includes('undefined'));
        }
    }
    assert.strictEqual(mainCount, 48, "Must verify exactly 48 main story chapters");
});

console.log(`All ${testsPassed} chapter titles runtime tests passed.`);
