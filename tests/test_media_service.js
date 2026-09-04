/**
 * 單元測試：MediaService (getVoiceCandidates)
 * 驗證語音候選 URL 清單生成、groupId 擷取、CDN 鏡像優先順序與邊界條件。
 */

const assert = require('assert');
const path = require('path');

// 載入待測模組
global.window = global;
const mediaServicePath = path.resolve(__dirname, '../dashboard/media-service.js');
require(mediaServicePath);

const MediaService = global.MediaService || window.MediaService;

assert(MediaService, 'MediaService 必須正確載入並暴露於全域');

console.log('開始執行 MediaService 測試案例...');

// Case 1: 正常 voiceName 解析 (7-14 位為 groupId)
{
    const voiceName = 'vo_adv_1001001_001';
    // substring(7, 14) -> '1001001'
    const candidates = MediaService.getVoiceCandidates(voiceName);
    assert.strictEqual(candidates.length, 3, '應產生 3 個候選 URL');
    assert.strictEqual(candidates[0], 'sound/story_vo/vo_adv_1001001_001.m4a', '第 1 順位必須為本地目錄');
    assert.strictEqual(candidates[1], 'https://prcn-sound.estertion.win/story_vo/1001001/vo_adv_1001001_001.m4a', '第 2 順位必須為 prcn-sound 鏡像');
    assert.strictEqual(candidates[2], 'https://redive.estertion.win/sound/story_vo/1001001/vo_adv_1001001_001.m4a', '第 3 順位必須為 redive 鏡像');
}

// Case 2: 另一種 voiceName 格式
{
    const voiceName = 'vo_adv_5045001_005';
    const candidates = MediaService.getVoiceCandidates(voiceName);
    assert.strictEqual(candidates[0], 'sound/story_vo/vo_adv_5045001_005.m4a');
    assert.strictEqual(candidates[1], 'https://prcn-sound.estertion.win/story_vo/5045001/vo_adv_5045001_005.m4a');
    assert.strictEqual(candidates[2], 'https://redive.estertion.win/sound/story_vo/5045001/vo_adv_5045001_005.m4a');
}

// Case 3: 空值或無效輸入
{
    assert.deepStrictEqual(MediaService.getVoiceCandidates(''), [], '空字串應回傳空陣列');
    assert.deepStrictEqual(MediaService.getVoiceCandidates(null), [], 'null 應回傳空陣列');
    assert.deepStrictEqual(MediaService.getVoiceCandidates(undefined), [], 'undefined 應回傳空陣列');
    assert.deepStrictEqual(MediaService.getVoiceCandidates(123), [], '非字串應回傳空陣列');
}

console.log('MediaService voice tests passed.');

// ==================================================
// Movie Feature Focused Tests (5-Point Verification)
// ==================================================
console.log('\n開始執行 Movie Feature 聚焦測試案例 (5項指標)...');

// 1. movie ID normalization
{
    assert.strictEqual(MediaService.normalizeMovieId('movie_2213101'), '2213101');
    assert.strictEqual(MediaService.normalizeMovieId('story_2213101'), '2213101');
    assert.strictEqual(MediaService.normalizeMovieId('2213101'), '2213101');
    assert.strictEqual(MediaService.normalizeMovieId(2213101), '2213101');
    assert.strictEqual(MediaService.normalizeMovieId(''), '');
    assert.strictEqual(MediaService.normalizeMovieId(null), '');
    assert.strictEqual(MediaService.normalizeMovieId(undefined), '');
    console.log('  [PASS] 1. movie ID normalization');
}

// 2. movie_links lookup
{
    const mockLinks = {
        '2213101': 'gdrive_id_101',
        'story_2213102': 'gdrive_id_102'
    };
    assert.strictEqual(MediaService.lookupMovieGdriveId('movie_2213101', mockLinks), 'gdrive_id_101');
    assert.strictEqual(MediaService.lookupMovieGdriveId('2213101', mockLinks), 'gdrive_id_101');
    assert.strictEqual(MediaService.lookupMovieGdriveId('movie_2213102', mockLinks), 'gdrive_id_102');
    assert.strictEqual(MediaService.lookupMovieGdriveId('story_2213102', mockLinks), 'gdrive_id_102');
    assert.strictEqual(MediaService.lookupMovieGdriveId('2213103', mockLinks), null);
    assert.strictEqual(MediaService.lookupMovieGdriveId('2213101', null), null);
    console.log('  [PASS] 2. movie_links lookup');
}

// 3. mapped ID -> Google Drive preview URL
{
    assert.strictEqual(MediaService.getMoviePreviewUrl('1a2b3c4d'), 'https://drive.google.com/file/d/1a2b3c4d/preview');
    assert.strictEqual(MediaService.getMoviePreviewUrl(''), null);
    assert.strictEqual(MediaService.getMoviePreviewUrl(null), null);
    console.log('  [PASS] 3. mapped ID -> Google Drive preview URL');
}

// 4. missing mapping -> fallback message
{
    const fallbackHtml = MediaService.getMovieFallbackHtml('2213109');
    assert(fallbackHtml.includes('story_2213109'), 'Fallback 必須包含動畫標識 story_2213109');
    assert(fallbackHtml.includes('此動畫正在準備上傳至 Google Drive'), 'Fallback 必須包含提示訊息');
    console.log('  [PASS] 4. missing mapping -> fallback message');
}

// 5. close popup clears iframe/body
{
    let elements = {};
    const mockDoc = {
        getElementById(id) {
            return elements[id] || null;
        },
        createElement(tag) {
            const el = {
                id: '',
                className: '',
                classList: {
                    classes: new Set(),
                    add(c) { this.classes.add(c); },
                    remove(c) { this.classes.delete(c); },
                    contains(c) { return this.classes.has(c); }
                },
                innerHTML: '',
                style: {},
                addEventListener(evt, fn) {}
            };
            return el;
        },
        body: {
            style: { overflow: '' },
            appendChild(el) {
                if (el.id) elements[el.id] = el;
                // mock sub element movie-player-body inside modal
                const bodyEl = mockDoc.createElement('div');
                bodyEl.id = 'movie-player-body';
                elements['movie-player-body'] = bodyEl;
            }
        }
    };

    const mockLinks = { '2213101': 'mock_drive_id_101' };

    // 5a. open popup with mapped ID
    MediaService.openMoviePopup('movie_2213101', mockLinks, mockDoc);
    const modal = elements['movie-player-modal'];
    const bodyEl = elements['movie-player-body'];
    assert(modal, 'Modal 元素必須被建立');
    assert(modal.classList.contains('active'), '開啟後 Modal 必須帶有 active class');
    assert(bodyEl.innerHTML.includes('iframe src="https://drive.google.com/file/d/mock_drive_id_101/preview"'), '必須注入 Google Drive 預覽 iframe');
    assert.strictEqual(mockDoc.body.style.overflow, 'hidden', '開啟後 body 必須鎖定捲動');

    // 5b. close popup clears iframe/body
    MediaService.closeMoviePopup(mockDoc);
    assert(!modal.classList.contains('active'), '關閉後 active class 必須被移除');
    assert.strictEqual(bodyEl.innerHTML, '', '關閉後 bodyEl 必須被清空 (無殘留 iframe)');
    assert.strictEqual(mockDoc.body.style.overflow, '', '關閉後 body 捲動必須還原');

    // 5c. open popup with unmapped ID -> fallback
    MediaService.openMoviePopup('movie_9999999', mockLinks, mockDoc);
    assert(modal.classList.contains('active'), '開啟未映射動畫 Modal 必須帶有 active');
    assert(bodyEl.innerHTML.includes('story_9999999'), '未映射動畫必須顯示 fallback 訊息');
    assert(!bodyEl.innerHTML.includes('iframe'), '未映射動畫不能有 iframe');

    // 5d. close again
    MediaService.closeMoviePopup(mockDoc);
    assert.strictEqual(bodyEl.innerHTML, '', '第二次關閉亦必須清空 bodyEl');
    console.log('  [PASS] 5. close popup clears iframe/body');
}

console.log('\n✅ All MediaService and Movie Feature tests passed successfully!');
