'use strict';

let assert;
try {
    assert = require('node:assert/strict');
} catch (_) {
    assert = require('assert').strict || require('assert');
}
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const navSource = fs.readFileSync(path.join(__dirname, '../dashboard/reader-navigation.js'), 'utf8');
const mapSource = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');

function createContractTestHarness(options = {}) {
    const localStorageData = new Map(options.localStorageEntries || []);
    const sessionStorageData = new Map(options.sessionStorageEntries || []);
    const domElements = new Map();
    const createdElements = [];

    function makeMockElement(id, tag = 'div') {
        const listeners = new Map();
        let _text = '';
        const el = {
            id,
            tagName: tag.toUpperCase(),
            className: '',
            style: {},
            children: [],
            disabled: false,
            title: '',
            attributes: {},
            dataset: {},
            get textContent() {
                if (this.children.length === 0) return _text;
                return _text + this.children.map(c => c.textContent).join('');
            },
            set textContent(v) {
                _text = String(v);
                this.children = [];
            },
            innerHTML: '',
            classList: {
                _classes: new Set(),
                add(c) { this._classes.add(c); },
                remove(c) { this._classes.delete(c); },
                contains(c) { return this._classes.has(c); }
            },
            setAttribute(k, v) { this.attributes[k] = v; },
            getAttribute(k) { return this.attributes[k]; },
            appendChild(child) {
                this.children.push(child);
                if (child.id) domElements.set(child.id, child);
            },
            addEventListener(evt, handler) {
                if (!listeners.has(evt)) listeners.set(evt, []);
                listeners.get(evt).push(handler);
            },
            getBoundingClientRect() {
                return { top: 0, bottom: 200, height: 200 };
            },
            scrollIntoView() {},
            querySelectorAll(sel) {
                if (sel === '[data-dialogue-index]') {
                    return this.children.filter(c => c.dataset && 'dialogueIndex' in c.dataset);
                }
                return [];
            },
            querySelector(sel) {
                const list = this.querySelectorAll(sel);
                return list[0] || null;
            },
            remove() {
                domElements.delete(this.id);
                const idx = createdElements.indexOf(this);
                if (idx !== -1) createdElements.splice(idx, 1);
            }
        };
        return el;
    }

    const bodyEl = makeMockElement('body', 'body');
    const mainEl = makeMockElement('main', 'main');
    mainEl.prepend = function (el) {
        domElements.set(el.id, el);
    };
    const navRightEl = makeMockElement('nav-right', 'div');
    const mapTabEl = makeMockElement('map-tab', 'div');
    mapTabEl.classList.add('active');
    const dialogueBoardEl = makeMockElement('dialogue-board', 'div');
    const mapContainerEl = makeMockElement('map-container', 'div');

    domElements.set('body', bodyEl);
    domElements.set('main', mainEl);
    domElements.set('nav-right', navRightEl);
    domElements.set('map-tab', mapTabEl);
    domElements.set('dialogue-board', dialogueBoardEl);

    const doc = {
        body: bodyEl,
        getElementById(id) {
            if (id === 'reader-resume' || id === 'reader-share') {
                if (!domElements.has(id)) domElements.set(id, makeMockElement(id, 'button'));
            }
            return domElements.get(id) || null;
        },
        querySelector(selector) {
            if (selector === '.nav-right') return navRightEl;
            if (selector === 'main') return mainEl;
            if (selector === '.map-container') return mapContainerEl;
            if (selector === '#map-tab') return mapTabEl;
            if (selector === '#dialogue-board') return dialogueBoardEl;
            return null;
        },
        querySelectorAll(selector) {
            if (selector === '.story-item') return [];
            return [];
        },
        createElement(tag) {
            const el = makeMockElement(`elem-${Date.now()}-${Math.random()}`, tag);
            createdElements.push(el);
            return el;
        },
        addEventListener() {}
    };

    const win = {
        location: new URL(options.url || 'https://example.test/'),
        history: {
            pushState(_, __, url) {
                win.location = new URL(url, win.location.href);
            },
            replaceState(_, __, url) {
                win.location = new URL(url, win.location.href);
            }
        },
        scrollTo() {},
        innerWidth: 1024,
        innerHeight: 768,
        AvatarService: {
            getSpeakerAvatar() { return ''; }
        },
        ChapterDataService: {
            load() { return Promise.resolve(); },
            getChapterKey(s) { return s.chapter ? s.chapter.split(' ')[0] : '第1章'; },
            getAllChapters() { return []; },
            getChapterInfo() { return null; }
        },
        StoryAssetService: {
            getChapterThumbnailUrl() { return ''; },
            getStoryThumbnailHtml() { return ''; }
        },
        DialogueView: {
            renderLoading() {},
            renderDialogue() {},
            renderError() {},
            renderEmpty() {},
            clearAutoStartSelection() {},
            clearDialogueHighlight() {}
        },
        fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }),
        addEventListener() {}
    };
    win.window = win;
    win.document = doc;

    const storage = {
        getItem(k) { return localStorageData.get(k) || null; },
        setItem(k, v) { localStorageData.set(k, String(v)); },
        removeItem(k) { localStorageData.delete(k); }
    };
    const sessionStorage = {
        getItem(k) { return sessionStorageData.get(k) || null; },
        setItem(k, v) { sessionStorageData.set(k, String(v)); },
        removeItem(k) { sessionStorageData.delete(k); }
    };

    const ctx = {
        window: win,
        document: doc,
        localStorage: storage,
        sessionStorage: sessionStorage,
        setTimeout(fn, ms) { return setTimeout(fn, ms); },
        clearTimeout(id) { clearTimeout(id); },
        requestAnimationFrame(fn) { return setTimeout(fn, 0); },
        URL,
        URLSearchParams,
        StoryAssetService: win.StoryAssetService,
        DialogueView: win.DialogueView,
        fetch: win.fetch,
        console
    };

    vm.runInNewContext(navSource, ctx);
    vm.runInNewContext(mapSource, ctx);

    const map = win.QuestMapModule;
    const nav = win.ReaderNavigation;

    // 避免 loadData 嘗試連線 DB / fetch
    map._loadDataPromise = Promise.resolve();

    // 準備測試數據
    map.stories = [
        { id: 2001001, chapter: '第1章 第1話', title: '王都的相遇', type: 'main', part: 1 },
        { id: 2001002, chapter: '第1章 第2話', title: '美味的飯糰', type: 'main', part: 1 },
        { id: 2015003, chapter: '第15章 第3話', title: '絕望的戰鬥', type: 'main', part: 1 },
        { id: 2015004, chapter: '第15章 第4話', title: '奇蹟的逆轉', type: 'main', part: 1 },
        { id: 1001001, chapter: '貪吃佩可 第1話', title: '大胃王王女', type: 'chara', charaName: '佩可' },
        { id: 1001002, chapter: '貪吃佩可 第2話', title: '隱藏的秘密', type: 'chara', charaName: '佩可' },
    ];
    map.chapters = {
        '第1章': [map.stories[0], map.stories[1]],
        '第15章': [map.stories[2], map.stories[3]],
        '佩可': [map.stories[4], map.stories[5]]
    };

    // 初始化 ReaderNavigation
    nav.init(map);

    return { win, doc, map, nav, storage, sessionStorage, domElements, dialogueBoardEl };
}

// 輔助函式：模擬設置當前閱讀行
function setupDialogueBoard(dialogueBoardEl, lineIndex = 0) {
    dialogueBoardEl.children = [];
    for (let i = 0; i <= lineIndex + 2; i++) {
        const line = {
            tagName: 'DIV',
            dataset: { dialogueIndex: String(i) },
            getBoundingClientRect: () => ({
                top: i === lineIndex ? 95 : (i < lineIndex ? 50 : 200),
                bottom: i === lineIndex ? 150 : (i < lineIndex ? 90 : 250)
            }),
            scrollIntoView: () => {}
        };
        dialogueBoardEl.children.push(line);
    }
}

async function runTests() {
    console.log('--- 開始執行 Reader / Navigation Contract 回歸測試 ---');

    // ----------------------------------------------------
    // Test A: 被動進入目錄不 auto-select
    // ----------------------------------------------------
    {
        const { map, nav, storage } = createContractTestHarness();
        map.currentView = 'menu';
        assert.equal(map.activeStoryId, null, '初始 activeStoryId 應為 null');

        // 被動進入 main 目錄
        map.enterCategory('main');

        // 等待微任務與事件循環完成
        await new Promise(r => setTimeout(r, 20));

        assert.equal(map.activeStoryId, null, '被動進入目錄後 activeStoryId 必須保持 null (不自動 select 第一話)');
        assert.equal(storage.getItem(nav.storageKey), null, '被動進入目錄不得寫入任何 resume position');
        console.log('✅ Test A Passed: 被動進入目錄不 auto-select');
    }

    // ----------------------------------------------------
    // Test B: 舊 resume 不被目錄瀏覽覆寫
    // ----------------------------------------------------
    {
        const savedPos = { storyId: 2015003, line: 10 };
        const { map, nav, storage } = createContractTestHarness({
            localStorageEntries: [['pcrd_reader_position_v1', JSON.stringify(savedPos)]]
        });

        // 使用者進 main directory 但未點擊任何話數
        map.enterCategory('main');
        await new Promise(r => setTimeout(r, 20));

        // 再次呼叫一般的 directory render
        await map.render();
        await new Promise(r => setTimeout(r, 20));

        const afterPos = JSON.parse(storage.getItem(nav.storageKey));
        assert.deepEqual(afterPos, savedPos, '目錄瀏覽後，舊的閱讀位置必須保持 2015003 / line 10，不得被覆寫');
        console.log('✅ Test B Passed: 舊 resume 不被目錄瀏覽覆寫');
    }

    // ----------------------------------------------------
    // Test C: 使用者主動點 B story 後 Prompt 消失
    // ----------------------------------------------------
    {
        const savedPos = { storyId: 2015003, line: 10 };
        const { map, nav, sessionStorage, doc } = createContractTestHarness({
            localStorageEntries: [['pcrd_reader_position_v1', JSON.stringify(savedPos)]]
        });

        // 模擬顯示 Resume Prompt
        const target = nav.getResumeTarget();
        nav.showResumePrompt(target);

        let toast = doc.getElementById('reader-resume-toast');
        assert.ok(toast, 'showResumePrompt 後 toast 必須存在於 DOM');

        // 使用者主動點擊選擇另一個 story B (2015004)
        await map.selectStory(2015004);

        toast = doc.getElementById('reader-resume-toast');
        assert.equal(toast, null, '使用者主動選擇 story B 後，舊 Prompt 必須立即從 DOM 移除');
        assert.equal(sessionStorage.getItem(nav.sessionPromptKey), '1', 'session seen flag 必須保持已記錄');
        console.log('✅ Test C Passed: 使用者主動點 B story 後 Prompt 消失');
    }

    // ----------------------------------------------------
    // Test D: switchTabType 保存舊 story
    // ----------------------------------------------------
    {
        const { map, nav, storage, dialogueBoardEl } = createContractTestHarness();

        // 準備：正在閱讀 story 2001001，當前在 line 5
        map.activeStoryId = 2001001;
        nav.readyStoryId = 2001001;
        setupDialogueBoard(dialogueBoardEl, 5);

        // 執行切換至 event 分頁
        map.switchTabType('event');

        const saved = JSON.parse(storage.getItem(nav.storageKey));
        assert.ok(saved, 'switchTabType 必須先保存閱讀進度');
        assert.equal(saved.storyId, 2001001, '保存的 storyId 必須為舊 story');
        assert.equal(saved.line, 5, '保存的 line 必須為 5');
        assert.equal(map.activeStoryId, null, 'switchTabType 完成後 activeStoryId 必須為 null');
        console.log('✅ Test D Passed: switchTabType 保存舊 story');
    }

    // ----------------------------------------------------
    // Test E: selectPartFromTab 保存舊 story
    // ----------------------------------------------------
    {
        const { map, nav, storage, dialogueBoardEl } = createContractTestHarness();

        // 準備：正在閱讀 story 2015003，當前在 line 12
        map.activeStoryId = 2015003;
        nav.readyStoryId = 2015003;
        setupDialogueBoard(dialogueBoardEl, 12);

        // 執行 selectPartFromTab(1)
        await map.selectPartFromTab(1);

        const saved = JSON.parse(storage.getItem(nav.storageKey));
        assert.ok(saved, 'selectPartFromTab 必須先保存閱讀進度');
        assert.equal(saved.storyId, 2015003, '保存的 storyId 必須為舊 story');
        assert.equal(saved.line, 12, '保存的 line 必須為 12');
        console.log('✅ Test E Passed: selectPartFromTab 保存舊 story');
    }

    // ----------------------------------------------------
    // Test F: clearActiveChara 完整離開 Reader
    // ----------------------------------------------------
    {
        const { map, nav, win, doc, storage, dialogueBoardEl } = createContractTestHarness();

        // 準備：正在閱讀角色故事 1001001 (佩可)，當前在 line 8
        map.activeTabType = 'chara';
        map.activeCharaName = '佩可';
        map.expandedChapter = '佩可';
        map.activeStoryId = 1001001;
        nav.readyStoryId = 1001001;
        win.location.hash = '#story=1001001';
        const shareBtn = doc.getElementById('reader-share');
        if (shareBtn) shareBtn.disabled = false;
        setupDialogueBoard(dialogueBoardEl, 8);

        // 執行返回角色列表
        map.clearActiveChara();

        const saved = JSON.parse(storage.getItem(nav.storageKey));
        assert.ok(saved, 'clearActiveChara 必須保存角色故事進度');
        assert.equal(saved.storyId, 1001001, '保存的 storyId 為 1001001');
        assert.equal(saved.line, 8, '保存的 line 為 8');

        assert.equal(map.activeStoryId, null, 'activeStoryId 必須為 null');
        assert.equal(map.activeCharaName, null, 'activeCharaName 必須為 null');
        assert.equal(map.expandedChapter, null, 'expandedChapter 必須為 null');
        assert.equal(win.location.hash, '', 'story hash 必須已清空');
        if (shareBtn) assert.equal(shareBtn.disabled, true, 'share 按鈕必須被 disabled');
        assert.equal(nav.readyStoryId, null, 'readyStoryId 必須已重設為 null');
        console.log('✅ Test F Passed: clearActiveChara 完整離開 Reader');
    }

    console.log('\n🎉 ALL NAVIGATION CONTRACT REGRESSION TESTS PASSED!');
}

runTests().catch(err => {
    console.error('❌ Test failed with error:', err);
    process.exit(1);
});
