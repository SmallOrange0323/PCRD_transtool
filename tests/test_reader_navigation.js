const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../dashboard/reader-navigation.js'), 'utf8');

function setup() {
    const storage = new Map();
    const frames = [];
    const elements = new Map();
    const moves = [];
    const lines = [0, 1, 2].map(index => ({ dataset: { dialogueIndex: String(index) }, getBoundingClientRect: () => ({ bottom: index * 100 }), scrollIntoView: () => moves.push(index) }));
    elements.set('dialogue-board', { querySelectorAll: () => lines, querySelector: s => lines[Number(s.match(/"(\d+)"/)[1])], getBoundingClientRect: () => ({ top: 0 }) });
    elements.set('map-tab', { classList: { contains: () => true } });
    elements.set('reader-navigation-status', { textContent: '' });
    const window = { location: new URL('https://example.test/reader'), history: { pushState(_, __, url) { window.location = new URL(url); } } };
    vm.runInNewContext(source, { window, document: { getElementById: id => elements.get(id) }, localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) }, URL, URLSearchParams, requestAnimationFrame: fn => frames.push(fn), setTimeout });
    const nav = window.ReaderNavigation;
    nav.map = { activeStoryId: 1, _storyRenderToken: 1, getStoryById: id => id === 1 ? { title: 'test' } : null };
    return { nav, window, storage, frames, moves, elements, flush() { while (frames.length) frames.shift()(); } };
}

test('malformed, negative and oversized route positions are rejected', () => {
    const { nav } = setup();
    for (const value of [null, {}, { storyId: '<script>' }, { storyId: 0 }, { storyId: 1, line: -1 }, { storyId: 1, line: 1.5 }, { storyId: 1, line: 100001 }]) assert.equal(nav.parsePosition(value), null);
    assert.equal(nav.parsePosition({ storyId: '1001001', line: '20' }).line, 20);
});

test('reading progress stores only story and line and selected updates shareable URL', () => {
    const { nav, window, storage } = setup();
    nav.readyStoryId = 1;
    nav.savePosition();
    assert.deepEqual(JSON.parse(storage.get(nav.storageKey)), { storyId: 1, line: 1 });
    nav.selected(1);
    assert.equal(window.location.hash, '#story=1');
});

test('restoration waits for live dialogue and clamps a removed line', () => {
    const state = setup();
    state.nav.restore = { storyId: 1, line: 999 };
    state.nav.dialogueReady(1);
    assert.deepEqual(state.moves, []);
    state.flush();
    assert.deepEqual(state.moves, [2]);
    assert.equal(state.nav.restore, null);
});

test('stale render cannot scroll or overwrite progress', () => {
    const state = setup();
    state.nav.restore = { storyId: 1, line: 2 };
    state.nav.dialogueReady(1);
    state.nav.map._storyRenderToken++;
    state.flush();
    assert.deepEqual(state.moves, []);
    assert.equal(state.storage.size, 0);
});

test('unknown route is reported without changing the current story', async () => {
    const { nav } = setup();
    await nav.open({ storyId: 9, line: 0 });
    assert.equal(nav.map.activeStoryId, 1);
});

test('movie-only story can be resumed and shared at its beginning', () => {
    const state = setup();
    // No dialogue lines is a valid movie-only episode.
    state.elements.get('dialogue-board').querySelectorAll = () => [];
    state.nav.dialogueReady(1);
    state.flush();
    assert.equal(state.nav.readyStoryId, 1);
    assert.deepEqual(JSON.parse(state.storage.get(state.nav.storageKey)), { storyId: 1, line: 0 });
});
