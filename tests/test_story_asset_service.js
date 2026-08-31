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

console.log(`\n🎉 All ${testsPassed} StoryAssetService tests passed!`);
