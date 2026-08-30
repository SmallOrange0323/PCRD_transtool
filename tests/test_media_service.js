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

console.log('MediaService tests passed.');
