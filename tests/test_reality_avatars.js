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

console.log('🧪 開始執行全角色現實生活頭像完整性測試 (test_reality_avatars.js)...\n');

// 載入全量映射字典
const mappingPath = path.join(__dirname, '../dashboard/avatar_reality_mapping.json');
assert.ok(fs.existsSync(mappingPath), '缺少 avatar_reality_mapping.json 檔案！');
const fullMapping = JSON.parse(fs.readFileSync(mappingPath, 'utf-8'));
const uniqueRealityIds = Array.from(new Set(Object.values(fullMapping))).sort((a, b) => a - b);

console.log(`📊 統計指標: 總映射詞條數 ${Object.keys(fullMapping).length} 條, 唯一現實頭像數 ${uniqueRealityIds.length} 個\n`);

// 測試 1: 核心角色與主角群、七冠現實姓名映射測試
console.log('--- 測試 1: 核心角色、主角群、七冠與第3部角色現實映射 ---');
const keyCharacters = {
    // 第 3 部分支 7 篇核心角色
    '空花': 104532, '遠見 空花': 104532,
    '莉瑪': 105231,
    '真陽': 103332, '野戶 真陽': 103332,
    '綾音': 102332, '北條 綾音': 102332,
    '美美': 102032, '茜 美美': 102032,
    '鈴奈': 101632, '美波 鈴奈': 101632,
    '妮諾': 103031, '妮諾・珠貝爾': 103031,
    '七七香': 101332, '丹野 七七香': 101332,
    '霞': 101431, '霧原 霞': 101431,
    '真琴': 104331, '安芸 真琴': 104331,
    '貪吃佩可': 105831, '佩可': 105831, '尤絲蒂亞娜‧F‧阿斯特賴亞': 105831,
    '伊緒': 101832, '支倉 伊緒': 101832,
    '美里': 101533, '愛川 美里': 101533,
    '克蕾雅': 118031, '克蕾雅‧波洋希亞': 118031,
    '茉莉': 100531, '織原 茉莉': 100531,
    '雪': 100832, '虹村 雪': 100832,
    '美冬': 104833, '大泉 美冬': 104833,
    '祈梨': 106631, '一之瀨 祈梨': 106631,
    '秋乃': 103232, '藤堂 秋乃': 103232,
    '珠希': 104632, '宮坂 珠希': 104632,
    '咲戀': 102832, '佐佐木 咲戀': 102832,
    // 美食殿堂與破曉之星
    '可可蘿': 105932, '棗可蘿': 105932,
    '凱留': 106031, '百地希留耶': 106031,
    '日和': 100132, '春咲日和': 100132,
    '優衣': 100232, '草野優衣': 100232,
    '怜': 100332, '士條怜': 100332,
    // 七冠
    '拉比林斯達': 106832, '模索路晶': 106832,
    '似似花': 107032, '現士場黑江': 107032,
    '克莉絲提娜': 107131,
    '霸瞳皇帝': 106931, '千里真那': 106931,
    // 第 3 部角色
    '雪菲': 106432, '阿賀斗紫布菜': 106432,
    '萊拉耶爾': 126532, '祓樹艾爾': 126532,
    // 重要騎士團角色
    '純': 104732, '白銀純': 104732,
    '智': 103732, '御久間智': 103732,
    '靜流': 104932, '星野靜流': 104932,
    '璃乃': 101131, '衣之咲璃乃': 101131
};

let passCount = 0;
for (const [name, expectedId] of Object.entries(keyCharacters)) {
    const actualId = AvatarService.realityAvatarMap[name];
    assert.strictEqual(actualId, expectedId, `角色 ${name} 的現實 ID 應為 ${expectedId}，實際為 ${actualId}`);
    passCount++;
}
console.log(`  ✅ ${passCount}/${Object.keys(keyCharacters).length} 個關鍵角色現實名稱對應驗證成功！`);

// 測試 2: exactRealityIds 與 resolveDialoguePortraitIds 完整性
console.log('\n--- 測試 2: 109 個現實頭像全部納入 exactRealityIds 且不被降級 ---');
for (const rid of uniqueRealityIds) {
    assert.ok(AvatarService.exactRealityIds.has(rid), `ID ${rid} 應存在於 exactRealityIds 集合中`);
    const candidates = AvatarService.resolveDialoguePortraitIds(rid);
    assert.strictEqual(candidates[0], rid, `ID ${rid} 第一順位應保持 ${rid}，實際為 ${candidates[0]}`);
}
console.log(`  ✅ 全部 ${uniqueRealityIds.length} 個現實頭像 ID 均保持 Exact ID，絕無被降級回退問題！`);

// 測試 3: 實體圖檔全量存在性檢查 (dashboard 與 dist_story_map)
console.log('\n--- 測試 3: 檢查全量 109 個現實頭像圖檔資產 (WebP 與 PNG) ---');
const dirs = [
    path.join(__dirname, '../dashboard/icon/unit'),
    path.join(__dirname, '../dist_story_map/icon/unit')
];

let checkedFiles = 0;
for (const uid of uniqueRealityIds) {
    for (const d of dirs) {
        const webpPath = path.join(d, `${uid}.webp`);
        const pngPath = path.join(d, `${uid}.png`);
        assert.ok(fs.existsSync(webpPath), `缺少 WebP: ${webpPath}`);
        assert.ok(fs.existsSync(pngPath), `缺少 PNG: ${pngPath}`);
        assert.ok(fs.statSync(webpPath).size > 0, `WebP 大小異常: ${webpPath}`);
        assert.ok(fs.statSync(pngPath).size > 0, `PNG 大小異常: ${pngPath}`);
        checkedFiles += 2;
    }
}
console.log(`  ✅ 成功驗證 ${checkedFiles} 個圖檔檔案 (${uniqueRealityIds.length} 個頭像 × 2 種格式 × 2 個發布目錄)，全數存在且大小均大於 0！`);

// 測試 4: 模擬 DialogueView 在現實篇章中取得發言人頭像
console.log('\n--- 測試 4: 模擬 DialogueView 在現實分支中解析頭像 ---');
const testSpeakers = [
    { name: '空花', isReality: true, expected: 104532 },
    { name: '遠見 空花', isReality: true, expected: 104532 },
    { name: '真陽', isReality: true, expected: 103332 },
    { name: '鈴奈', isReality: true, expected: 101632 },
    { name: '七七香', isReality: true, expected: 101332 },
    { name: '真琴', isReality: true, expected: 104331 },
    { name: '雪', isReality: true, expected: 100832 },
    { name: '咲戀', isReality: true, expected: 102832 },
    { name: '珠希', isReality: true, expected: 104632 },
    { name: '秋乃', isReality: true, expected: 103232 },
    { name: '可可蘿', isReality: true, expected: 105932 },
    { name: '凱留', isReality: true, expected: 106031 },
    { name: '佩可', isReality: true, expected: 105831 },
    { name: '春咲日和', isReality: true, expected: 100132 },
    { name: '草野優衣', isReality: true, expected: 100232 },
    { name: '白銀純', isReality: true, expected: 104732 },
    // 非現實章節應走原本預設（如 customMap 或 null）
    { name: '空花', isReality: false, expectedNot: 104532 }
];

for (const tc of testSpeakers) {
    const resId = AvatarService.getUnitId(tc.name, {}, tc.isReality);
    if (tc.expected) {
        assert.strictEqual(resId, tc.expected, `[${tc.name}] 在 isReality=${tc.isReality} 下應得到 ${tc.expected}，實際為 ${resId}`);
    }
    if (tc.expectedNot) {
        assert.notStrictEqual(resId, tc.expectedNot, `[${tc.name}] 在 isReality=${tc.isReality} 下不應得到現實 ID ${tc.expectedNot}`);
    }
    console.log(`  ✅ [${tc.name}] (isReality: ${tc.isReality}) -> unit_id: ${resId}`);
}

console.log('\n🎉 全角色現實生活頭像完整性整合測試 (4/4 大項) 全數通過 (PASS)！');
