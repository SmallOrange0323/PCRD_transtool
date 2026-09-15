const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');

function setup() {
    const synopsis = { style: {}, textContent: '' };
    const shell = {};
    const window = { innerWidth: 390, StoryDataService: { getOfficialSynopsis: async () => '佑樹的故事' } };
    const document = { getElementById: id => id === 'official-synopsis-content' ? synopsis : shell };
    vm.runInNewContext(source, { window, document, console, Map, Set });
    const map = window.QuestMapModule;
    Object.assign(map, { activeStoryId: 1, _storyRenderToken: 2, getStoryById: () => ({ id: 1 }), getQuickDirectoryHtml: () => 'directory', updateSummaryTabsUI() {} });
    return { map, window, synopsis, shell };
}

test('mobile shell offers collapsed official synopsis without loading it', () => {
    const { map, window, shell } = setup();
    let requests = 0;
    window.StoryDataService.getOfficialSynopsis = () => { requests++; };
    map.updateSummaryContent(2);
    assert.match(shell.innerHTML, /<details class="mobile-official-synopsis"/);
    assert.match(shell.innerHTML, /if\(this.open\)/);
    assert.equal(requests, 0);
});

test('mobile synopsis loads on demand and escapes via textContent', async () => {
    const { map, window, synopsis } = setup();
    window.StoryDataService.getOfficialSynopsis = async () => '<b>{player}</b>';
    await map.refreshOfficialSynopsis(1, 2);
    assert.equal(synopsis.textContent, '<b>佑樹</b>');
});

test('delayed synopsis cannot overwrite a newer story', async () => {
    const { map, window, synopsis } = setup();
    let resolve;
    window.StoryDataService.getOfficialSynopsis = () => new Promise(r => { resolve = r; });
    const pending = map.refreshOfficialSynopsis(1, 2);
    map.activeStoryId = 3;
    map._storyRenderToken++;
    resolve('old story');
    await pending;
    assert.equal(synopsis.textContent, '');
});
