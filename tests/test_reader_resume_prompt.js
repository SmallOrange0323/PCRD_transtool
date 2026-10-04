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
            pushState(_, __, url) { window.location = new URL(url); }
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

    // 1. 有 resume 時 initial load 不會 auto redirect，但會顯示 non-blocking prompt，且立即記錄 seen flag
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

        console.log('✅ Test 1 Passed: 有 resume 時 initial load 不跳轉並正常顯示 prompt，且立即記錄 seen flag');
    }

    // 2. 無 resume 時不產生 prompt，且右上角 resume button disabled
    {
        const env = createTestEnvironment({
            initialUrl: 'https://example.test/reader'
        });

        env.nav.init(env.mockMap);

        const toast = env.document.getElementById('reader-resume-toast');
        assert.strictEqual(toast, null, 'No prompt should be rendered when there is no saved progress');

        const btn = env.document.getElementById('reader-resume');
        assert.strictEqual(btn.disabled, true, 'Toolbar resume button must be disabled when there is no saved progress');
        assert.strictEqual(btn.title, '尚無閱讀紀錄');

        console.log('✅ Test 2 Passed: 無 resume 時不產生 prompt 且按鈕正確 disabled');
    }

    // 3. 使用者透過 deep-link 進站時：不產生舊 resume prompt
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader#story=5001004&line=2'
        });

        env.nav.init(env.mockMap);

        const toast = env.document.getElementById('reader-resume-toast');
        assert.strictEqual(toast, null, 'Deep-link load must NOT show old resume prompt');
        assert.ok(env.mockMap.jumpToCalls.includes(5001004), 'Deep-link story must be opened directly');

        console.log('✅ Test 3 Passed: Deep-link 進站不顯示舊 resume prompt');
    }

    // 3b. Hash 存在但並非有效 story deep-link 時：不得抑制 resume prompt
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader#invalid_section'
        });

        env.nav.init(env.mockMap);

        // 斷言：沒有 auto redirect
        assert.strictEqual(env.mockMap.jumpToCalls.length, 0, 'Invalid hash must not redirect');
        // 斷言：非 story hash 不得壓掉 resume prompt
        const toast = env.document.getElementById('reader-resume-toast');
        assert.ok(toast, 'Invalid non-story hash must NOT suppress resume prompt');
        assert.ok(toast.textContent.includes('主線劇情 第15章・第3話'), 'Prompt should display for saved resume');

        console.log('✅ Test 3b Passed: 無效/非 story hash 不抑制 resume prompt');
    }

    // 4. 當前頁面本身即為 resume target 時：不顯示 prompt
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            activeStoryId: 2015003, // 目前已在該 story
            initialUrl: 'https://example.test/reader'
        });

        env.nav.init(env.mockMap);

        const toast = env.document.getElementById('reader-resume-toast');
        assert.strictEqual(toast, null, 'Must NOT show prompt if current story is already the resume target');

        console.log('✅ Test 4 Passed: 目前已在目標劇情時不顯示 prompt');
    }

    // 5. 使用者關閉 prompt 或同 session 重新載入：本 session 最多顯示一次 (Seen Flag)
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader'
        });

        env.nav.init(env.mockMap);

        let toast = env.document.getElementById('reader-resume-toast');
        assert.ok(toast, 'Toast should initially appear');

        // 點擊關閉按鈕
        const closeBtn = toast.children[0].children[0]; // header closeBtn
        closeBtn.click();

        toast = env.document.getElementById('reader-resume-toast');
        assert.strictEqual(toast, null, 'Toast must be removed after dismiss');
        assert.strictEqual(env.sessionStorage.getItem('pcrd_reader_prompt_seen_v1'), '1', 'Seen flag must be saved in sessionStorage');

        // 模擬同 session 下重新 init / reload
        const env2 = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            sessionStorageEntries: [['pcrd_reader_prompt_seen_v1', '1']],
            initialUrl: 'https://example.test/reader'
        });
        env2.nav.init(env2.mockMap);

        const toast2 = env2.document.getElementById('reader-resume-toast');
        assert.strictEqual(toast2, null, 'Must NOT show prompt again in the same seen session');

        console.log('✅ Test 5 Passed: prompt 顯示過後本 session 不再重複彈出 (Seen Flag)');
    }

    // 6. Prompt 的 [繼續閱讀] 與 Toolbar 的 [繼續閱讀] 共用同一 canonical resume action
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader'
        });

        env.nav.init(env.mockMap);

        const toast = env.document.getElementById('reader-resume-toast');
        const promptResumeBtn = toast.children[2].children[1]; // actions -> resumeBtn

        // 點擊 Prompt 的「繼續閱讀」
        promptResumeBtn.click();
        await new Promise(r => setTimeout(r, 10));

        assert.ok(env.mockMap.jumpToCalls.includes(2015003), 'Prompt resume click must open resume story');
        assert.strictEqual(env.document.getElementById('reader-resume-toast'), null, 'Toast must be dismissed on resume click');

        // 測試 Toolbar 按鈕點擊行為亦相同
        const envToolbar = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader'
        });
        envToolbar.nav.init(envToolbar.mockMap);

        const toolbarBtn = envToolbar.document.getElementById('reader-resume');
        assert.strictEqual(toolbarBtn.title, '上次閱讀：主線劇情 第15章・第3話', 'Toolbar title must match canonical label');

        toolbarBtn.click();
        await new Promise(r => setTimeout(r, 10));

        assert.ok(envToolbar.mockMap.jumpToCalls.includes(2015003), 'Toolbar resume click must open same resume story');

        console.log('✅ Test 6 Passed: Prompt 與 Toolbar 共用同一個 canonical resume action 與目標');
    }

    // 7. Resume label 共用 formatter 驗證：第1部、第2部、第3部、活動、角色、公會
    {
        const env = createTestEnvironment();
        const nav = env.nav;

        // 第1部（未明寫第1部 -> 不硬補第1部）
        assert.strictEqual(
            nav.formatResumeLabel({ id: 2015003, chapter: '第15章 第3話', title: '當希望被擊潰時', type: 'main' }),
            '主線劇情 第15章・第3話'
        );
        assert.strictEqual(
            nav.formatResumeLabel({ id: 2000001, chapter: '序章', title: '前篇', type: 'main' }),
            '主線劇情 序章・前篇'
        );

        // 第2部（保留部別）
        assert.strictEqual(
            nav.formatResumeLabel({ id: 2016001, chapter: '第2部 第1章 第1話', title: '新的起點', type: 'main' }),
            '主線劇情 第2部・第1章・第1話'
        );

        // 第3部（保留部別）
        assert.strictEqual(
            nav.formatResumeLabel({ id: 2025002, chapter: '第3部 第2章 第4話', title: '未知之門', type: 'main' }),
            '主線劇情 第3部・第2章・第4話'
        );

        // 活動
        assert.strictEqual(
            nav.formatResumeLabel({ id: 5001004, chapter: '初音的禮物大作戰 第4話', title: '被解放的魔物們', isEvent: true }),
            '活動：初音的禮物大作戰・第4話'
        );

        // 角色
        assert.strictEqual(
            nav.formatResumeLabel({ id: 1002006, chapter: '優衣 第6話', title: '想知道你真正的心意', type: 'chara' }),
            '優衣・角色劇情 第6話'
        );

        // 公會
        assert.strictEqual(
            nav.formatResumeLabel({ id: 3001001, chapter: '美食殿堂 第1話', title: '幸福的餐桌有你有我', type: 'guild' }),
            '公會：美食殿堂・第1話'
        );

        console.log('✅ Test 7 Passed: formatResumeLabel 保留主線第2部/第3部部別與各類劇情格式化契約驗證通過');
    }

    // 8. Invalid / corrupted resume record 容錯處理 (Fail gracefully)
    {
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', '{"storyId":9999999,"line":0}']], // 不存在於 DB 的 ID
            initialUrl: 'https://example.test/reader'
        });

        // 執行 init，不得拋出異常
        assert.doesNotThrow(() => env.nav.init(env.mockMap));

        // 斷言：不產生 prompt，按鈕 disabled
        assert.strictEqual(env.document.getElementById('reader-resume-toast'), null, 'Corrupted / missing story must NOT show toast');
        const btn = env.document.getElementById('reader-resume');
        assert.strictEqual(btn.disabled, true, 'Toolbar button must be disabled for invalid story target');

        console.log('✅ Test 8 Passed: 損壞或不存在的閱讀記錄安全容錯');
    }

    // 9. Tooltip 與最新閱讀進度同步：更新 target 後 updateResume 同步更新 title
    {
        const env = createTestEnvironment({
            initialUrl: 'https://example.test/reader'
        });

        env.nav.init(env.mockMap);
        const btn = env.document.getElementById('reader-resume');
        assert.strictEqual(btn.disabled, true);
        assert.strictEqual(btn.title, '尚無閱讀紀錄');

        // 模擬閱讀了第 2 部劇情並存入 localStorage
        env.localStorage.setItem('pcrd_reader_position_v1', JSON.stringify({ storyId: 2016001, line: 5 }));
        env.nav.selected(2016001);

        assert.strictEqual(btn.disabled, false);
        assert.strictEqual(btn.title, '上次閱讀：主線劇情 第2部・第1章・第1話', 'Toolbar title must dynamically sync with updated resume target');

        console.log('✅ Test 9 Passed: Toolbar Tooltip 即時與最新閱讀進度保持同步');
    }

    // 10. 舊 Auto-Resume 呼叫路徑保證：無 deep-link 時絕無自動呼叫 open(saved) 之路徑
    {
        const savedPos = JSON.stringify({ storyId: 2015003, line: 10 });
        const env = createTestEnvironment({
            localStorageEntries: [['pcrd_reader_position_v1', savedPos]],
            initialUrl: 'https://example.test/reader'
        });

        // 覆寫 open 方法以偵測是否有任何非預期的呼叫
        let openCallCount = 0;
        env.nav.open = () => { openCallCount++; };

        env.nav.init(env.mockMap);

        assert.strictEqual(openCallCount, 0, 'init() without deep-link must NEVER call open() automatically');

        console.log('✅ Test 10 Passed: 契約保證無任何 automatic open(saved position) 路徑');
    }

    console.log('\n🎉 ALL 10 READER RESUME PROMPT TESTS PASSED!');
}

runTests().catch(err => {
    console.error('Test execution failed:', err);
    process.exit(1);
});
