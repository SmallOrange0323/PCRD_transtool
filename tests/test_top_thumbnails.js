/**
 * test_top_thumbnails.js
 * 驗證公會、額外劇情與露娜塔頂層縮圖之完整性與 StoryAssetService 介面契約
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const ROOT = path.resolve(__dirname, '..');
const DASHBOARD = path.join(ROOT, 'dashboard');

// 1. 載入 StoryAssetService
const serviceCode = fs.readFileSync(path.join(DASHBOARD, 'story-asset-service.js'), 'utf-8');
const vm = require('vm');
const sandbox = {
    window: {},
    console: console,
    encodeURIComponent: encodeURIComponent,
    decodeURIComponent: decodeURIComponent,
    JSON: JSON
};
vm.createContext(sandbox);
vm.runInContext(serviceCode, sandbox);
const StoryAssetService = sandbox.window.StoryAssetService;

assert(StoryAssetService, 'StoryAssetService 必須成功載入');
console.log('✅ StoryAssetService 載入成功');

// 2. 驗證公會頂層縮圖 (19 個)
const guildIds = [
    3001, 3002, 3003, 3004, 3005, 3006, 3007, 3008, 3009, 3010,
    3011, 3012, 3013, 3014, 3015, 3016, 3017, 3022, 3101
];
for (const gid of guildIds) {
    const filePath = path.join(DASHBOARD, 'icon', 'guild_top', `${gid}.webp`);
    assert(fs.existsSync(filePath), `公會縮圖檔案必須存在: ${filePath}`);
    assert(fs.statSync(filePath).size > 0, `公會縮圖不可為空: ${filePath}`);

    const urls = StoryAssetService.getGuildTopThumbnailUrls(gid, 3001001);
    assert.strictEqual(urls[0], `icon/guild_top/${gid}.webp`, `首選網址必須是 icon/guild_top/${gid}.webp`);

    const html = StoryAssetService.getGuildTopThumbnailHtml(gid, 3001001, null, null, 'test-class');
    assert(html.includes(`src="icon/guild_top/${gid}.webp"`), 'HTML 必須包含正確首選 src');
    assert(html.includes('class="test-class"'), 'HTML 必須包含指定 class');
}
console.log(`✅ 通過全部 ${guildIds.length} 個公會頂層縮圖檔案與 HTML 契約測試`);

// 3. 驗證額外劇情分類縮圖 (12 個)
const exstoryIds = [
    4001, 4002, 4003, 4005, 4006, 4007, 4008, 4009, 4010, 4011, 4013, 4015
];
for (const cid of exstoryIds) {
    const filePath = path.join(DASHBOARD, 'icon', 'exstory_top', `${cid}.webp`);
    assert(fs.existsSync(filePath), `額外分類縮圖必須存在: ${filePath}`);
    assert(fs.statSync(filePath).size > 0, `額外分類縮圖不可為空: ${filePath}`);

    const urls = StoryAssetService.getExStoryTopThumbnailUrls(cid, 4001001);
    assert.strictEqual(urls[0], `icon/exstory_top/${cid}.webp`, `首選網址必須是 icon/exstory_top/${cid}.webp`);

    const html = StoryAssetService.getExStoryTopThumbnailHtml(cid, 4001001);
    assert(html.includes(`src="icon/exstory_top/${cid}.webp"`), 'HTML 必須包含正確首選 src');
}
console.log(`✅ 通過全部 ${exstoryIds.length} 個額外劇情分類頂層縮圖檔案與 HTML 契約測試`);

// 4. 驗證露娜之塔期數縮圖 (30 個)
const towerIds = Array.from({ length: 30 }, (_, i) => 7001 + i);
for (const tid of towerIds) {
    const filePath = path.join(DASHBOARD, 'icon', 'tower_top', `${tid}.webp`);
    assert(fs.existsSync(filePath), `露娜塔期數縮圖必須存在: ${filePath}`);
    assert(fs.statSync(filePath).size > 0, `露娜塔期數縮圖不可為空: ${filePath}`);

    const urls = StoryAssetService.getTowerTopThumbnailUrls(tid, 7001001);
    assert.strictEqual(urls[0], `icon/tower_top/${tid}.webp`, `首選網址必須是 icon/tower_top/${tid}.webp`);

    const html = StoryAssetService.getTowerTopThumbnailHtml(tid, 7001001);
    assert(html.includes(`src="icon/tower_top/${tid}.webp"`), 'HTML 必須包含正確首選 src');
}
console.log(`✅ 通過全部 ${towerIds.length} 個露娜之塔期數頂層縮圖檔案與 HTML 契約測試`);

// 5. 驗證 extra_story_index.json 中的代表縮圖
const extraIndex = JSON.parse(fs.readFileSync(path.join(DASHBOARD, 'data', 'extra_story_index.json'), 'utf-8'));
let checkedRepCount = 0;
for (const group of ['official_categories', 'legacy_categories']) {
    for (const cat of extraIndex[group] || []) {
        const rep = cat.representativeStoryThumbnail;
        if (rep) {
            const repPath = path.join(DASHBOARD, rep);
            assert(fs.existsSync(repPath), `extra_story_index.json 代表縮圖必須存在於本地: ${repPath}`);
            checkedRepCount++;
        }
    }
}
console.log(`✅ 通過 ${checkedRepCount} 個 extra_story_index.json 代表縮圖實體檔案校驗`);

console.log('\n🎉 所有頂層縮圖與服務測試全數 PASS！');
