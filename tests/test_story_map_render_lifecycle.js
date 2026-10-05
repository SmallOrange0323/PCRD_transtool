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

const mapSource = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
const navSource = fs.readFileSync(path.join(__dirname, '../dashboard/reader-navigation.js'), 'utf8');

function createLifecycleTestHarness(options = {}) {
    const localStorageData = new Map();
    const sessionStorageData = new Map();
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
    mainEl.prepend = function (el) { domElements.set(el.id, el); };
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
            pushState(_, __, url) { win.location = new URL(url, win.location.href); },
            replaceState(_, __, url) { win.location = new URL(url, win.location.href); }
        },
        scrollTo() {},
        innerWidth: 1024,
        innerHeight: 768,
        AvatarService: { getSpeakerAvatar() { return ''; } },
        ChapterDataService: {
            load() { return Promise.resolve(); },
            getChapterKey(part, groupId, chapter) {
                if (typeof part === 'object' && part) return part.chapter ? part.chapter.split(' ')[0] : '第1章';
                return chapter ? chapter.split(' ')[0] : '第1章';
            },
            getAllChapters() { return []; },
            getChapterInfo() { return null; }
        },
        StoryAssetService: new Proxy({
            getChapterThumbnailUrl() { return ''; },
            getStoryThumbnailHtml() { return ''; },
            getEventTopThumbnailHtml() { return ''; }
        }, {
            get(target, prop) {
                if (prop in target) return target[prop];
                return () => '';
            }
        }),
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

    // 準備標準備用測試數據
    const mainStories = [
        { id: 2001001, chapter: '第1章 第1話', title: '王都的相遇', type: 'main', part: 1 },
        { id: 2001002, chapter: '第1章 第2話', title: '美味的飯糰', type: 'main', part: 1 },
        { id: 2015003, chapter: '第15章 第3話', title: '絕望的戰鬥', type: 'main', part: 1 },
        { id: 2015004, chapter: '第15章 第4話', title: '奇蹟的逆轉', type: 'main', part: 1 }
    ];
    const eventStories = [
        { id: 5001001, chapter: '初音的禮物 第1話', title: '序幕', type: 'event', isEvent: true, groupId: 5001 },
        { id: 5001002, chapter: '初音的禮物 第2話', title: '相遇', type: 'event', isEvent: true, groupId: 5001 }
    ];
    const events = [
        { title: '初音的禮物', story_group_id: 5001, start_time: '2020-01-01' }
    ];
    const charaStories = [
        { id: 1001001, chapter: '貪吃佩可 第1話', title: '大胃王', type: 'chara', charaName: '佩可' },
        { id: 1001002, chapter: '貪吃佩可 第2話', title: '王女的秘密', type: 'chara', charaName: '佩可' }
    ];

    map.stories = mainStories;
    map.eventStories = eventStories;
    map.events = events;
    map.chapters = {
        '第1章': [mainStories[0], mainStories[1]],
        '第15章': [mainStories[2], mainStories[3]],
        '【2020年1月】 初音的禮物': [eventStories[0], eventStories[1]],
        '佩可': [charaStories[0], charaStories[1]]
    };

    nav.init(map);

    return { win, doc, map, nav, storage, sessionStorage, mainStories, eventStories, charaStories };
}

async function runTests() {
    console.log('--- 開始執行 Story Map Render & Jump Lifecycle 回歸測試 ---');

    // ----------------------------------------------------
    // Test A — jump from landing menu
    // ----------------------------------------------------
    {
        const { map } = createLifecycleTestHarness();
        map._loadDataPromise = Promise.resolve();
        map.currentView = 'menu';
        assert.equal(map.currentView, 'menu', '初始 currentView 為 menu');

        const jumpPromise = map.jumpToStory(2015003);
        const result = await jumpPromise;

        assert.equal(result, undefined, 'jumpToStory 成功 resolve');
        assert.equal(map.currentView, 'list', 'jumpToStory 必須由自己保證切換至 list 視圖');
        assert.equal(map.activeStoryId, 2015003, 'activeStoryId 必須為目標故事');
        assert.equal(map.activeTabType, 'main', 'activeTabType 必須為 main');
        assert.equal(map.expandedChapter, '第15章', 'expandedChapter 必須為目標章節');
        console.log('✅ Test A Passed: jump from landing (canonical currentView ownership)');
    }

    // ----------------------------------------------------
    // Test B — jump waits for in-flight loadData
    // ----------------------------------------------------
    {
        const { map } = createLifecycleTestHarness();
        map.stories = []; // 資料尚未載入
        map.chapters = {};
        map.currentView = 'menu';

        let resolveLoad;
        map._loadDataInternal = () => new Promise(resolve => {
            resolveLoad = () => {
                map.stories = [
                    { id: 2001001, chapter: '第1章 第1話', title: '王都的相遇', type: 'main', part: 1 },
                    { id: 2015003, chapter: '第15章 第3話', title: '絕望的戰鬥', type: 'main', part: 1 }
                ];
                map.chapters = {
                    '第1章': [map.stories[0]],
                    '第15章': [map.stories[1]]
                };
                resolve();
            };
        });
        map._loadDataPromise = null;

        // 發動跳轉，此時 loadData 仍在進行中
        const jumpP = map.jumpToStory(2015003);

        // 在 loadData resolve 前，不應有錯誤的選話或 pendingJump 殘留
        assert.equal(map.activeStoryId, null, 'loadData 完成前 activeStoryId 仍為 null');
        assert.equal(map.pendingJumpStoryId, undefined, '不得再有 pendingJumpStoryId 屬性');

        // 完成載入
        resolveLoad();
        await jumpP;

        assert.equal(map.activeStoryId, 2015003, 'loadData 結束後目標 story 正常開啟');
        assert.equal(map.currentView, 'list', '視圖已切換為 list');
        console.log('✅ Test B Passed: jump waits for in-flight loadData');
    }

    // ----------------------------------------------------
    // Test C — loadData failure
    // ----------------------------------------------------
    {
        const { map } = createLifecycleTestHarness();
        map.currentView = 'menu';
        map.activeStoryId = null;
        map._loadDataInternal = () => Promise.reject(new Error('Network offline'));
        map._loadDataPromise = null;

        const result = await map.jumpToStory(2015003);

        assert.equal(result, false, 'loadData 失敗時 jumpToStory 必須優雅返回 false，不拋 unhandled rejection');
        assert.equal(map.currentView, 'menu', 'loadData 失敗時 currentView 必須維持原狀 menu');
        assert.equal(map.activeStoryId, null, 'activeStoryId 不得被修改');
        assert.equal(map.pendingJumpStoryId, undefined, '不得殘留 pending jump state');
        console.log('✅ Test C Passed: loadData failure (graceful error handling)');
    }

    // ----------------------------------------------------
    // Test D — safeRender 不 drop request (serialized queue)
    // ----------------------------------------------------
    {
        const { map } = createLifecycleTestHarness();
        const executionLog = [];
        let releaseBlocker;
        const blocker = new Promise(resolve => { releaseBlocker = resolve; });

        // Request A: 耗時非同步任務
        const pA = map.safeRender(async () => {
            executionLog.push('A-start');
            await blocker;
            executionLog.push('A-end');
            return 'A-result';
        });

        // 此時 A 正在執行中，立即發出 Request B
        assert.equal(map.isRendering, true, 'A 執行期間 isRendering 為 true');
        const pB = map.safeRender(async () => {
            executionLog.push('B-exec');
            return 'B-result';
        });

        // B 發出後，isRendering 依然為 true
        assert.equal(map.isRendering, true, 'B 排隊期間 isRendering 仍為 true');

        // 解除 A 的阻塞
        releaseBlocker();

        const [resA, resB] = await Promise.all([pA, pB]);

        assert.equal(resA, 'A-result', 'caller A 獲得自己的傳回值');
        assert.equal(resB, 'B-result', 'caller B 獲得自己的傳回值');
        assert.deepEqual(executionLog, ['A-start', 'A-end', 'B-exec'], '任務嚴格按順序串行執行，B 沒有被 drop');
        assert.equal(map.isRendering, false, '整條隊列排空後 isRendering 重設為 false');
        assert.equal(map._renderQueue, null, '整條隊列排空後 _renderQueue 恢復為 null/idle');
        console.log('✅ Test D Passed: safeRender does not drop request (serialized queue)');
    }

    // ----------------------------------------------------
    // Test E — previous failure does not poison queue
    // ----------------------------------------------------
    {
        const { map } = createLifecycleTestHarness();
        const executionLog = [];

        // 任務 A 會 throw
        const pA = map.safeRender(async () => {
            executionLog.push('A-fault');
            throw new Error('Render crash in A');
        });

        // 任務 B 正常排隊
        const pB = map.safeRender(async () => {
            executionLog.push('B-success');
            return 'B-done';
        });

        // caller A 必須收到自己的 rejection
        await assert.rejects(pA, /Render crash in A/, 'caller A 正確捕獲 rejection');

        // caller B 必須依然成功執行
        const resB = await pB;
        assert.equal(resB, 'B-done', 'A 失敗不得阻止 B 執行');
        assert.deepEqual(executionLog, ['A-fault', 'B-success']);
        assert.equal(map.isRendering, false, '隊列排空後 isRendering 為 false');
        assert.equal(map._renderQueue, null, '隊列 clean');
        console.log('✅ Test E Passed: previous failure does not poison queue');
    }

    // ----------------------------------------------------
    // Test F — rapid jump A → B
    // ----------------------------------------------------
    {
        const { map, eventStories } = createLifecycleTestHarness();
        map._loadDataPromise = Promise.resolve();

        // Story A: Main (2001001, 第1章)
        // Story B: Event (5001002, 初音的禮物)
        const pA = map.jumpToStory(2001001);
        const pB = map.jumpToStory(5001002);

        await Promise.allSettled([pA, pB]);

        // 最終狀態必須完全屬於 B，不得混雜 A 的狀態
        assert.equal(map.activeStoryId, 5001002, 'activeStoryId 最終必須為 B');
        assert.equal(map.activeTabType, 'event', 'activeTabType 最終必須為 B 所屬的 event');
        assert.equal(map.expandedChapter, '【2020年1月】 初音的禮物', 'expandedChapter 最終必須為 B 所屬的 初音的禮物');
        assert.equal(map.currentView, 'list', 'currentView 必須為 list');
        console.log('✅ Test F Passed: rapid jump A -> B (no mixed state)');
    }

    // ----------------------------------------------------
    // Test G — legacy removal verification
    // ----------------------------------------------------
    {
        assert.equal(mapSource.includes('pendingJumpStoryId'), false, 'map.js 不得再含有 pendingJumpStoryId');
        assert.equal(mapSource.includes('skipAutoSelect'), false, 'map.js 不得再含有 skipAutoSelect');
        assert.match(mapSource, /async _render\(\)\s*\{/, 'map.js 定義乾淨無參數的 _render()');
        assert.match(mapSource, /async render\(\)\s*\{\s*return this\.safeRender\(\(\) => this\._render\(\)\);/, 'render() 定義乾淨無參數');
        console.log('✅ Test G Passed: legacy removal verification (0 references)');
    }

    // ----------------------------------------------------
    // Test H — direct jump preserves previous reader position
    // ----------------------------------------------------
    {
        const { map, nav, storage, doc } = createLifecycleTestHarness();
        map._loadDataPromise = Promise.resolve();

        // 設置初始狀態為正在閱讀 Story A (2001001)
        const storyA = 2001001;
        const storyB = 2015003;
        map.activeStoryId = storyA;
        map.currentView = 'list';
        nav.readyStoryId = storyA;

        // 設置 dialogue-board 包含對白行，模擬目前位於 line 7
        const board = doc.getElementById('dialogue-board');
        board.children = [];
        const line7 = {
            tagName: 'DIV',
            dataset: { dialogueIndex: '7' },
            getBoundingClientRect: () => ({ top: 100, bottom: 200 })
        };
        board.children.push(line7);

        // 追蹤 localStorage 的寫入歷史
        const savedPositions = [];
        const originalSetItem = storage.setItem.bind(storage);
        storage.setItem = (k, v) => {
            if (k === 'pcrd_reader_position_v1') {
                savedPositions.push(JSON.parse(v));
            }
            originalSetItem(k, v);
        };

        // 執行 jumpToStory(storyB)
        await map.jumpToStory(storyB);

        // 驗證：在切換到 B 之前，Story A 的位置 line 7 曾被精確保存
        assert.ok(savedPositions.length >= 1, '在 jump 過程中必須至少執行過一次 position 保存');
        assert.equal(savedPositions[0].storyId, storyA, '保存的 storyId 必須為離開前的 storyA');
        assert.equal(savedPositions[0].line, 7, '保存的 line 必須為離開前的 line 7');

        // 最終 activeStoryId 必須為 storyB
        assert.equal(map.activeStoryId, storyB, '最終 activeStoryId 必須為目標故事 B');
        console.log('✅ Test H Passed: direct jump preserves previous reader position before DOM mutation');
    }

    console.log('\n🎉 ALL STORY MAP RENDER & JUMP LIFECYCLE TESTS PASSED!');
}

runTests().catch(err => {
    console.error('❌ Test failed with error:', err);
    process.exit(1);
});
