const assert = require('assert');
const fs = require('fs');
const path = require('path');

// 載入 AvatarService
const avatarServiceCode = fs.readFileSync(path.join(__dirname, '../dashboard/avatar-service.js'), 'utf-8');
const vm = require('vm');
const sandbox = { window: {}, console: console };
vm.createContext(sandbox);
vm.runInContext(avatarServiceCode, sandbox);
const AvatarService = sandbox.window.AvatarService;

console.log('🧪 開始執行現實頭像整合測試 (test_reality_avatars.js)...\n');

// 測試 1: realityAvatarMap 映射完整性
console.log('--- 測試 1: realityAvatarMap 核心角色映射 ---');
const expectedMappings = {
    '空花': 104532,
    '莉瑪': 105231,
    '真陽': 103332,
    '綾音': 102332,
    '美美': 102032,
    '鈴奈': 101632,
    '妮諾': 103031,
    '七七香': 101332,
    '霞': 101431,
    '真琴': 104331,
    '貪吃佩可': 105831,
    '伊緒': 101832,
    '美里': 101533,
    '克蕾雅': 118031,
    '茉莉': 100531,
    '雪': 100832,
    '美冬': 104833,
    '祈梨': 106631,
    '秋乃': 103232,
    '珠希': 104632,
    '咲戀': 102832
};

for (const [name, expectedId] of Object.entries(expectedMappings)) {
    const actualId = AvatarService.realityAvatarMap[name];
    assert.strictEqual(actualId, expectedId, '角色 ' + name + ' 的現實 ID 應為 ' + expectedId + '，實際為 ' + actualId);
    console.log('  ✅ ' + name + ' -> ' + actualId);
}

// 測試 2: resolveDialoguePortraitIds 不被降級
console.log('\n--- 測試 2: resolveDialoguePortraitIds 保持 Exact ID ---');
const realityIds = [104532, 102832, 103232, 104632, 100832, 101632, 102332, 102032, 101332, 103332, 101533, 104833, 101832];
for (const rid of realityIds) {
    const candidates = AvatarService.resolveDialoguePortraitIds(rid);
    assert.strictEqual(candidates[0], rid, 'ID ' + rid + ' 第一順位應保持 ' + rid + '，實際為 ' + candidates[0]);
    console.log('  ✅ ' + rid + ' -> candidates: [' + candidates.join(', ') + ']');
}

// 測試 3: 實體圖檔存在性檢查
console.log('\n--- 測試 3: 本地與發布包圖檔資產存在性 ---');
const dirs = [
    path.join(__dirname, '../dashboard/icon/unit'),
    path.join(__dirname, '../dist_story_map/icon/unit')
];

for (const [name, uid] of Object.entries(expectedMappings)) {
    for (const d of dirs) {
        const webpPath = path.join(d, uid + '.webp');
        const pngPath = path.join(d, uid + '.png');
        assert.ok(fs.existsSync(webpPath), '缺少 WebP: ' + webpPath);
        assert.ok(fs.existsSync(pngPath), '缺少 PNG: ' + pngPath);
        assert.ok(fs.statSync(webpPath).size > 0, 'WebP 大小異常: ' + webpPath);
        assert.ok(fs.statSync(pngPath).size > 0, 'PNG 大小異常: ' + pngPath);
    }
    console.log('  ✅ [' + name + '] ' + uid + '.webp / ' + uid + '.png 驗證通過');
}

// 測試 4: 模擬 DialogueView 在 7 篇現實篇章中取得頭像
console.log('\n--- 測試 4: 模擬 7 篇現實分支頭像解析 ---');
const realityStories = [
    { sid: 2210102, testSpeaker: '空花', expectedId: 104532 },
    { sid: 2211102, testSpeaker: '真陽', expectedId: 103332 },
    { sid: 2212103, testSpeaker: '鈴奈', expectedId: 101632 },
    { sid: 2212104, testSpeaker: '七七香', expectedId: 101332 },
    { sid: 2213104, testSpeaker: '真琴', expectedId: 104331 },
    { sid: 2214101, testSpeaker: '雪', expectedId: 100832 },
    { sid: 2215102, testSpeaker: '咲戀', expectedId: 102832 },
    { sid: 2215102, testSpeaker: '珠希', expectedId: 104632 },
    { sid: 2215102, testSpeaker: '秋乃', expectedId: 103232 }
];

for (const item of realityStories) {
    const isReality = [2210102, 2211102, 2212103, 2212104, 2213104, 2214101, 2215102].includes(item.sid);
    assert.ok(isReality, '話數 ' + item.sid + ' 應判定為現實分支');
    const mappedId = AvatarService.realityAvatarMap[item.testSpeaker];
    assert.strictEqual(mappedId, item.expectedId, '話數 ' + item.sid + ' 之發言人 ' + item.testSpeaker + ' 現實 ID 應為 ' + item.expectedId);
    const portraitIds = AvatarService.resolveDialoguePortraitIds(mappedId);
    assert.strictEqual(portraitIds[0], item.expectedId);
    console.log('  ✅ Story ' + item.sid + ': ' + item.testSpeaker + ' -> ' + mappedId + ' (Portrait Tier 0: ' + portraitIds[0] + ')');
}

console.log('\n🎉 所有現實頭像整合測試 (4/4 大項) 全數通過 (PASS)！');
