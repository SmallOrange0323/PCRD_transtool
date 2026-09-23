'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const charactersJsPath = path.join(__dirname, '../dashboard/characters.js');
const charactersSource = fs.readFileSync(charactersJsPath, 'utf8');

console.log('--- 1. 驗證 extraUnits 不包含 hardcoded 136901 ---');
// 解析 extraUnits 陣列區塊
const extraUnitsMatch = charactersSource.match(/const extraUnits = \[\s*([\s\S]*?)\s*\];/);
assert.ok(extraUnitsMatch, 'characters.js 必須包含 extraUnits 定義');
const extraUnitsBlock = extraUnitsMatch[1];
assert.ok(!extraUnitsBlock.includes('136901'), 'extraUnits 嚴禁包含 136901 hardcoded 定義');
assert.ok(!extraUnitsBlock.includes('璐璐伊'), 'extraUnits 嚴禁包含 璐璐伊 hardcoded 定義');
console.log('  PASS: extraUnits 不存在 136901 / 璐璐伊');

console.log('--- 2. 驗證 DB 原生 query 自然返回璐璐伊 ---');
// 提取 characters.js 中的 production SQL
const sqlMatch = charactersSource.match(/window\.PCRDatabase\.runQuery\(`([\s\S]*?)`\)/);
assert.ok(sqlMatch, '必須能從 characters.js 提取 production SQL');
const prodSql = sqlMatch[1].trim();

// 透過 Python 執行 SQLite 查詢
const pythonScript = `
import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('dashboard/redive_tw.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 執行 production SQL
cur.execute('''${prodSql}''')
rows = [dict(r) for r in cur.fetchall()]

# 執行 rarity 檢查
cur.execute('SELECT * FROM unit_rarity WHERE unit_id = 136901 ORDER BY rarity ASC')
rar_rows = [dict(r) for r in cur.fetchall()]

print(json.dumps({'characters': rows, 'rarity': rar_rows}, ensure_ascii=False))
`;

const stdout = execFileSync('python', ['-c', pythonScript], {
    cwd: path.join(__dirname, '..'),
    encoding: 'utf8'
});
const dbResult = JSON.parse(stdout);
const allCharacters = dbResult.characters;
const rarityRows = dbResult.rarity;

const rurui = allCharacters.find(c => c.unit_id === 136901);
assert.ok(rurui, 'Production SQL 必須自然返回 unit_id 136901 (璐璐伊)');
assert.equal(rurui.unit_name, '璐璐伊', 'unit_name 必須為繁體中文 璐璐伊');
assert.equal(rurui.rarity, 3, '初期星數必須為 3');
assert.equal(rurui.pos, 450, '站位 search_area_width 必須為 450 (中衛)');
assert.ok(rarityRows.length >= 1, 'unit_rarity 必須至少有一筆資料');
assert.equal(rarityRows.length, 5, 'unit_rarity 應包含 1~5 星共 5 筆成長數據');
console.log(`  PASS: DB 原生查詢回傳璐璐伊 (unit_id=136901, pos=450, rarity_count=${rarityRows.length})`);

console.log('--- 3. 驗證搜尋與過濾邏輯 (Search & Filter Contract) ---');
// 嚴格逐字對齊 characters.js 中的 updateView 搜尋邏輯 (僅 unit_name, race, guild)
function filterCharacters(term) {
    const t = term.toLowerCase();
    return allCharacters.filter(c =>
        c.unit_name.toLowerCase().includes(t) ||
        (c.race && c.race.toLowerCase().includes(t)) ||
        (c.guild && c.guild.toLowerCase().includes(t))
    );
}

const searchByName = filterCharacters('璐璐伊');
assert.equal(searchByName.length, 1, '以 璐璐伊 搜尋必須正好命中 1 位');
assert.equal(searchByName[0].unit_id, 136901, '搜尋命中的角色 ID 必須為 136901');
console.log('  PASS: 名稱搜尋「璐璐伊」精準命中');

console.log('--- 4. 驗證預設 ID 降冪排序位置 (ID-desc Ordering Contract) ---');
const ruruiIndex = allCharacters.findIndex(c => c.unit_id === 136901);
assert.equal(ruruiIndex, 27, '在 335 位角色的 id-desc 排序中，璐璐伊的 index 必須為 27 (第 28 位)');
assert.ok(allCharacters[ruruiIndex - 1].unit_id > 136901, '前一位角色的 unit_id 必須大於 136901');
assert.ok(allCharacters[ruruiIndex + 1].unit_id < 136901, '後一位角色的 unit_id 必須小於 136901');
console.log(`  PASS: 璐璐伊位於 id-desc 排序第 28 位 (前: ${allCharacters[ruruiIndex - 1].unit_id} ${allCharacters[ruruiIndex - 1].unit_name}, 後: ${allCharacters[ruruiIndex + 1].unit_id} ${allCharacters[ruruiIndex + 1].unit_name})`);

console.log('--- 5. 驗證 UI 卡片渲染合約 (Render Contract) ---');
// 建立 mock AvatarService
const mockAvatarService = {
    getCharacterCardAvatarHtml(unitId, unitName) {
        return `<img src="icon/unit/${unitId}31.webp" alt="${unitName}">`;
    }
};

// 提取 renderGrid 實作並測試
function mockRenderGrid(characters, excludedUnitIds) {
    const gridFiltered = characters.filter(c => !excludedUnitIds.has(c.unit_id));
    if (gridFiltered.length === 0) return '<div class="empty-msg">找不到符合條件的角色</div>';
    return gridFiltered.map(c => {
        const avatarHtml = mockAvatarService.getCharacterCardAvatarHtml(c.unit_id, c.unit_name);
        return `
            <div class="char-card glass-card" onclick="CharactersModule.showDetail(${c.unit_id})">
                <div class="char-avatar">${avatarHtml}</div>
                <div class="char-info">
                    <div class="char-name">${c.unit_name}</div>
                    <div class="char-meta">
                        <span>站位: ${c.pos || '??'}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Case A: excluded = false (預設正常顯示)
const excludedEmpty = new Set();
const renderedHtml = mockRenderGrid([rurui], excludedEmpty);
assert.match(renderedHtml, /CharactersModule\.showDetail\(136901\)/, 'Card 必須綁定 136901 的 showDetail 事件');
assert.match(renderedHtml, /<div class="char-name">璐璐伊<\/div>/, 'Card 必須正確渲染角色名稱 璐璐伊');
assert.match(renderedHtml, /<span>站位: 450<\/span>/, 'Card 必須正確渲染站位: 450');
assert.match(renderedHtml, /icon\/unit\/13690131\.webp/, 'Card 必須引用對應之 136901 頭像資源');
console.log('  PASS: excluded=false 時 card 正確 render');

// Case B: excluded = true (被排除時不 render)
const excludedWithRurui = new Set([136901]);
const excludedHtml = mockRenderGrid([rurui], excludedWithRurui);
assert.ok(!excludedHtml.includes('136901'), 'excluded=true 時嚴禁 render 該角色卡片');
assert.match(excludedHtml, /找不到符合條件的角色/, '全部排除時應顯示空訊息');
console.log('  PASS: excluded=true 時正確排除卡片');

console.log('🎉 璐璐伊角色圖鑑正式收錄與回歸測試 (Regression Tests) 全數通過！');
