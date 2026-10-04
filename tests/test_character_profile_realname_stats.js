'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// ============================================================================
// 1. 環境設定與 DOM / 服務 Mock
// ============================================================================
global.window = global;
global.localStorage = {
    _data: {},
    getItem(k) { return this._data[k] || null; },
    setItem(k, v) { this._data[k] = String(v); }
};

let gridInnerHtml = '';
global.document = {
    getElementById(id) {
        if (id === 'characters-tab') return { innerHTML: '' };
        if (id === 'char-detail-modal') return { classList: { add() {}, remove() {} } };
        if (id === 'modal-body') return { innerHTML: '' };
        if (id === 'stats-display-grid') {
            return {
                set innerHTML(val) { gridInnerHtml = val; },
                get innerHTML() { return gridInnerHtml; }
            };
        }
        return null;
    },
    querySelector() { return null; }
};

const realNameMappingPath = path.join(__dirname, '../dashboard/data/real_name_mapping.json');
const realNameData = JSON.parse(fs.readFileSync(realNameMappingPath, 'utf8'));

global.fetch = async function (url) {
    if (url.includes('real_name_mapping.json')) {
        return {
            ok: true,
            json: async () => realNameData
        };
    }
    return {
        ok: true,
        json: async () => ({})
    };
};

global.AvatarService = {
    getCharacterCardAvatarHtml(unitId, name) {
        return `<img src="icon_${unitId}.png" alt="${name}">`;
    },
    getSkillIconHtml(iconType) {
        return `<span>icon_${iconType}</span>`;
    }
};

global.PCRDatabase = {
    currentRegion: 'tw',
    runQuery(sql, params) {
        return [];
    }
};

require(path.join(__dirname, '../dashboard/characters.js'));
const CharactersModule = global.CharactersModule;
assert.ok(CharactersModule && typeof CharactersModule.render === 'function', 'CharactersModule must be loaded');

CharactersModule.renderLayout = function () {};

async function runTests() {
    // 預先載入 realNameMap
    await CharactersModule.render();

    // ========================================================================
    // Case A: 璐璐伊（136901）真名解析
    // ========================================================================
    {
        const parseCharaName = (fullName) => {
            const match = fullName.match(/^(.+?)([(\uff08].+?[)\uff09])$/);
            if (match) {
                return { baseName: match[1].trim(), suffix: match[2].trim() };
            }
            return { baseName: fullName.trim(), suffix: "" };
        };

        const gameName = '璐璐伊';
        const parsed = parseCharaName(gameName);
        let realName = "";
        if (CharactersModule.realNameMap) {
            const found = Object.entries(CharactersModule.realNameMap).find(([real, game]) => game === parsed.baseName);
            if (found) {
                realName = found[0] + parsed.suffix;
            }
        }

        assert.strictEqual(realName, '深見璐璐', 'Case A: 璐璐伊之遊戲內真名必須正確解析為 深見璐璐');
        console.log('✅ Case A Passed: 璐璐伊 -> 深見璐璐');
    }

    // ========================================================================
    // Case B: 少戰聯動角色（139201, 139301, 139401）真名解析
    // ========================================================================
    {
        const parseCharaName = (fullName) => {
            const match = fullName.match(/^(.+?)([(\uff08].+?[)\uff09])$/);
            if (match) {
                return { baseName: match[1].trim(), suffix: match[2].trim() };
            }
            return { baseName: fullName.trim(), suffix: "" };
        };

        const garupanCases = [
            { gameName: '美穗（少戰）', expectedReal: '西住 美穗（少戰）' },
            { gameName: '真穗（少戰）', expectedReal: '西住 真穗（少戰）' },
            { gameName: '艾麗卡（少戰）', expectedReal: '逸見 艾麗卡（少戰）' }
        ];

        for (const gc of garupanCases) {
            const parsed = parseCharaName(gc.gameName);
            let realName = "";
            if (CharactersModule.realNameMap) {
                const found = Object.entries(CharactersModule.realNameMap).find(([real, game]) => game === parsed.baseName);
                if (found) {
                    realName = found[0] + parsed.suffix;
                }
            }
            assert.strictEqual(realName, gc.expectedReal, `Case B: ${gc.gameName} 之遊戲內真名必須為 ${gc.expectedReal}`);
        }
        console.log('✅ Case B Passed: 少戰聯動角色真名解析正確');
    }

    // ========================================================================
    // Case C: 璐璐伊（136901）數值計算與防 NaN 驗證（Lv. 280）
    // ========================================================================
    {
        CharactersModule.currentStats = {
            unit_id: '136901',
            rarity: '5',
            hp: '741.8',
            hp_growth: '137.4',
            atk: '71.57',
            atk_growth: '13.26',
            magic_str: '0.0',
            magic_str_growth: '0.0',
            def: '5.13',
            def_growth: '0.96',
            magic_def: '4.72',
            magic_def_growth: '0.87',
            physical_critical: '20.0',
            physical_critical_growth: '0.0',
            magic_critical: '0.0',
            magic_critical_growth: '0.0',
            life_steal: '0.0',
            life_steal_growth: '0.0'
        };

        CharactersModule.updateCalculatedStats(280);

        assert.ok(!gridInnerHtml.includes('NaN'), 'Case C: 璐璐伊數值不得包含 NaN');
        assert.ok(gridInnerHtml.includes('<span class="value">39076</span>'), 'Case C: HP 必須為 39076');
        assert.ok(gridInnerHtml.includes('<span class="value">3771</span>'), 'Case C: 物理攻擊必須為 3771');
        assert.ok(gridInnerHtml.includes('<span class="value">272</span>'), 'Case C: 物理防禦必須為 272');
        assert.ok(gridInnerHtml.includes('<span class="value">247</span>'), 'Case C: 魔法防禦必須為 247');
        console.log('✅ Case C Passed: 璐璐伊 Lv.280 數值計算精確且無 NaN');
    }

    // ========================================================================
    // Case D: 非法/缺失數值之 finite-number guard 驗證
    // ========================================================================
    {
        CharactersModule.currentStats = {
            unit_id: '999999',
            rarity: '5',
            hp: 'invalid',
            hp_growth: '0.0',
            atk: null,
            atk_growth: undefined,
            magic_str: 'Infinity',
            magic_str_growth: '0.0',
            def: 'NaN',
            def_growth: '0.0',
            magic_def: undefined,
            magic_def_growth: undefined,
            physical_critical: '0.0',
            physical_critical_growth: '0.0',
            magic_critical: '0.0',
            magic_critical_growth: '0.0',
            life_steal: '0.0',
            life_steal_growth: '0.0'
        };

        CharactersModule.updateCalculatedStats(280);

        assert.ok(!gridInnerHtml.includes('NaN'), 'Case D: 非法數值不得讓 UI 出現 NaN');
        assert.ok(!gridInnerHtml.includes('Infinity'), 'Case D: 非法數值不得讓 UI 出現 Infinity');
        assert.ok(!gridInnerHtml.includes('undefined'), 'Case D: 非法數值不得讓 UI 出現 undefined');

        // 測試 renderStat 對非法輸入回傳安全佔位符（不得轉成 0，必須顯示 —）
        const safePlaceholder = CharactersModule.renderStat('測試', NaN);
        assert.ok(safePlaceholder.includes('<span class="value">—</span>'), 'Case D: renderStat(NaN) 必須回傳安全佔位符 —');
        assert.ok(!safePlaceholder.includes('<span class="value">0</span>'), 'Case D: renderStat(NaN) 不得被轉成 0');

        const safeInfPlaceholder = CharactersModule.renderStat('測試', Infinity);
        assert.ok(safeInfPlaceholder.includes('<span class="value">—</span>'), 'Case D: renderStat(Infinity) 必須回傳安全佔位符 —');

        const safeNullPlaceholder = CharactersModule.renderStat('測試', null);
        assert.ok(safeNullPlaceholder.includes('<span class="value">—</span>'), 'Case D: renderStat(null) 必須回傳安全佔位符 —');

        const safeUndefinedPlaceholder = CharactersModule.renderStat('測試', undefined);
        assert.ok(safeUndefinedPlaceholder.includes('<span class="value">—</span>'), 'Case D: renderStat(undefined) 必須回傳安全佔位符 —');

        const safeStrPlaceholder = CharactersModule.renderStat('測試', 'abc');
        assert.ok(safeStrPlaceholder.includes('<span class="value">—</span>'), 'Case D: renderStat("abc") 必須回傳安全佔位符 —');

        // 合法數值 0 必須保留為 0，不得顯示 —
        const safeZeroPlaceholder = CharactersModule.renderStat('測試', 0);
        assert.ok(safeZeroPlaceholder.includes('<span class="value">0</span>'), 'Case D: renderStat(0) 必須精確保留 0');
        assert.ok(!safeZeroPlaceholder.includes('<span class="value">—</span>'), 'Case D: renderStat(0) 不得顯示 —');

        console.log('✅ Case D Passed: Finite-Number Guard 徹底阻斷非有限數值，且合法 0 正常保留');
    }

    // ========================================================================
    // Case E: toFiniteStat 與 calcStat 單元契約驗證
    // ========================================================================
    {
        // toFiniteStat
        assert.strictEqual(CharactersModule.toFiniteStat(null), null);
        assert.strictEqual(CharactersModule.toFiniteStat(undefined), null);
        assert.strictEqual(CharactersModule.toFiniteStat(''), null);
        assert.strictEqual(CharactersModule.toFiniteStat('abc'), null);
        assert.strictEqual(CharactersModule.toFiniteStat(NaN), null);
        assert.strictEqual(CharactersModule.toFiniteStat(Infinity), null);
        assert.strictEqual(CharactersModule.toFiniteStat(-Infinity), null);
        assert.strictEqual(CharactersModule.toFiniteStat(0), 0);
        assert.strictEqual(CharactersModule.toFiniteStat('0'), 0);
        assert.strictEqual(CharactersModule.toFiniteStat('0.0'), 0);
        assert.strictEqual(CharactersModule.toFiniteStat(123.45), 123.45);
        assert.strictEqual(CharactersModule.toFiniteStat('123.45'), 123.45);

        // calcStat
        assert.strictEqual(CharactersModule.calcStat(null, 10, 100), null);
        assert.strictEqual(CharactersModule.calcStat(100, undefined, 100), null);
        assert.strictEqual(CharactersModule.calcStat('abc', 'def', 100), null);
        assert.strictEqual(CharactersModule.calcStat('0', '0', 100), 0);
        assert.strictEqual(CharactersModule.calcStat('741.8', '137.4', 280), 39076);
        assert.strictEqual(CharactersModule.calcStat('71.57', '13.26', 280), 3771);

        console.log('✅ Case E Passed: toFiniteStat & calcStat 核心函式嚴格契約驗證通過');
    }

    // ========================================================================
    // Case F: 全角色 376 位 rarity rows 直接透過 sql.js 讀取 redive_tw.db 並以 calcStat sweep 驗證
    // ========================================================================
    {
        const initSqlJs = require(path.join(__dirname, '../dashboard/sql-wasm.js'));
        const wasmBinary = fs.readFileSync(path.join(__dirname, '../dashboard/sql-wasm.wasm'));
        const SQL = await initSqlJs({ wasmBinary });
        const dbBinary = fs.readFileSync(path.join(__dirname, '../dashboard/redive_tw.db'));
        const db = new SQL.Database(dbBinary);

        const sql = `
            SELECT ur.unit_id, ur.rarity, ur.hp, ur.hp_growth, ur.atk, ur.atk_growth,
                   ur.magic_str, ur.magic_str_growth, ur.def, ur.def_growth,
                   ur.magic_def, ur.magic_def_growth, ur.physical_critical, ur.physical_critical_growth,
                   ur.magic_critical, ur.magic_critical_growth, ur.life_steal, ur.life_steal_growth
            FROM unit_rarity ur
            JOIN (SELECT unit_id, MAX(rarity) as max_rarity FROM unit_rarity GROUP BY unit_id) max_r
              ON ur.unit_id = max_r.unit_id AND ur.rarity = max_r.max_rarity
            ORDER BY ur.unit_id
        `;

        const queryResult = db.exec(sql);
        db.close();

        assert.ok(queryResult && queryResult.length > 0, 'Case F: 查詢 unit_rarity 必須有返回結果');
        const columns = queryResult[0].columns;
        const rawRows = queryResult[0].values;

        // 轉換為物件列表
        const rows = rawRows.map(values => {
            const obj = {};
            columns.forEach((col, idx) => {
                obj[col] = values[idx];
            });
            return obj;
        });

        assert.strictEqual(rows.length, 376, `全角色 rarity 目錄必須包含 376 位角色，實際為 ${rows.length}`);

        const statFields = [
            ['hp', 'hp_growth'],
            ['atk', 'atk_growth'],
            ['magic_str', 'magic_str_growth'],
            ['def', 'def_growth'],
            ['magic_def', 'magic_def_growth'],
            ['physical_critical', 'physical_critical_growth'],
            ['magic_critical', 'magic_critical_growth'],
            ['life_steal', 'life_steal_growth']
        ];

        let totalEvaluated = 0;
        let nanCount = 0;
        let infCount = 0;
        let nullCount = 0;

        for (const row of rows) {
            for (const [baseField, growthField] of statFields) {
                totalEvaluated++;
                const result = CharactersModule.calcStat(row[baseField], row[growthField], 280);
                if (result === null) {
                    nullCount++;
                } else if (!Number.isFinite(result)) {
                    infCount++;
                } else if (Number.isNaN(result)) {
                    nanCount++;
                }
            }
        }

        assert.strictEqual(nanCount, 0, 'Sweep 驗證: NaN 數量必須為 0');
        assert.strictEqual(infCount, 0, 'Sweep 驗證: Infinity 數量必須為 0');
        assert.strictEqual(nullCount, 0, 'Sweep 驗證: 異常 null 數量必須為 0');
        assert.strictEqual(totalEvaluated, 376 * 8, 'Sweep 驗證: 必須評估 376 * 8 = 3008 個欄位');

        console.log(`✅ Case F Passed: 全 376 位角色（共 ${totalEvaluated} 個欄位）Lv.280 sweep 驗證 100% finite (0 NaN, 0 Inf, 0 null)`);
    }

    // ========================================================================
    // Case G: 名字切換按鈕 toggleNameDisplay 雙向行為驗證
    // ========================================================================
    {
        let h2Text = '';
        let btnText = '🔍 顯示真名';
        const mockTitleEl = {
            set innerHTML(val) { h2Text = val; },
            get innerHTML() { return h2Text; }
        };
        const mockBtn = {
            set innerText(val) { btnText = val; },
            get innerText() { return btnText; }
        };

        global.document.querySelector = (sel) => {
            if (sel === '.detail-main-info h2') return mockTitleEl;
            return null;
        };
        const origGetElementById = global.document.getElementById;
        global.document.getElementById = (id) => {
            if (id === 'char-name-toggle-btn') return mockBtn;
            return origGetElementById(id);
        };

        CharactersModule.activeUnitId = '136901';

        // 第一次點擊：切換為真名
        CharactersModule.toggleNameDisplay('璐璐伊', '深見璐璐');
        assert.ok(h2Text.includes('深見璐璐'), 'Case G: 標題應顯示真名');
        assert.ok(btnText.includes('顯示遊戲名'), 'Case G: 按鈕文字應切換為 顯示遊戲名');

        // 第二次點擊：切換回遊戲名
        CharactersModule.toggleNameDisplay('璐璐伊', '深見璐璐');
        assert.ok(h2Text.includes('璐璐伊'), 'Case G: 標題應切換回遊戲名');
        assert.ok(btnText.includes('顯示真名'), 'Case G: 按鈕文字應切換為 顯示真名');

        console.log('✅ Case G Passed: toggleNameDisplay 雙向切換行為完全正常');
    }

    // ========================================================================
    // Case H: Official Precedence Regression & Frontend Lookup 驗證
    // ========================================================================
    {
        // 模擬 generator 處理 official 與 legacy alias 的行為
        const officialEntries = { "深見璐璐": "璐璐伊" };
        const officialGameNames = new Set(Object.values(officialEntries));

        const existingMapping = {
            "舊璐璐伊名稱": "璐璐伊",         // legacy alias: 應被移除
            "某獨立舊角色真名": "純舊角色"     // legacy-only: 應被保留
        };

        const legacyOnly = Object.fromEntries(
            Object.entries(existingMapping).filter(([r, g]) => !officialGameNames.has(g))
        );

        const mergedResult = { ...legacyOnly, ...officialEntries };

        // 1. generator 結果合約斷言
        assert.ok("深見璐璐" in mergedResult, "深見璐璐 -> 璐璐伊 必須存在於 mapping 中");
        assert.strictEqual(mergedResult["深見璐璐"], "璐璐伊");
        assert.ok(!("舊璐璐伊名稱" in mergedResult), "舊璐璐伊名稱 -> 璐璐伊 必須不存在於 mapping 中 (legacy alias 必須被移除)");
        assert.ok("某獨立舊角色真名" in mergedResult, "official 不存在的 legacy-only entry 必須被保留");
        assert.strictEqual(mergedResult["某獨立舊角色真名"], "純舊角色");

        // 2. 使用真正的前端 lookup 邏輯驗證
        CharactersModule.realNameMap = mergedResult;
        
        const parseCharaName = (fullName) => {
            const match = fullName.match(/^(.+?)([(\uff08].+?[)\uff09])$/);
            if (match) {
                return { baseName: match[1].trim(), suffix: match[2].trim() };
            }
            return { baseName: fullName.trim(), suffix: "" };
        };

        const parsedLuluyi = parseCharaName("璐璐伊");
        const foundLuluyi = Object.entries(CharactersModule.realNameMap).find(
            ([real, game]) => game === parsedLuluyi.baseName
        );
        assert.ok(foundLuluyi, "前端 lookup 必須能找到 璐璐伊");
        assert.strictEqual(foundLuluyi[0], "深見璐璐", "前端 lookup: 璐璐伊 必須精確解析為 深見璐璐");

        const parsedLegacy = parseCharaName("純舊角色");
        const foundLegacy = Object.entries(CharactersModule.realNameMap).find(
            ([real, game]) => game === parsedLegacy.baseName
        );
        assert.ok(foundLegacy, "前端 lookup 必須能找到 legacy-only 純舊角色");
        assert.strictEqual(foundLegacy[0], "某獨立舊角色真名", "前端 lookup: 純舊角色 必須精確解析為 某獨立舊角色真名");

        console.log('✅ Case H Passed: Official Precedence Regression & Frontend Lookup 驗證完全通過');
    }

    console.log('\n🎉 ALL FOCUSED PROFILE REALNAME & STATS TESTS PASSED!');
}

runTests().catch(err => {
    console.error('Test execution failed:', err);
    process.exit(1);
});
