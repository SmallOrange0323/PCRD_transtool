'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../dashboard/reader-navigation.js'), 'utf8');

function createTestEnvironment(options = {}) {
    const localStorageData = new Map(options.localStorageEntries || []);
    const sessionStorageData = new Map(options.sessionStorageEntries || []);
    const elements = new Map();
    const createdElements = [];

    // 建立 DOM 模擬節點
    const mainEl = {
        prepend(el) { elements.set(el.id, el); }
    };
    const bodyEl = {
        appendChild(el) {
            elements.set(el.id, el);
            createdElements.push(el);
        }
    };
    const navRightEl = {
        innerHTML: ''
    };

    function makeMockElement(id, tag = 'div') {
        const listeners = new Map();
        let _text = '';
        const el = {
            id,
            tagName: tag.toUpperCase(),
            className: '',
            get textContent() {
                if (this.children.length === 0) return _text;
                return _text + this.children.map(c => c.textContent).join('');
            },
            set textContent(v) {
                _text = String(v);
                this.children = [];
            },
            disabled: false,
            title: '',
            attributes: {},
            children: [],
            setAttribute(k, v) { this.attributes[k] = v; },
            getAttribute(k) { return this.attributes[k]; },
            appendChild(child) { this.children.push(child); },
            addEventListener(evt, handler) {
                if (!listeners.has(evt)) listeners.set(evt, []);
                listeners.get(evt).push(handler);
            },
            click() {
                const handlers = listeners.get('click') || [];
                for (const h of handlers) h({ target: this });
            },
            focus() {},
            select() {},
            remove() {
                elements.delete(this.id);
                const idx = createdElements.indexOf(this);
                if (idx !== -1) createdElements.splice(idx, 1);
            }
        };
        return el;
    }

    const document = {
        getElementById(id) {
            if (id === 'reader-resume' || id === 'reader-share') {
                if (!elements.has(id)) elements.set(id, makeMockElement(id, 'button'));
            }
            return elements.get(id) || null;
        },
        querySelector(selector) {
            if (selector === '.nav-right') return navRightEl;
            if (selector === 'main') return mainEl;
            return null;
        },
        createElement(tag) {
            return makeMockElement(`elem-${Math.random().toString(36).slice(2, 7)}`, tag);
        },
        body: bodyEl,
        addEventListener() {},
        removeEventListener() {}
    };

    const window = {
        location: new URL(options.initialUrl || 'https://example.test/reader'),
        history: {
            state: null,
            pushState(state, __, url) {
                this.state = state;
                window.location = new URL(url);
            },
            replaceState(state, __, url) {
                this.state = state;
                window.location = new URL(url);
            }
        },
        navigator: {
            clipboard: {
                async writeText(text) { window._clipboardText = text; }
            }
        },
        addEventListener() {},
        removeEventListener() {}
    };

    const localStorage = {
        getItem(k) { return localStorageData.has(k) ? localStorageData.get(k) : null; },
        setItem(k, v) { localStorageData.set(k, String(v)); },
        removeItem(k) { localStorageData.delete(k); }
    };

    const sessionStorage = {
        getItem(k) { return sessionStorageData.has(k) ? sessionStorageData.get(k) : null; },
        setItem(k, v) { sessionStorageData.set(k, String(v)); },
        removeItem(k) { sessionStorageData.delete(k); }
    };

    const sandbox = {
        window,
        document,
        navigator: window.navigator,
        localStorage,
        sessionStorage,
        URL,
        URLSearchParams,
        setTimeout,
        clearTimeout,
        console
    };

    vm.runInNewContext(source, sandbox);
    const nav = window.ReaderNavigation;

    const mockStories = options.mockStories || [
        { id: 2015003, chapter: '第15章 第3話', title: '當希望被擊潰時', type: 'main' },
        { id: 2016001, chapter: '第2部 第1章 第1話', title: '新的起點', type: 'main' },
        { id: 2025002, chapter: '第3部 第2章 第4話', title: '未知之門', type: 'main' },
        { id: 5001004, chapter: '初音的禮物大作戰 第4話', title: '被解放的魔物們', isEvent: true },
        { id: 1002006, chapter: '優衣 第6話', title: '想知道你真正的心意', type: 'chara' },
        { id: 3001001, chapter: '美食殿堂 第1話', title: '幸福的餐桌有你有我', type: 'guild' }
    ];

    const mockMap = {
        activeStoryId: options.activeStoryId !== undefined ? options.activeStoryId : null,
        isRendering: false,
        _storyRenderToken: 1,
        getStoryById(id) {
            return mockStories.find(s => s.id === Number(id)) || null;
        },
        jumpToCalls: [],
        async jumpToStory(id) {
            this.jumpToCalls.push(id);
            this.activeStoryId = id;
        },
        exitReader() {}
    };

    return { nav, document, window, localStorage, sessionStorage, mockMap, elements };
}

async function runTests() {
    console.log('--- 開始執行 Reader Resume Prompt 回歸測試 ---');

    // Test A (既有 Test 1): URL 無 hash + saved progress -> open() = 0，顯示 resume prompt
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader'
        });

        env.nav.init(env.mockMap);

        // 斷言：沒有 auto redirect / jumpToStory
        assert.strictEqual(env.mockMap.jumpToCalls.length, 0, 'Initial load must NOT auto-redirect to resume story');
        assert.strictEqual(env.window.location.hash, '', 'Hash must remain empty on initial load without deep-link');

        // 斷言：產生了 prompt toast
        const toast = env.document.getElementById('reader-resume-toast');
        assert.ok(toast, 'Non-blocking resume prompt must be displayed when saved progress exists');
        assert.ok(toast.textContent.includes('主線劇情 第15章・第3話'), 'Prompt label must display canonical chapter and episode');

        // 斷言：Prompt 顯示後已立即寫入 pcrd_reader_prompt_seen_v1
        assert.strictEqual(env.sessionStorage.getItem('pcrd_reader_prompt_seen_v1'), '1', 'Prompt seen flag must be set immediately on display');

        console.log('✅ Test A Passed: URL 無 hash + saved progress 不跳轉並正常顯示 prompt');
    }

    // Test B (最關鍵 production bug regression): 初始 URL 為 #story=2015003 (無 line) + saved progress
    // -> open() = 0, 不 jumpToStory, stale hash 被清除, landing page 保持, 顯示 resume prompt
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader#story=2015003'
        });

        env.nav.init(env.mockMap);

        // 斷言：絕不 auto redirect / jumpToStory
        assert.strictEqual(env.mockMap.jumpToCalls.length, 0, 'Stale internal route #story=... must NOT trigger open()');
        // 斷言：stale hash 已透過 replaceState 清空，保持 landing page
        assert.strictEqual(env.window.location.hash, '', 'Stale internal hash must be cleared via replaceState');
        // 斷言：顯示 resume prompt
        const toast = env.document.getElementById('reader-resume-toast');
        assert.ok(toast, 'Resume prompt must appear for saved progress even when entering with stale #story hash');
        assert.ok(toast.textContent.includes('主線劇情 第15章・第3話'));

        console.log('✅ Test B Passed: 初始 URL #story=2015003 視為 stale route，清除 hash、不 auto open 並顯示 prompt');
    }

    // Test C: 初始 URL 為 #story=2015003 但沒有 saved progress
    // -> open() = 0, stale hash 被清除, 留在 landing page, 不顯示 resume prompt
    {
        const env = createTestEnvironment({
            initialUrl: 'https://example.test/reader#story=2015003'
        });

        env.nav.init(env.mockMap);

        assert.strictEqual(env.mockMap.jumpToCalls.length, 0, 'Stale hash without saved progress must NOT trigger open()');
        assert.strictEqual(env.window.location.hash, '', 'Stale hash must be cleared via replaceState');
        const toast = env.document.getElementById('reader-resume-toast');
        assert.strictEqual(toast, null, 'Must NOT show prompt if there is no saved progress');

        console.log('✅ Test C Passed: 初始 URL #story=2015003 無 saved progress 時清空 hash 且不顯示 prompt');
    }

    // Test D: 初始 URL 為 #story=2015003&line=0 -> explicit deep-link (line=0 必須合法成立)
    // -> 正常 open 2015003, 不顯示 resume prompt
    {
        const savedPos = JSON.stringify({ storyId: 2016001, line: 10 }); // 其他 saved進度
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader#story=2015003&line=0'
        });

        env.nav.init(env.mockMap);

        assert.ok(env.mockMap.jumpToCalls.includes(2015003), 'Explicit deep-link line=0 must open story directly');
        const toast = env.document.getElementById('reader-resume-toast');
        assert.strictEqual(toast, null, 'Explicit deep-link must suppress resume prompt');

        console.log('✅ Test D Passed: 初始 URL #story=2015003&line=0 判定為 explicit deep-link 並正常 open');
    }

    // Test E: 初始 URL 為 #story=2015003&line=42 -> explicit deep-link 保持指定 line 契約
    {
        const env = createTestEnvironment({
            initialUrl: 'https://example.test/reader#story=2015003&line=42'
        });

        env.nav.init(env.mockMap);

        assert.ok(env.mockMap.jumpToCalls.includes(2015003), 'Explicit deep-link line=42 must open story directly');
        assert.strictEqual(env.nav.restore?.line, 42, 'Pending restore line contract must be 42');

        console.log('✅ Test E Passed: 初始 URL #story=2015003&line=42 判定為 explicit deep-link 並保留 restore line');
    }

    // Test F: invalid hash -> 不 open, 有 resume 時仍顯示 prompt
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader#invalid_section'
        });

        env.nav.init(env.mockMap);

        assert.strictEqual(env.mockMap.jumpToCalls.length, 0, 'Invalid hash must not redirect');
        const toast = env.document.getElementById('reader-resume-toast');
        assert.ok(toast, 'Invalid non-story hash must NOT suppress resume prompt');
        assert.ok(toast.textContent.includes('主線劇情 第15章・第3話'));

        console.log('✅ Test F Passed: 無效 hash 不 open 且有 resume 時正常顯示 prompt');
    }

    // Test G: 確認 share() 產生的 URL 一定包含 story= 與 line=
    {
        const env = createTestEnvironment({
            initialUrl: 'https://example.test/reader'
        });
        env.nav.init(env.mockMap);
        env.mockMap.activeStoryId = 2015003;
        env.nav.readyStoryId = 2015003;

        await env.nav.share();

        const sharedUrl = env.window._clipboardText;
        assert.ok(sharedUrl, 'share() must write URL to clipboard');
        const urlObj = new URL(sharedUrl);
        const params = new URLSearchParams(urlObj.hash.slice(1));
        assert.strictEqual(params.get('story'), '2015003', 'Share URL must contain story parameter');
        assert.ok(params.has('line'), 'Share URL must explicitly contain line parameter');

        console.log('✅ Test G Passed: share() 產生的 URL 保證包含 story= 與 line=，符合 explicit deep-link 規範');
    }

    // Test 7 (實機情境完整模擬):
    // 1. 正常閱讀 story 2015003
    // 2. selected(2015003) 產生 #story=2015003
    // 3. 模擬下一次 page load / init 使用這個 URL，localStorage 同時有進度
    // 4. 驗證：不 open story, 不 jumpToStory, URL stale hash 被清掉, 保持 landing page, resume prompt 出現
    {
        // 步驟 1 & 2: 第一次 session 站內閱讀與 selected()
        const envSession1 = createTestEnvironment({
            initialUrl: 'https://example.test/reader'
        });
        envSession1.nav.init(envSession1.mockMap);
        envSession1.nav.selected(2015003);
        assert.strictEqual(envSession1.window.location.hash, '#story=2015003', 'selected() creates #story=2015003 in address bar');

        // 模擬閱讀進度寫入 localStorage
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });

        // 步驟 3: 第二次 session 載入 (例如使用者重新整理或瀏覽器還原分頁，帶有上次殘留的 #story=2015003)
        const envSession2 = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: envSession1.window.location.href // 'https://example.test/reader#story=2015003'
        });

        envSession2.nav.init(envSession2.mockMap);

        // 步驟 4: 驗證
        assert.strictEqual(envSession2.mockMap.jumpToCalls.length, 0, 'Reloading with #story=2015003 must NOT auto open story');
        assert.strictEqual(envSession2.window.location.hash, '', 'Stale #story=2015003 hash must be wiped from URL');
        const toast = envSession2.document.getElementById('reader-resume-toast');
        assert.ok(toast, 'Resume prompt MUST be displayed on reload');
        assert.ok(toast.textContent.includes('主線劇情 第15章・第3話'));

        console.log('✅ Test 7 (實機模擬) Passed: 站內閱讀產生 #story 殘留後重新整理，成功阻止 auto open 並清除 hash 顯示 prompt');
    }

    // 額外回歸驗證：關閉 prompt 後 seen flag、各類 label 格式化契約
    {
        const env = createTestEnvironment();
        const nav = env.nav;

        assert.strictEqual(
            nav.formatResumeLabel({ id: 2015003, chapter: '第15章 第3話', title: '當希望被擊潰時', type: 'main' }),
            '主線劇情 第15章・第3話'
        );
        assert.strictEqual(
            nav.formatResumeLabel({ id: 2016001, chapter: '第2部 第1章 第1話', title: '新的起點', type: 'main' }),
            '主線劇情 第2部・第1章・第1話'
        );
        assert.strictEqual(
            nav.formatResumeLabel({ id: 2025002, chapter: '第3部 第2章 第4話', title: '未知之門', type: 'main' }),
            '主線劇情 第3部・第2章・第4話'
        );
        console.log('✅ 額外格式化回歸驗證通過');
    }

    console.log('\n🎉 ALL READER RESUME PROMPT & STALE HASH REGRESSION TESTS PASSED!');
}

runTests().catch(err => {
    console.error('Test execution failed:', err);
    process.exit(1);
});
