'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const mapSource = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
const htmlSource = fs.readFileSync(path.join(__dirname, '../dashboard/story_map.html'), 'utf8');

// Landing menu must be rendered before the first data preload await.
const renderStart = mapSource.indexOf('async _render(skipAutoSelect = false)');
const menuCheck = mapSource.indexOf("if (this.currentView === 'menu')", renderStart);
const dataAwait = mapSource.indexOf('await this.loadData();', renderStart);
assert.ok(renderStart >= 0, 'map.js must define _render');
assert.ok(menuCheck > renderStart, 'map.js must keep an explicit landing-menu branch');
assert.ok(dataAwait > menuCheck, 'landing menu must be handled before loadData is awaited');

// Concurrent callers must share one Story Map data-loading promise.
assert.match(mapSource, /_loadDataPromise:\s*null/);
assert.match(mapSource, /if \(this\._loadDataPromise\) \{\s*return this\._loadDataPromise;/);
assert.match(mapSource, /this\._loadDataPromise = this\._loadDataInternal\(\)/);

// SQLite startup remains a single shared promise and is deferred to a later task.
assert.match(htmlSource, /const databaseReadyPromise = new Promise\(\(resolve, reject\) => \{/);
assert.match(htmlSource, /setTimeout\(\(\) => \{[\s\S]*PCRDatabase\.initDatabase/);
assert.match(htmlSource, /window\.PCRD_DATABASE_READY = databaseReadyPromise/);

// The visible menu is rendered before the background full-data readiness chain.
const initialRender = htmlSource.indexOf('await QuestMapModule.render();');
const appReady = htmlSource.indexOf('window.PCRD_APP_READY =');
assert.ok(initialRender >= 0 && appReady > initialRender,
    'first menu render must precede background full-data readiness work');

// Character catalog is DB-backed and must join the same database promise.
assert.match(htmlSource, /tabId === 'characters'[\s\S]*await window\.PCRD_DATABASE_READY/);

console.log('✅ Fast-startup source contract passed');
