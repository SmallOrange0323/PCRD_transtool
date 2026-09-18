'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../dashboard/characters.js'), 'utf8');

const renderStart = source.indexOf('renderLayout(container) {');
const updateStart = source.indexOf('this.updateView = () => {', renderStart);
const renderEnd = source.indexOf('\n    renderGrid(characters) {', updateStart);

assert.ok(renderStart >= 0 && updateStart > renderStart && renderEnd > updateStart,
    'character catalog renderLayout source must be discoverable');

const initialLayout = source.slice(renderStart, updateStart);
const renderLayout = source.slice(renderStart, renderEnd);

assert.match(initialLayout, /<div id="char-grid" class="char-grid"><\/div>/,
    'initial layout must create an empty result container');
assert.ok(!initialLayout.includes('this.renderGrid('),
    'initial layout must not pre-render the grid before updateView');
assert.ok(!initialLayout.includes('this.renderTable('),
    'initial layout must not pre-render the table before updateView');
assert.ok(!initialLayout.includes('this.renderGuildView('),
    'initial layout must not pre-render the guild view before updateView');

assert.match(renderLayout, /searchInput\.addEventListener\('input', \(\) => \{/,
    'search input must use a debounced wrapper');
assert.match(renderLayout, /clearTimeout\(this\._searchDebounceTimer\)/,
    'search debounce must cancel the previous pending update');
assert.match(renderLayout, /setTimeout\(\(\) => \{[\s\S]*?updateView\(\);[\s\S]*?\}, 150\)/,
    'search debounce must update once after 150ms');
assert.match(renderLayout, /char-sort'\)\.addEventListener\('change', updateView\)/,
    'sort changes must remain immediate');

const lastUpdateIndex = renderLayout.lastIndexOf('updateView();');
assert.ok(lastUpdateIndex > renderLayout.indexOf("view-btn-guild"),
    'renderLayout must perform one explicit initial update after event wiring');

console.log('✅ Character catalog render contract passed');
