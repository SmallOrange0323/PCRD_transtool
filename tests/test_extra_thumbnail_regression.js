const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

// 1. 載入真實 extra_story_index.json
const extraStoryIndexPath = path.join(__dirname, '../dashboard/data/extra_story_index.json');
const extraStoryIndex = JSON.parse(fs.readFileSync(extraStoryIndexPath, 'utf8'));

// 2. 透過 Node vm 載入真實 dashboard/map.js
const mapCode = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
const sandbox = {
    window: {
        addEventListener: () => {}
    },
    console: console,
    document: {},
    Map: Map,
    Set: Set
};
vm.createContext(sandbox);
vm.runInContext(mapCode, sandbox);

const QuestMapModule = sandbox.window.QuestMapModule;
assert.ok(QuestMapModule, 'QuestMapModule must be loaded from map.js');
assert.strictEqual(typeof QuestMapModule.resolveExtraDirectoryThumbnail, 'function', 'resolveExtraDirectoryThumbnail must be a function on QuestMapModule');

// 裝載 extraStoryIndex 到 QuestMapModule
QuestMapModule.extraStoryIndex = extraStoryIndex;

// Helper to assert descriptor across vm boundaries
function assertDescriptorEqual(actual, expected, msg) {
    if (expected === null) {
        assert.strictEqual(actual, null, msg);
    } else {
        assert.ok(actual, `${msg}: actual is null/undefined`);
        assert.strictEqual(actual.kind, expected.kind, `${msg} (kind mismatch)`);
        assert.strictEqual(actual.id, expected.id, `${msg} (id mismatch)`);
    }
}

console.log('=== Running Focused Extra Thumbnail Regression Tests ===');

// Helper to get category by ID
function getCat(id) {
    return QuestMapModule.getExtraCategory(id);
}

// ----------------------------------------------------
// Test 1: mechanical_rima -> exstory_top / 4006 (NOT 4004)
// ----------------------------------------------------
const mechCat = getCat('mechanical_rima');
assert.ok(mechCat, 'mechanical_rima category must exist in index');
const mechResult = QuestMapModule.resolveExtraDirectoryThumbnail(
    mechCat,
    '機械莉瑪特別劇情',
    [{ id: 4004001, title: '地底來的侵略者' }]
);
assertDescriptorEqual(mechResult, { kind: 'exstory_top', id: '4006' }, 'mechanical_rima must resolve to exstory_top/4006');
assert.notStrictEqual(mechResult?.id, '4004', 'mechanical_rima must NOT guess 4004 from story ID');
console.log('  [PASS] Test 1: mechanical_rima -> exstory_top/4006 (strictly not 4004)');

// ----------------------------------------------------
// Test 2: grand_masters / 1001 -> null
// ----------------------------------------------------
const gmCat = getCat('grand_masters');
assert.ok(gmCat, 'grand_masters category must exist in index');
const gmResult = QuestMapModule.resolveExtraDirectoryThumbnail(
    gmCat,
    'Grand Masters 特別劇情',
    [{ id: 1001, title: 'GAME START！' }]
);
assertDescriptorEqual(gmResult, null, 'grand_masters must resolve to null (text-only contract)');
console.log('  [PASS] Test 2: grand_masters / 1001 -> null');

// ----------------------------------------------------
// Test 3: karyl_yabaival / 1003 -> null
// ----------------------------------------------------
const karylCat = getCat('karyl_yabaival');
assert.ok(karylCat, 'karyl_yabaival category must exist in index');
const karylResult = QuestMapModule.resolveExtraDirectoryThumbnail(
    karylCat,
    'キャル＆ヤバイバル',
    [{ id: 1003, title: 'キャル＆ヤバイバル' }]
);
assertDescriptorEqual(karylResult, null, 'karyl_yabaival must resolve to null (text-only contract)');
console.log('  [PASS] Test 3: karyl_yabaival / 1003 -> null');

// ----------------------------------------------------
// Test 4: gindaco_oedo_summer / 1004 -> null
// ----------------------------------------------------
const gindacoCat = getCat('gindaco_oedo_summer');
assert.ok(gindacoCat, 'gindaco_oedo_summer category must exist in index');
const gindacoResult = QuestMapModule.resolveExtraDirectoryThumbnail(
    gindacoCat,
    '銀だこハイボール酒場 × オーエド横丁夏祭',
    [{ id: 1004, title: 'オーエド横丁夏祭り・屋台攻略戦' }]
);
assertDescriptorEqual(gindacoResult, null, 'gindaco_oedo_summer must resolve to null (text-only contract)');
console.log('  [PASS] Test 4: gindaco_oedo_summer / 1004 -> null');

// ----------------------------------------------------
// Test 5: luna_tower 第 1 期 -> tower_top / 7001
// ----------------------------------------------------
const lunaCat = getCat('luna_tower');
assert.ok(lunaCat, 'luna_tower category must exist in index');
const luna1Result = QuestMapModule.resolveExtraDirectoryThumbnail(
    lunaCat,
    '第 1 期',
    [{ id: 7001000 }]
);
assertDescriptorEqual(luna1Result, { kind: 'tower_top', id: '7001' }, 'luna_tower period 1 must resolve to tower_top/7001');
console.log('  [PASS] Test 5: luna_tower 第 1 期 -> tower_top/7001');

// ----------------------------------------------------
// Test 6: luna_tower 第 30 期 -> tower_top / 7030
// ----------------------------------------------------
const luna30Result = QuestMapModule.resolveExtraDirectoryThumbnail(
    lunaCat,
    '第 30 期',
    [{ id: 7030000 }]
);
assertDescriptorEqual(luna30Result, { kind: 'tower_top', id: '7030' }, 'luna_tower period 30 must resolve to tower_top/7030');
console.log('  [PASS] Test 6: luna_tower 第 30 期 -> tower_top/7030');

// ----------------------------------------------------
// Test 7: anniversary_countdown different series -> respective story thumbnail ID
// ----------------------------------------------------
const anniCat = getCat('anniversary_countdown');
assert.ok(anniCat, 'anniversary_countdown category must exist in index');

// Series 1: 0.5 週年倒數 (first story 9002001)
const anni1Result = QuestMapModule.resolveExtraDirectoryThumbnail(
    anniCat,
    '0.5 週年倒數',
    [{ id: 9002001 }, { id: 9002002 }]
);
assertDescriptorEqual(anni1Result, { kind: 'story', id: '9002001' }, 'Anniversary series 1 must resolve to story/9002001');

// Series 2: 1 週年倒數 (first story 9002018)
const anni2Result = QuestMapModule.resolveExtraDirectoryThumbnail(
    anniCat,
    '1 週年倒數',
    [{ id: 9002018 }, { id: 9002019 }]
);
assertDescriptorEqual(anni2Result, { kind: 'story', id: '9002018' }, 'Anniversary series 2 must resolve to story/9002018');

// Series 3: 2 週年倒數 (first story 9002050)
const anni3Result = QuestMapModule.resolveExtraDirectoryThumbnail(
    anniCat,
    '2 週年倒數',
    [{ id: 9002050 }]
);
assertDescriptorEqual(anni3Result, { kind: 'story', id: '9002050' }, 'Anniversary series 3 must resolve to story/9002050');

assert.notStrictEqual(anni1Result.id, anni2Result.id, 'Different anniversary series must have different thumbnail IDs');
assert.notStrictEqual(anni2Result.id, anni3Result.id, 'Different anniversary series must NOT be hardcoded to 9002001');
console.log('  [PASS] Test 7: anniversary_countdown series resolve to respective story IDs (9002001, 9002018, 9002050)');

// ----------------------------------------------------
// Test 8: Special Story Items 1001-1005 text-only contract check
// ----------------------------------------------------
[1001, 1002, 1003, 1004, 1005].forEach(sid => {
    const itemHtml = QuestMapModule.getStoryItemHtml(
        { id: sid, title: `Test ${sid}`, isEvent: false, type: 'extra' },
        '特別故事',
        `Test ${sid}`
    );
    assert.ok(!itemHtml.includes('<img'), `Story ${sid} must NOT render <img> tag in text-only contract`);
    assert.ok(!itemHtml.includes(`icon/story/${sid}.webp`), `Story ${sid} must NOT request icon/story/${sid}.webp`);
    assert.ok(!itemHtml.includes('card/full/100431.webp'), `Story ${sid} must NOT fall back to unrelated default card`);
    assert.ok(itemHtml.includes('📖'), `Story ${sid} must render existing neutral icon`);
});
console.log('  [PASS] Test 8: Special stories 1001~1005 strictly render text-only neutral icon without <img> or fallback requests');

console.log('\n✅ All Focused Extra Thumbnail Regression Tests PASSED successfully!');
