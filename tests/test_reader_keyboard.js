const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');

function setup() {
    const state = { toggles: 0, stops: 0, active: true, popup: false };
    const document = {
        body: { style: {} },
        getElementById: id => id === 'map-tab' ? { classList: { contains: () => state.active } } : {},
        querySelector: () => state.popup ? {} : null
    };
    const window = { AutoVoiceController: { isActive: () => true } };
    vm.runInNewContext(source, { window, document, console, Map, Set });
    const map = window.QuestMapModule;
    Object.assign(map, { activeStoryId: 1, currentDialogueList: [{}], toggleAutoVoice: () => state.toggles++, stopAutoVoice: () => state.stops++ });
    const event = overrides => ({ key: ' ', code: 'Space', preventDefault() { this.prevented = true; }, target: { closest: () => null }, ...overrides });
    return { map, state, event };
}

test('Space toggles AUTO and Escape stops it while reading', () => {
    const { map, state, event } = setup();
    const space = event();
    map.handleReaderKeydown(space);
    map.handleReaderKeydown(event({ key: 'Escape', code: 'Escape' }));
    assert.equal(space.prevented, true);
    assert.equal(state.toggles, 1);
    assert.equal(state.stops, 1);
});

test('typing, native controls, IME, modifiers, and repeats retain their keys', () => {
    const { map, state, event } = setup();
    for (const overrides of [
        { target: { closest: () => ({}) } }, { target: { isContentEditable: true } },
        { isComposing: true }, { keyCode: 229 }, { repeat: true }, { ctrlKey: true },
        { metaKey: true }, { altKey: true }, { shiftKey: true }, { defaultPrevented: true }
    ]) map.handleReaderKeydown(event(overrides));
    assert.equal(state.toggles, 0);
});

test('hidden reader, loading story and open popup do not start playback', () => {
    const { map, state, event } = setup();
    state.active = false;
    map.handleReaderKeydown(event());
    state.active = true;
    map.isLoadingDialogue = true;
    map.handleReaderKeydown(event());
    map.isLoadingDialogue = false;
    state.popup = true;
    map.handleReaderKeydown(event());
    assert.equal(state.toggles, 0);
});
