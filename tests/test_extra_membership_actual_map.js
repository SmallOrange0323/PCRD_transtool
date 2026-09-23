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
assert.strictEqual(typeof QuestMapModule.getExtraMembership, 'function', 'getExtraMembership must be a function on QuestMapModule');

// 3. 裝載真實 extraStoryIndex 到 QuestMapModule
QuestMapModule.extraStoryIndex = extraStoryIndex;

// 4. 提供受控 stories 集合 (模擬載入之 DB 話數)
const story9002002 = { id: 9002002, groupId: 9002, title: '倒數第14天', type: 'tower' };
const story7999999 = { id: 7999999, groupId: 7999, title: '未歸類塔話數', type: 'tower' };
const story4004001 = { id: 4004001, groupId: 4004, title: '地底來的侵略者', type: 'tower' };

QuestMapModule.stories = [
    story9002002,
    story7999999,
    story4004001
];

console.log('=== Running Actual dashboard/map.js getExtraMembership Regression Tests ===');

// Test 1: 9002001 (explicit anchor) -> anniversary_countdown, isSeriesChild: false
const m9002001 = QuestMapModule.getExtraMembership(9002001);
assert.ok(m9002001, '9002001 must have extra membership');
assert.strictEqual(m9002001.categoryId, 'anniversary_countdown', '9002001 categoryId must be anniversary_countdown');
assert.strictEqual(m9002001.isSeriesChild, false, '9002001 isSeriesChild must be false (explicit anchor)');
console.log('  [PASS] Test 1: 9002001 -> anniversary_countdown / isSeriesChild false');

// Test 2: 9002002 (real story object with groupId 9002) -> anniversary_countdown, isSeriesChild: true
// 2A: by ID lookup through this.stories
const m9002002ById = QuestMapModule.getExtraMembership(9002002);
assert.ok(m9002002ById, '9002002 by ID must resolve membership through loaded story object');
assert.strictEqual(m9002002ById.categoryId, 'anniversary_countdown', '9002002 categoryId must be anniversary_countdown');
assert.strictEqual(m9002002ById.isSeriesChild, true, '9002002 isSeriesChild must be true');

// 2B: by direct story object
const m9002002ByObj = QuestMapModule.getExtraMembership(story9002002);
assert.ok(m9002002ByObj, 'story9002002 by object must resolve membership');
assert.strictEqual(m9002002ByObj.categoryId, 'anniversary_countdown', 'story9002002 categoryId must be anniversary_countdown');
assert.strictEqual(m9002002ByObj.isSeriesChild, true, 'story9002002 isSeriesChild must be true');
console.log('  [PASS] Test 2: 9002002 (with real groupId 9002) -> anniversary_countdown / isSeriesChild true');

// Test 3: 9002999 (不存在於 this.stories，非 explicit entry) -> 嚴格 null，絕不得猜測 Anniversary
const m9002999 = QuestMapModule.getExtraMembership(9002999);
assert.strictEqual(m9002999, null, 'Non-existent 9002999 must strictly return null, no Math.floor fallback allowed');
console.log('  [PASS] Test 3: 9002999 (non-existent) -> strictly null (no Math.floor guess)');

// Test 4: 7999999 (一般塔劇情，非 Extra) -> null
const m7999999 = QuestMapModule.getExtraMembership(7999999);
assert.strictEqual(m7999999, null, '7999999 must return null');
console.log('  [PASS] Test 4: 7999999 -> null');

// Test 5: 4004001 (mechanical_rima explicit entry) -> mechanical_rima, isSeriesChild: false
const m4004001 = QuestMapModule.getExtraMembership(4004001);
assert.ok(m4004001, '4004001 must resolve extra membership');
assert.strictEqual(m4004001.categoryId, 'mechanical_rima', '4004001 categoryId must be mechanical_rima');
assert.strictEqual(m4004001.isSeriesChild, false, '4004001 isSeriesChild must be false');
console.log('  [PASS] Test 5: 4004001 -> mechanical_rima');

console.log('\n✅ All Actual dashboard/map.js getExtraMembership Regression Tests PASSED successfully!');
