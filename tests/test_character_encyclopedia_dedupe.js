'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// ============================================================================
// 1. 靜態原始碼合約檢查：確認已徹底移除 extraUnits 陣列與注入邏輯
// ============================================================================
const source = fs.readFileSync(path.join(__dirname, '../dashboard/characters.js'), 'utf8');

assert.ok(!source.includes('const extraUnits ='), 'characters.js must not define hardcoded extraUnits');
assert.ok(!source.includes('extraUnits'), 'characters.js must not reference extraUnits anywhere');

// ============================================================================
// 2. 載入 CharactersModule 並建立測試環境（Exercise Production Code Path）
// ============================================================================
global.window = global;
global.localStorage = {
    _data: {},
    getItem(k) { return this._data[k] || null; },
    setItem(k, v) { this._data[k] = String(v); }
};

// 注入偽造的 DOM container 與 fetch
const mockContainer = {
    innerHTML: ''
};
global.document = {
    getElementById(id) {
        if (id === 'characters-tab') return mockContainer;
        if (id === 'char-detail-modal') return { classList: { add() {}, remove() {} } };
        if (id === 'modal-body') return { innerHTML: '' };
        return null;
    },
    querySelector() { return null; }
};

global.fetch = async function (url) {
    return {
        ok: true,
        json: async () => ({})
    };
};

global.AvatarService = {
    getCharacterCardAvatarHtml(unitId, name) {
        return `<img src="icon_${unitId}.png" alt="${name}">`;
    }
};

// 載入正式 production 模組
require(path.join(__dirname, '../dashboard/characters.js'));
const CharactersModule = global.CharactersModule;
assert.ok(CharactersModule && typeof CharactersModule.render === 'function', 'CharactersModule must be loaded');

// 抑制 renderLayout 在測試環境缺少完整 DOM 的報錯
CharactersModule.renderLayout = function () {};

// 執行非同步測試
async function runTests() {
    // ============================================================================
    // 測試案例 1：Exercise production render() path
    // 驗證：authoritative SQL result 不產生 duplicate exact unit_id，
    // 且 extraUnits 不再注入第二筆資料，unit_id 被正規化為 canonical String
    // ============================================================================
    {
        const mockDbRows = [
            { unit_id: "180601", unit_name: "凱留（公主）", rarity: 3, pos: 747, race: "獸人族", guild: "美食殿堂" },
            { unit_id: "180501", unit_name: "可可蘿（公主）", rarity: 3, pos: 545, race: "精靈族", guild: "美食殿堂" },
            { unit_id: "139401", unit_name: "艾麗卡（少戰）", rarity: 3, pos: 322, race: "精靈族", guild: "？？？" },
            { unit_id: "139301", unit_name: "真穗（少戰）", rarity: 3, pos: 700, race: "獸人族", guild: "？？？" },
            { unit_id: "139201", unit_name: "美穗（少戰）", rarity: 1, pos: 486, race: "人類", guild: "？？？" }
        ];

        global.PCRDatabase = {
            runQuery(sql) {
                return mockDbRows;
            }
        };

        // 呼叫並等待真實 production 的 render() 完成
        await CharactersModule.render();

        // 1. 驗證 180601 只有一筆，且 unit_id 型態為 String
        const karylEntries = CharactersModule.allCharacters.filter(c => c.unit_id === "180601");
        assert.equal(karylEntries.length, 1, 'Production render() must produce exactly 1 entry for 180601');
        assert.strictEqual(typeof karylEntries[0].unit_id, 'string', 'unit_id must be canonical String');
        assert.strictEqual(karylEntries[0].unit_name, "凱留（公主）");

        // 2. 驗證 139201, 139301, 139401 來自 DB 查詢結果，而非任何已廢棄的 extraUnits
        const miho = CharactersModule.allCharacters.find(c => c.unit_id === "139201");
        const maho = CharactersModule.allCharacters.find(c => c.unit_id === "139301");
        const erika = CharactersModule.allCharacters.find(c => c.unit_id === "139401");

        assert.ok(miho && maho && erika, '139201, 139301, 139401 must all exist from DB query');
        assert.strictEqual(miho.unit_name, "美穗（少戰）", 'Name should match DB, not old hardcoded fallback');
        assert.strictEqual(miho.pos, 486, '139201 must have valid pos from DB');
        assert.notStrictEqual(miho.race, "??", '139201 race must not be "??"');

        assert.strictEqual(maho.unit_name, "真穗（少戰）");
        assert.strictEqual(maho.pos, 700);
        assert.notStrictEqual(maho.race, "??");

        assert.strictEqual(erika.unit_name, "艾麗卡（少戰）");
        assert.strictEqual(erika.pos, 322);
    }

    // ============================================================================
    // 測試案例 2：驗證前端 identity comparison 與操作統一使用 canonical String unit_id
    // ============================================================================
    {
        // A. 驗證 toggleExclude: 不論傳入 number 180601 或 string "180601"，均以 String("180601") 保存
        CharactersModule.excludedUnitIds.clear();

        // 傳入 number
        CharactersModule.toggleExclude(180601);
        assert.ok(CharactersModule.excludedUnitIds.has("180601"), 'toggleExclude(number) must store string "180601"');
        assert.ok(!CharactersModule.excludedUnitIds.has(180601), 'toggleExclude must not store number type');

        // 傳入 string 取消排除
        CharactersModule.toggleExclude("180601");
        assert.ok(!CharactersModule.excludedUnitIds.has("180601"), 'toggleExclude("180601") must toggle off correctly');

        // B. 驗證 showDetail: activeUnitId 與 profile 查找均正確以 String 匹配
        let queryArgsCaptured = null;
        global.PCRDatabase.runQuery = function (sql, params) {
            queryArgsCaptured = params;
            return [];
        };

        // 傳入 number 139201 給 showDetail
        await CharactersModule.showDetail(139201);
        assert.strictEqual(CharactersModule.activeUnitId, "139201", 'activeUnitId must be canonical String');
    }

    console.log('✅ Character encyclopedia contract & production path tests passed');
}

runTests().catch(err => {
    console.error('Test execution failed:', err);
    process.exit(1);
});
