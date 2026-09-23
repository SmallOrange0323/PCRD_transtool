/**
 * tests/test_story_asset_service.js
 * 劇情素材服務 (StoryAssetService) 針對性單元測試 (Node VM Runtime Harness)
 * 驗證環境判定 (Production Pages vs Local/Dev) 與 CG (Still) URL 候選清單排序
 * 
 * 本測試直接透過 Node vm 沙盒執行 browser-global 原始碼，不依賴任何 CommonJS/module.exports。
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SERVICE_CODE = fs.readFileSync(
    path.join(__dirname, '../dashboard/story-asset-service.js'),
    'utf-8'
);

function createServiceInstance(locationMock = null) {
    const sandbox = {
        window: locationMock !== null ? { location: locationMock } : {},
        console: console
    };
    vm.createContext(sandbox);
    vm.runInContext(SERVICE_CODE, sandbox);
    return sandbox.window.StoryAssetService;
}

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

console.log("=== Testing StoryAssetService (P3C Remote-First Optimization via VM Sandbox) ===");

const TRANSPARENT_PLACEHOLDER = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

// Test 1 — GitHub Pages production + 9-digit ID
test("Test 1: GitHub Pages production + 9-digit ID remote-first", () => {
    const service = createServiceInstance({
        hostname: 'smallorange0323.github.io',
        pathname: '/PCRD_transtool/'
    });

    assert.strictEqual(service.isProductionPages(), true, "應識別為 GitHub Pages production");

    const urls = service.getStillUrls("512200601");
    assert.strictEqual(urls[0], "https://redive.estertion.win/card/story/512200601.webp", "首選必須為 Estertion WebP");
    assert.strictEqual(urls[1], "https://redive.estertion.win/card/story/512200601.png", "次選必須為 Estertion PNG");

    // 不得包含 local still/story
    assert.strictEqual(urls.some(u => u.includes("still/story/512200601")), false, "Production 候選清單不得包含 local still/story");

    // 最後一個必須為 transparent placeholder
    assert.strictEqual(urls[urls.length - 1], TRANSPARENT_PLACEHOLDER, "最後一項必須是透明佔位圖");
});

// Test 2 — localhost + 9-digit ID
test("Test 2: localhost + 9-digit ID local-first", () => {
    const service = createServiceInstance({
        hostname: 'localhost',
        pathname: '/story_map.html'
    });

    assert.strictEqual(service.isProductionPages(), false, "localhost 不得識別為 production");

    const urls = service.getStillUrls("512200601");
    assert.strictEqual(urls[0], "still/story/512200601.webp", "Local 首選必須為 local still/story WebP");
    assert.strictEqual(urls[1], "still/story/512200601.png", "Local 次選必須為 local still/story PNG");
    assert.strictEqual(urls[2], "https://redive.estertion.win/card/story/512200601.webp", "後續應接 Estertion WebP");
    assert.strictEqual(urls[urls.length - 1], TRANSPARENT_PLACEHOLDER);
});

// Test 3 — location absent / Node environment
test("Test 3: location absent / Node environment safe fallback", () => {
    const service = createServiceInstance(null); // 沒有 location
    assert.strictEqual(service.isProductionPages(), false, "無 location 時應安全回傳 false");

    const urls = service.getStillUrls("512200601");
    assert.strictEqual(urls[0], "still/story/512200601.webp", "無 location 時應預設保留 local-first");
    assert.strictEqual(urls[urls.length - 1], TRANSPARENT_PLACEHOLDER);
});

// Test 4 — short ID card/full routing
test("Test 4: short ID card/full routing (local vs production)", () => {
    // Local
    const localService = createServiceInstance({ hostname: '127.0.0.1', pathname: '/' });
    const localUrls = localService.getStillUrls("100401");
    assert.strictEqual(localUrls[0], "still/story/100401.webp");
    assert.strictEqual(localUrls[1], "still/story/100401.png");
    assert.strictEqual(localUrls[2], "https://redive.estertion.win/card/full/100401.webp", "短 ID 應路由至 card/full");
    assert.strictEqual(localUrls[3], "https://redive.estertion.win/card/full/100401.png");

    // Production
    const prodService = createServiceInstance({ hostname: 'smallorange0323.github.io', pathname: '/PCRD_transtool/index.html' });
    const prodUrls = prodService.getStillUrls("100401");
    assert.strictEqual(prodUrls[0], "https://redive.estertion.win/card/full/100401.webp", "Production 短 ID 首選應為 Estertion card/full WebP");
    assert.strictEqual(prodUrls[1], "https://redive.estertion.win/card/full/100401.png");
    assert.strictEqual(prodUrls.some(u => u.includes("still/story/100401")), false, "Production 不得包含 local still/story");
});

// Test 5 — empty / invalid ID
test("Test 5: empty / invalid ID returns placeholder without throwing", () => {
    const service = createServiceInstance({ hostname: 'smallorange0323.github.io', pathname: '/PCRD_transtool/' });
    const emptyUrls = service.getStillUrls("");
    assert.strictEqual(emptyUrls.length, 1);
    assert.strictEqual(emptyUrls[0], TRANSPARENT_PLACEHOLDER);

    const nullUrls = service.getStillUrls(null);
    assert.strictEqual(nullUrls.length, 1);
    assert.strictEqual(nullUrls[0], TRANSPARENT_PLACEHOLDER);
});

// Test 6 — production path specificity
test("Test 6: production path specificity (other repo path is not production)", () => {
    const service = createServiceInstance({
        hostname: 'smallorange0323.github.io',
        pathname: '/another-project/'
    });

    assert.strictEqual(service.isProductionPages(), false, "非 /PCRD_transtool/ 路徑不得判定為 production");
    const urls = service.getStillUrls("512200601");
    assert.strictEqual(urls[0], "still/story/512200601.webp", "非 production 應保留 local-first");
});

// Test 7 — production with specific subpath /PCRD_transtool/index.html
test("Test 7: production with index.html subpath", () => {
    const service = createServiceInstance({
        hostname: 'smallorange0323.github.io',
        pathname: '/PCRD_transtool/index.html'
    });
    assert.strictEqual(service.isProductionPages(), true, "/PCRD_transtool/index.html 應判定為 production");
});

// Test 8 — getStoryThumbnailUrls candidate order
test("Test 8: getStoryThumbnailUrls candidate order (story -> still -> bg -> fallback)", () => {
    const service = createServiceInstance();
    const urls = service.getStoryThumbnailUrls("2201101", "1001001", "10040");
    assert.strictEqual(urls[0], "icon/story/2201101.webp", "第一候選必須為本地官方縮圖");
    assert(urls.some(u => u.includes("1001001")), "必須包含 still_id 候選");
    assert(urls.some(u => u.includes("10040")), "必須包含 bg_id 候選");
    assert(urls.some(u => u.includes("100431.webp")), "最後必須包含預設卡面保底");
});

// Test 9 — getStoryThumbnailHtml rendering and dataset serialization
test("Test 9: getStoryThumbnailHtml rendering and error fallback data attribute", () => {
    const service = createServiceInstance();
    const html = service.getStoryThumbnailHtml("2201101", null, null, "test-thumb-class", "width:100%;");
    assert(html.includes('src="icon/story/2201101.webp"'), "img src 必須為第一候選");
    assert(html.includes('class="test-thumb-class"'), "img class 必須正確套用");
    assert(html.includes('data-candidates="'), "必須包含已序列化之候選清單");
    assert(html.includes('onerror="StoryAssetService.handleImageError(this)"'), "必須包含 onerror 處理器");
});

// Test 10 — Character candidate order (Option A contract)
test("Test 10: Character candidate order (story -> local card -> remote card -> global default)", () => {
    const service = createServiceInstance();
    const urls = service.getStoryThumbnailUrls("1001001", null, null, { characterGroupId: 1001 });
    assert.strictEqual(urls[0], "icon/story/1001001.webp", "第一候選必須為本地官方縮圖");
    assert.strictEqual(urls[1], "card/100131.webp", "第二候選必須為本機角色 3★ 卡面");
    assert.strictEqual(urls[2], "https://redive.estertion.win/card/full/100131.webp", "第三候選必須為遠端角色 3★ 卡面");
    assert.strictEqual(urls[3], "https://redive.estertion.win/card/full/100431.webp", "最後必須為全域預設卡面保底");
    assert.strictEqual(urls.length, 4, "角色模式候選長度應為 4");
});

// Test 11 — Missing-current-asset scenario
test("Test 11: Missing-current-asset candidate chain (e.g. 1390001)", () => {
    const service = createServiceInstance();
    const urls = service.getStoryThumbnailUrls("1390001", null, null, { characterGroupId: 1390 });
    assert.strictEqual(urls[0], "icon/story/1390001.webp");
    assert.strictEqual(urls[1], "card/139031.webp");
    assert.strictEqual(urls[2], "https://redive.estertion.win/card/full/139031.webp");
    assert.strictEqual(urls[3], "https://redive.estertion.win/card/full/100431.webp");
});

// Test 12 — Character mode ignores still/bg
test("Test 12: Character mode strictly excludes still and background fallbacks", () => {
    const service = createServiceInstance();
    const urls = service.getStoryThumbnailUrls("1001002", "100100201", "502460", { characterGroupId: "1001" });
    assert.strictEqual(urls[0], "icon/story/1001002.webp");
    assert.strictEqual(urls[1], "card/100131.webp");
    assert.strictEqual(urls[2], "https://redive.estertion.win/card/full/100131.webp");
    assert.strictEqual(urls[3], "https://redive.estertion.win/card/full/100431.webp");
    assert.strictEqual(urls.some(u => u.includes("100100201")), false, "不得包含 still 候選");
    assert.strictEqual(urls.some(u => u.includes("502460")), false, "不得包含 bg 候選");
});

// Test 13 — Generic behavior remains unchanged
test("Test 13: Generic behavior remains unchanged when options has no characterGroupId", () => {
    const service = createServiceInstance();
    const urlsNoOpt = service.getStoryThumbnailUrls("2201101", "1001001", "10040");
    const urlsEmptyOpt = service.getStoryThumbnailUrls("2201101", "1001001", "10040", {});
    assert.deepStrictEqual(urlsNoOpt, urlsEmptyOpt, "空 options 與未傳 options 結果必須一致");
    assert.strictEqual(urlsNoOpt[0], "icon/story/2201101.webp");
    assert(urlsNoOpt.some(u => u.includes("1001001")), "必須包含 still 候選");
    assert(urlsNoOpt.some(u => u.includes("10040")), "必須包含 bg 候選");
    assert.strictEqual(urlsNoOpt[urlsNoOpt.length - 1], "https://redive.estertion.win/card/full/100431.webp");
});

// Test 14 — Invalid characterGroupId safely handled
test("Test 14: Invalid characterGroupId safely falls back to generic without generating malformed URLs", () => {
    const service = createServiceInstance();
    const invalidInputs = ["../evil", "1001/foo", "abc", null, "", "1001.31"];
    for (const inv of invalidInputs) {
        const urls = service.getStoryThumbnailUrls("2201101", "1001001", "10040", { characterGroupId: inv });
        assert.strictEqual(urls.some(u => u.includes("../evil")), false, `不安全輸入 ${inv} 不得流入 URL`);
        assert.strictEqual(urls.some(u => u.includes("foo")), false, `不安全輸入 ${inv} 不得流入 URL`);
        if (inv) {
            assert.strictEqual(urls.some(u => u.includes(String(inv))), false, `無效輸入 ${inv} 不得作為路徑片段`);
        }
        // 應安全退回一般通用路徑（第一項為專屬縮圖，最後一項為全域 100431 保底）
        assert.strictEqual(urls[0], "icon/story/2201101.webp");
        assert(urls.some(u => u.includes("1001001")), "應保留一般 still 候選");
    }
});

// Test 15 — HTML serialization with characterGroupId
test("Test 15: getStoryThumbnailHtml renders primary and serializes character card fallbacks", () => {
    const service = createServiceInstance();
    const html = service.getStoryThumbnailHtml("1001001", null, null, "story-thumb-img", "width:100%;", { characterGroupId: 1001 });
    assert(html.includes('src="icon/story/1001001.webp"'), "首選 src 必須為官方話數縮圖");
    assert(html.includes('class="story-thumb-img"'), "class 必須套用");
    assert(html.includes('onerror="StoryAssetService.handleImageError(this)"'), "必須套用 onerror 處理器");

    // 反序列化 data-candidates 驗證
    const match = html.match(/data-candidates="([^"]+)"/);
    assert(match, "必須包含 data-candidates 屬性");
    const candidates = JSON.parse(decodeURIComponent(match[1]));
    assert.deepStrictEqual(candidates, [
        "card/100131.webp",
        "https://redive.estertion.win/card/full/100131.webp",
        "https://redive.estertion.win/card/full/100431.webp"
    ], "data-candidates 必須依序為本機卡面、遠端卡面與全域保底");
});

// Test 16 — Event top thumbnail priority
test("Test 16: getEventTopThumbnailUrls prioritizes icon/event_top over fallbacks", () => {
    const service = createServiceInstance();
    const urls = service.getEventTopThumbnailUrls("5001", "500101", "1001001", "10040");
    assert.strictEqual(urls[0], "icon/event_top/5001.webp", "第一候選必須為官方活動頂層專屬縮圖");
    assert.strictEqual(urls[1], "icon/story/500101.webp", "第二候選必須為首話話數縮圖");
    assert(urls.some(u => u.includes("1001001")), "必須包含 still 候選");
    assert(urls.some(u => u.includes("10040")), "必須包含 bg 候選");
    assert.strictEqual(urls[urls.length - 1], "https://redive.estertion.win/card/full/100431.webp", "最後必須為預設卡面保底");
});

// Test 17 — Graceful fallback when event_top missing / error stepping candidates
test("Test 17: Event top fallback sequence remains ordered and valid for onerror stepping", () => {
    const service = createServiceInstance();
    const urls = service.getEventTopThumbnailUrls("5002", "500201", null, null);
    assert.strictEqual(urls[0], "icon/event_top/5002.webp");
    assert.strictEqual(urls[1], "icon/story/500201.webp");
    assert.strictEqual(urls[2], "https://redive.estertion.win/card/full/100431.webp");
    assert.strictEqual(urls.length, 3);
});

// Test 18 — Defensive handling when event_id is null / undefined / 0 / "0"
test("Test 18: Defensive handling when event_id is null, undefined, 0, '0', or invalid", () => {
    const service = createServiceInstance();
    const invalidEventIds = [null, undefined, 0, "0", "", "   ", "abc", "../evil"];
    for (const inv of invalidEventIds) {
        const urls = service.getEventTopThumbnailUrls(inv, "500101");
        assert.strictEqual(urls.some(u => u.includes("icon/event_top/")), false, `無效 eventId ${inv} 不得產生 event_top URL`);
        assert.strictEqual(urls[0], "icon/story/500101.webp", "無效 eventId 應平滑由 fallbackStoryId 接管");
        assert.strictEqual(urls[urls.length - 1], "https://redive.estertion.win/card/full/100431.webp");
    }

    // 全空極端情況
    const emptyUrls = service.getEventTopThumbnailUrls(null, null);
    assert.strictEqual(emptyUrls.length, 1);
    assert.strictEqual(emptyUrls[0], "https://redive.estertion.win/card/full/100431.webp");
});

// Test 19 — getEventTopThumbnailHtml valid syntax, attribute escaping, and onerror wiring
test("Test 19: getEventTopThumbnailHtml produces valid image tag, escaped attributes, and onerror handler", () => {
    const service = createServiceInstance();
    const html = service.getEventTopThumbnailHtml("5001", "500101", null, null, "event-cover-img", "width:100%;");
    assert(html.startsWith("<img "), "必須以 <img 開頭");
    assert(html.endsWith(">"), "必須以 > 結尾");
    assert(html.includes('src="icon/event_top/5001.webp"'), "首選 src 必須為活動頂層縮圖");
    assert(html.includes('class="event-cover-img"'), "class 屬性必須正確套用");
    assert(html.includes('style="width:100%;"'), "style 屬性必須正確套用");
    assert(html.includes('data-candidates="'), "必須包含 data-candidates 屬性");
    assert(html.includes('data-step="0"'), "必須包含 data-step='0'");
    assert(html.includes('onerror="StoryAssetService.handleImageError(this)"'), "必須包含 onerror 處理器");

    // 反序列化驗證候選網址
    const match = html.match(/data-candidates="([^"]+)"/);
    assert(match, "data-candidates 必須存在");
    const candidates = JSON.parse(decodeURIComponent(match[1]));
    assert.deepStrictEqual(candidates, [
        "icon/story/500101.webp",
        "https://redive.estertion.win/card/full/100431.webp"
    ]);

    // 極端全空防禦測試
    const emptyHtml = service.getEventTopThumbnailHtml(null, null);
    assert(emptyHtml.includes('src="https://redive.estertion.win/card/full/100431.webp"'), "全空時首選 src 應為預設保底卡面");
    assert(emptyHtml.includes('onerror="StoryAssetService.handleImageError(this)"'));
});

// Test 20 — Story thumbnail fallback placeholder ordering (Phase 3 Part A)
test("Test 20: Story thumbnail fallback placeholder ordering contract", () => {
    const service = createServiceInstance();
    const stillId = "100401";
    const bgId = "10001";
    const storyId = "2201101";

    // 1. getStillUrls(id) 預設仍以 transparent GIF 結尾
    const stillUrlsDefault = service.getStillUrls(stillId);
    assert.strictEqual(
        stillUrlsDefault[stillUrlsDefault.length - 1],
        TRANSPARENT_PLACEHOLDER,
        "getStillUrls(id) 預設必須以透明佔位圖結尾"
    );

    // 2. getStillUrls(id, false) 不含 transparent GIF
    const stillUrlsNoPlaceholder = service.getStillUrls(stillId, false);
    assert.strictEqual(
        stillUrlsNoPlaceholder.includes(TRANSPARENT_PLACEHOLDER),
        false,
        "getStillUrls(id, false) 不得包含透明佔位圖"
    );
    assert.strictEqual(
        stillUrlsNoPlaceholder.length,
        stillUrlsDefault.length - 1,
        "getStillUrls(id, false) 長度應為預設長度減 1"
    );

    // 3. getStoryThumbnailUrls(storyId, stillId, bgId) 排序與無佔位符驗證
    const thumbUrls = service.getStoryThumbnailUrls(storyId, stillId, bgId);

    // 4. transparent GIF 不在 getStoryThumbnailUrls() candidates 中
    assert.strictEqual(
        thumbUrls.includes(TRANSPARENT_PLACEHOLDER),
        false,
        "getStoryThumbnailUrls candidates 中嚴禁包含中間透明佔位圖"
    );

    // 驗證順序: story thumbnail -> real still candidates -> real bg candidates -> default card
    const storyIdx = thumbUrls.indexOf(`icon/story/${storyId}.webp`);
    assert.strictEqual(storyIdx, 0, "第一順位必須為官方專屬縮圖");

    // 尋找任一 real still candidate 的 index
    const firstStillUrl = stillUrlsNoPlaceholder[0];
    const stillIdx = thumbUrls.indexOf(firstStillUrl);
    assert(stillIdx > storyIdx, "real still candidate 必須在 story thumbnail 之後");

    // 尋找任一 real bg candidate 的 index
    const bgUrls = service.getBackgroundUrls(bgId);
    const firstBgUrl = bgUrls[0];
    const bgIdx = thumbUrls.indexOf(firstBgUrl);
    assert(bgIdx > stillIdx, "real bg candidate 必須在 real still candidate 之後");

    // 尋找 default card 的 index
    const defaultCardUrl = 'https://redive.estertion.win/card/full/100431.webp';
    const defaultCardIdx = thumbUrls.indexOf(defaultCardUrl);
    assert(defaultCardIdx > bgIdx, "default card 必須在 real bg candidate 之後");

    // 5. handleImageError 所有候選耗盡後仍會使用 transparent GIF
    const mockImg = {
        dataset: {
            step: "1",
            candidates: encodeURIComponent(JSON.stringify(["http://example.com/failed.png"]))
        },
        src: "http://example.com/failed.png"
    };
    // step 為 1，candidates 長度為 1，此時已耗盡
    service.handleImageError(mockImg);
    assert.strictEqual(
        mockImg.src,
        TRANSPARENT_PLACEHOLDER,
        "handleImageError 在候選耗盡時最終必須設置透明佔位圖"
    );
});

console.log(`\n🎉 All ${testsPassed} StoryAssetService tests passed!`);
