/**
 * tests/test_speaker_view.js
 * 登場角色視圖 (SpeakerView) 專屬單元測試
 * 驗證：
 * 1. renderSpeakerCard 優先使用 avatarService.getAvatarHtml (NPC .png 與完整 6 級 fallback 鏈)
 * 2. renderSpeakerCard 在只有 getUrlCandidates 時優先選取 .png 且包含 this.onerror=null 防禦
 * 3. 未提供 avatarService 或無 unitId 時生成文字佔位符
 * 4. 點擊事件、計數、轉義與排序/過濾功能合約
 */

const assert = require('assert');
const path = require('path');

global.window = global;
require(path.join(__dirname, '../dashboard/speaker-view.js'));
const SpeakerView = window.SpeakerView;

assert(SpeakerView, 'SpeakerView 必須正確載入並暴露於全域');

console.log('開始執行 SpeakerView 測試案例...');

// 1. renderSpeakerCard with avatarService.getAvatarHtml
{
    const mockAvatarService = {
        getAvatarHtml(name, speakerAvatars) {
            return `<img src="icon/unit/193631.png" onerror="AvatarService.handleError(this, '${name}', 193631)">`;
        },
        getUnitId() { return 193631; }
    };

    const html = SpeakerView.renderSpeakerCard('八斗神局長', {
        appearanceMap: { '八斗神局長': [1, 2, 3] },
        speakerAvatars: { '八斗神局長': 193631 },
        avatarService: mockAvatarService,
        escapeHtml: (str) => str
    });

    assert(html.includes('icon/unit/193631.png'), '必須調用 avatarService.getAvatarHtml 產生之頭像');
    assert(html.includes('AvatarService.handleError'), '必須包含完整 fallback 處理器');
    assert(html.includes('🎬 登場 3 話'), '必須正確統計登場話數');
    assert(html.includes('八斗神局長'), '必須顯示角色名稱');
    console.log('  [PASS] 1. renderSpeakerCard with avatarService.getAvatarHtml');
}

// 2. renderSpeakerCard fallback to getUrlCandidates prefers .png and includes this.onerror=null
{
    const mockAvatarService = {
        getUnitId() { return 193631; },
        getUrlCandidates() {
            return [
                'icon/unit/193631.webp',
                'https://redive.estertion.win/icon/unit/193631.webp',
                'icon/unit/193631.png',
                'https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/icon/unit/193631.png'
            ];
        }
    };

    const html = SpeakerView.renderSpeakerCard('八斗神局長', {
        appearanceMap: { '八斗神局長': [1] },
        avatarService: mockAvatarService,
        escapeHtml: (str) => str
    });

    assert(html.includes('src="icon/unit/193631.png"'), '候選中必須優先選取 .png 格式');
    assert(html.includes('this.onerror=null'), 'onerror 必須包含 this.onerror=null 防止無限循環');
    console.log('  [PASS] 2. renderSpeakerCard prefers .png and has this.onerror=null');
}

// 3. renderSpeakerCard without avatarService -> text placeholder
{
    const html = SpeakerView.renderSpeakerCard('未知路人', {
        appearanceMap: { '未知路人': [1] },
        avatarService: null,
        escapeHtml: (str) => str
    });

    assert(html.includes('class="npc-avatar-placeholder"'), '無頭像服務必須生成文字佔位符');
    assert(html.includes('未知'), '文字佔位符必須顯示前兩個字');
    console.log('  [PASS] 3. renderSpeakerCard fallback to text placeholder');
}

// 4. filterSpeakers and sortSpeakers contracts
{
    const all = ['佩可', '可可蘿', '凱留'];
    const filtered = SpeakerView.filterSpeakers(all, '可');
    assert.deepStrictEqual(filtered, ['佩可', '可可蘿']);

    const appearances = {
        '佩可': [1, 2],
        '可可蘿': [1, 2, 3, 4],
        '凱留': [1]
    };

    const desc = SpeakerView.sortSpeakers(['佩可', '可可蘿', '凱留'], appearances, 'appearances-desc');
    assert.deepStrictEqual(desc, ['可可蘿', '佩可', '凱留'], '話數多到少排序正確');

    const asc = SpeakerView.sortSpeakers(['佩可', '可可蘿', '凱留'], appearances, 'appearances-asc');
    assert.deepStrictEqual(asc, ['凱留', '佩可', '可可蘿'], '話數少到多排序正確');
    console.log('  [PASS] 4. filterSpeakers and sortSpeakers');
}

const sampleNpcCatalog = {
    version: 1,
    metadata: { total_npcs: 4, female_count: 2, main_count: 3, event_count: 3, special_count: 1 },
    npcs: [
        {
            name: '秘書',
            unit_id: 6111,
            gender: 'female',
            appearance_count: 72,
            main_count: 20,
            event_count: 48,
            other_count: 4,
            story_scopes: ['main', 'event', 'other'],
            is_special: true,
            special_label: '秘書子',
            aliases: ['秘書子'],
            variants: [
                { unit_id: 6111, label: '常服' },
                { unit_id: 6112, label: '泳裝' }
            ]
        },
        {
            name: '尾狗刀',
            unit_id: 106211,
            gender: 'male',
            appearance_count: 72,
            main_count: 70,
            event_count: 0,
            other_count: 2,
            story_scopes: ['main', 'other'],
            is_special: false,
            special_label: null,
            aliases: ['詠斗', '過去的詠斗'],
            variants: []
        },
        {
            name: '鬼魂教父',
            unit_id: 14011,
            gender: 'male',
            appearance_count: 15,
            main_count: 0,
            event_count: 15,
            other_count: 0,
            story_scopes: ['event'],
            is_special: false,
            special_label: null,
            aliases: [],
            variants: []
        },
        {
            name: '女性教員',
            unit_id: 3211,
            gender: 'female',
            appearance_count: 12,
            main_count: 3,
            event_count: 9,
            other_count: 0,
            story_scopes: ['main', 'event'],
            is_special: false,
            special_label: null,
            aliases: [],
            variants: []
        }
    ]
};

// 5. 子頁籤切換與既有 'all' 視圖向後相容
{
    const pageAll = SpeakerView.renderSpeakerPageHtml({
        appearanceMap: { '貪吃佩可': [1, 2], '可可蘿': [1] },
        speakerAvatars: { '貪吃佩可': 105811 },
        npcCatalog: sampleNpcCatalog,
        escapeHtml: (s) => s
    });
    assert(pageAll.includes('data-subtab="all"'), '應渲染全部登場角色子頁籤');
    assert(pageAll.includes('🖼️ NPC 頭像圖鑑 (4)'), '應渲染附帶數量的 NPC 頭像圖鑑子頁籤');
    assert(pageAll.includes('class="speaker-grid"'), '預設 all 模式必須保留原有 .speaker-grid');
    assert(!pageAll.includes('id="speaker-npc-container"'), '預設 all 模式不應渲染 NPC 圖鑑容器');

    const pageNpc = SpeakerView.renderSpeakerPageHtml({
        speakerSubTab: 'npc',
        npcCatalog: sampleNpcCatalog,
        escapeHtml: (s) => s
    });
    assert(pageNpc.includes('id="speaker-npc-container"'), 'npc 模式必須渲染 #speaker-npc-container');
    assert(pageNpc.includes('data-npc-scope="main"'), 'npc 模式必須包含主線登場篩選鈕');
    assert(pageNpc.includes('data-npc-scope="event"'), 'npc 模式必須包含活動登場篩選鈕');
    assert(pageNpc.includes('id="speaker-npc-female-btn"'), 'npc 模式必須包含只看女角切換鈕');
    console.log('  [PASS] 5. speaker sub-tab switching and backward compatibility');
}

// 6. 秘書不獨立切出特殊區塊，與所有具名 NPC 一致於一般網格渲染
{
    const npcHtml = SpeakerView.renderNpcCatalogContentHtml({
        npcCatalog: sampleNpcCatalog,
        escapeHtml: (s) => s
    });
    assert(!npcHtml.includes('npc-special-section'), '不得再單獨渲染獨立特殊 NPC 橫幅區塊');
    assert(!npcHtml.includes('⭐ 特殊立繪 NPC'), '不得出現特殊立繪 NPC 獨立標題');

    const gridSection = npcHtml.split('class="npc-catalog-grid"')[1] || '';
    assert(gridSection.includes('icon/unit/006111.png') && gridSection.includes('QuestMapModule.showCharaModal(&quot;秘書&quot;, 6111)'), '秘書須於一般 NPC 網格內渲染並使用 006111.png');
    assert(gridSection.includes('icon/unit/014011.png') && gridSection.includes('showCharaModal(&quot;鬼魂教父&quot;, 14011)'), '一般 NPC 網格須正確渲染鬼魂教父');
    assert(gridSection.includes('icon/unit/003211.png') && gridSection.includes('showCharaModal(&quot;女性教員&quot;, 3211)'), '一般 NPC 網格須正確渲染女性教員');
    console.log('  [PASS] 6. 秘書 unified inside regular NPC catalog grid without standalone section');
}

// 7. 主線 / 活動 / 女角 / 別名與簡繁關鍵字組合篩選
{
    const mainFemales = SpeakerView.filterNpcCatalog(sampleNpcCatalog.npcs, {
        npcScopeFilter: 'main',
        npcFemaleOnly: true
    });
    assert.deepStrictEqual(mainFemales.map(n => n.name), ['秘書', '女性教員'], '主線＋女角篩選須僅保留秘書與女性教員');

    const eventOnly = SpeakerView.filterNpcCatalog(sampleNpcCatalog.npcs, {
        npcScopeFilter: 'event'
    });
    assert.deepStrictEqual(eventOnly.map(n => n.name), ['秘書', '鬼魂教父', '女性教員'], '活動登場篩選須排除無活動話數之尾狗刀');

    const eventSorted = SpeakerView.sortNpcCatalog(eventOnly, 'appearances-desc', 'event');
    assert.deepStrictEqual(eventSorted.map(n => n.name), ['秘書', '鬼魂教父', '女性教員'], '活動模式應依 event_count 排序');

    const byAlias = SpeakerView.filterNpcCatalog(sampleNpcCatalog.npcs, { searchQuery: '詠斗' });
    assert.deepStrictEqual(byAlias.map(n => n.name), ['尾狗刀'], '搜尋 aliases 別名 詠斗 須命中尾狗刀');

    const bySimplifiedSpecial = SpeakerView.filterNpcCatalog(sampleNpcCatalog.npcs, { searchQuery: '秘书子' });
    assert.deepStrictEqual(bySimplifiedSpecial.map(n => n.name), ['秘書'], '輸入簡體 秘书子 須命中 秘書（秘書子）');

    const mainHtml = SpeakerView.renderNpcCatalogContentHtml({
        npcCatalog: sampleNpcCatalog,
        npcScopeFilter: 'main',
        npcFemaleOnly: true,
        escapeHtml: (s) => s
    });
    assert(mainHtml.includes('🎬 主線 3 話'), '主線篩選下卡片話數標記應顯示主線話數');
    console.log('  [PASS] 7. scope/female/search/alias/simplified combination filtering and sorting');
}

// 8. 無結果空狀態提示與 QuestMapModule NPC 圖鑑整合（含保護實體與焦點不重繪）
(async () => {
    const emptyHtml = SpeakerView.renderNpcCatalogContentHtml({
        npcCatalog: sampleNpcCatalog,
        searchQuery: '不存在的角色名稱xyz',
        escapeHtml: (s) => s
    });
    assert(emptyHtml.includes('查無符合條件的 NPC 角色'), '查無結果時須顯示友善空狀態提示');

    const fs = require('fs');
    const vm = require('vm');
    const mapCode = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');

    const npcContainer = { innerHTML: '' };
    const tabEl = { innerHTML: '' };
    const scopeBtns = [
        { getAttribute: () => 'all', classList: { toggle(cls, val) { this._active = val; } } },
        { getAttribute: () => 'main', classList: { toggle(cls, val) { this._active = val; } } },
        { getAttribute: () => 'event', classList: { toggle(cls, val) { this._active = val; } } }
    ];
    const femaleBtn = { classList: { toggle(cls, val) { this._active = val; } } };

    const catalogWithProtectedConflict = {
        version: 1,
        metadata: { total_npcs: 3 },
        npcs: [
            ...sampleNpcCatalog.npcs,
            { name: '格蕾斯', unit_id: 999999, gender: 'female', appearance_count: 1, main_count: 1, event_count: 0, other_count: 0, story_scopes: ['main'], is_special: false, special_label: null, aliases: [], variants: [] },
            { name: '可可蘿', unit_id: 999998, gender: 'female', appearance_count: 1, main_count: 1, event_count: 0, other_count: 0, story_scopes: ['main'], is_special: false, special_label: null, aliases: [], variants: [] }
        ]
    };

    const sandbox = {
        window: {},
        document: {
            addEventListener() {},
            getElementById(id) {
                if (id === 'speaker-npc-container') return npcContainer;
                if (id === 'map-tab') return tabEl;
                if (id === 'speaker-npc-female-btn') return femaleBtn;
                return null;
            },
            querySelector() { return null; },
            querySelectorAll(sel) { return sel === '[data-npc-scope]' ? scopeBtns : []; }
        },
        console: { log() {}, warn() {}, error() {} },
        fetch: async (url) => {
            if (url.includes('npc_catalog.json')) {
                return { ok: true, json: async () => catalogWithProtectedConflict };
            }
            return { ok: false, status: 404 };
        },
        setTimeout,
        clearTimeout
    };
    sandbox.window = sandbox;
    sandbox.window.SpeakerView = SpeakerView;
    sandbox.window.AvatarService = {
        manifestLoaded: false,
        manifestUnavailable: false,
        getAvatarHtml: () => '',
        getUnitId: () => null
    };

    vm.runInNewContext(mapCode, sandbox);
    const QMM = sandbox.QuestMapModule;
    QMM.speakerIdentityRules = { entities: { '可可蘿': { canonical_game_name: '可可蘿', base_ids: [1059] } } };
    QMM.speakerAvatars = { '可可蘿': 105911, '格蕾斯': 134111, '鬼魂教父': 1411 };

    const loaded = await QMM.ensureNpcCatalog();
    assert(loaded && loaded.npcs.length === 6, 'ensureNpcCatalog 應成功載入並快取');
    assert.strictEqual(QMM.speakerAvatars['鬼魂教父'], 14011, '鬼魂教父應安全更新為專屬頭像 14011');
    assert.strictEqual(QMM.speakerAvatars['秘書'], 6111, '秘書應寫入專屬頭像 6111');
    assert.strictEqual(QMM.speakerAvatars['女性教員'], 3211, '女性教員應寫入頭像 3211');
    assert.strictEqual(QMM.speakerAvatars['可可蘿'], 105911, '不得覆蓋 entities 可操作角色可可蘿');
    assert.strictEqual(QMM.speakerAvatars['格蕾斯'], 134111, '不得覆蓋保護名單格蕾斯');

    // 切換到 npc 子頁籤並操作局部更新
    QMM.handleSpeakerSubTab('npc');
    assert(tabEl.innerHTML.includes('id="speaker-npc-container"'), 'handleSpeakerSubTab("npc") 應渲染 NPC 分頁');
    const previousTabHtml = tabEl.innerHTML;

    QMM.handleNpcScopeFilter('event');
    assert.strictEqual(tabEl.innerHTML, previousTabHtml, 'handleNpcScopeFilter 不得整頁重建（保留搜尋框焦點）');
    assert.strictEqual(scopeBtns[2].classList._active, true, 'event 篩選鈕應啟用 active');
    assert(!npcContainer.innerHTML.includes('尾狗刀'), 'event 篩選應僅更新 #speaker-npc-container 並排除尾狗刀');

    QMM.handleNpcFemaleToggle();
    assert.strictEqual(femaleBtn.classList._active, true, '只看女角鈕應啟用 active');
    assert(!npcContainer.innerHTML.includes('鬼魂教父'), '女角篩選應排除鬼魂教父');

    QMM.handleSpeakerSearch('秘书子');
    await new Promise(resolve => setTimeout(resolve, 350));
    assert.strictEqual(tabEl.innerHTML, previousTabHtml, 'handleSpeakerSearch 不得整頁重建（保留搜尋框焦點）');
    assert(npcContainer.innerHTML.includes('showCharaModal(&quot;秘書&quot;, 6111)'), 'debounce 後應僅更新 #speaker-npc-container 並顯示秘書卡片');
    assert(!npcContainer.innerHTML.includes('女性教員'), '搜尋 秘书子 後應過濾掉女性教員');

    // fetch 失敗時 ensureNpcCatalog 安全降級回傳 null
    sandbox.fetch = async () => { throw new Error('Network error'); };
    QMM.npcCatalog = null;
    QMM._npcCatalogPromise = null;
    const failedLoad = await QMM.ensureNpcCatalog();
    assert.strictEqual(failedLoad, null, 'fetch 失敗時應安全降級回傳 null');

    console.log('  [PASS] 8. empty state and QuestMapModule NPC catalog integration');

    // 9. < 100000 exact active NPC portrait renders <img> in renderSpeakerCard instead of placeholder
    {
        const mockAvatarSvc = {
            getUnitId(name, ext) { return (ext && ext[name]) || null; },
            resolveExactDialoguePortrait(uid) {
                if (Number(uid) === 51611) {
                    return { status: 'active', unitId: 51611, filename: '051611.png', path: 'icon/unit/051611.png' };
                }
                return { status: 'unknown_placeholder', unitId: Number(uid), filename: null };
            },
            getAvatarHtmlByUnitId(uid, name) {
                return `<img src="icon/unit/${String(uid).padStart(6, '0')}.png" data-exact-npc="${uid}">`;
            },
            getAvatarHtml(name, ext) {
                const uid = this.getUnitId(name, ext);
                if (!uid || uid < 100000) return `<div class="npc-avatar-placeholder">${name.slice(0, 2)}</div>`;
                return `<img src="icon/unit/${uid}.png" data-standard="${uid}">`;
            }
        };

        const npcCardHtml = SpeakerView.renderSpeakerCard('米亞', {
            appearanceMap: { '米亞': [1, 2, 3] },
            speakerAvatars: { '米亞': 51611 },
            avatarService: mockAvatarSvc,
            escapeHtml: (s) => s
        });
        assert(npcCardHtml.includes('icon/unit/051611.png'), 'unit_id < 100000 的 active NPC 應改走精確對白路徑渲染圖片');
        assert(!npcCardHtml.includes('npc-avatar-placeholder'), '有實圖的 NPC 不得退化成文字佔位符');
        assert(npcCardHtml.includes('QuestMapModule.showCharaModal(&quot;米亞&quot;, 51611)'), '點擊 NPC 卡片須帶入精確 unit_id 以在 Modal 顯示頭像');

        const playableCardHtml = SpeakerView.renderSpeakerCard('佩可', {
            appearanceMap: { '佩可': [1, 2, 3, 4] },
            speakerAvatars: { '佩可': 105811 },
            avatarService: mockAvatarSvc,
            escapeHtml: (s) => s
        });
        assert(playableCardHtml.includes('data-standard="105811"'), 'unit_id >= 100000 的既有角色應維持原 getAvatarHtml 路徑');
        console.log('  [PASS] 9. renderSpeakerCard resolves < 100000 active exact NPC portrait');
    }

    // 10. hideGenericNpc filter default + toggle + backward compatibility
    {
        const sampleRules = {
            entities: { '貪吃佩可': { canonical_game_name: '貪吃佩可' } },
            speaker_rules: {
                '飢餓的公主': [{ target_type: 'entity', target_entity: '貪吃佩可', allow_null_unit_id: true }]
            }
        };
        const appearanceMap = {
            '貪吃佩可': [1, 2, 3],
            '飢餓的公主': [4],
            '女性教員': [5, 6],
            '王宮騎士': [7, 8],
            '旁白': [9]
        };

        // 未傳 filterOptions 維持原行為（保留王宮騎士）
        const legacyFiltered = SpeakerView.filterSpeakers(Object.keys(appearanceMap), '');
        assert(legacyFiltered.includes('王宮騎士'), '未傳 hideGenericNpc 時必須向後相容保留泛用 NPC');

        // 啟用 hideGenericNpc: true 時僅保留 entities / entity rules / npcCatalog 名單
        const filteredNamed = SpeakerView.filterSpeakers(Object.keys(appearanceMap), '', {
            hideGenericNpc: true,
            npcCatalog: sampleNpcCatalog,
            speakerIdentityRules: sampleRules
        });
        assert.deepStrictEqual(filteredNamed, ['貪吃佩可', '飢餓的公主', '女性教員'], 'hideGenericNpc 應只留下主要與具名角色');

        const allPageHtmlHidden = SpeakerView.renderSpeakerPageHtml({
            appearanceMap,
            speakerAvatars: {},
            speakerSubTab: 'all',
            hideGenericNpc: true,
            npcCatalog: sampleNpcCatalog,
            speakerIdentityRules: sampleRules,
            escapeHtml: (s) => s
        });
        assert(allPageHtmlHidden.includes('id="speaker-hide-generic-btn"'), '全部登場角色頁應渲染隱藏泛用 NPC 切換按鈕');
        assert(allPageHtmlHidden.includes('顯示 3 位主要與具名角色（已隱藏 1 項泛用／未登錄 NPC）'), '應正確顯示統計摘要');
        assert(!allPageHtmlHidden.includes('王宮騎士'), '預設隱藏泛用 NPC 時不得出現王宮騎士');

        // 驗證 QuestMapModule.handleHideGenericNpcToggle 局部更新 DOM 而不重建整頁
        const hideBtnEl = { classList: { _active: true, toggle(cls, f) { this._active = Boolean(f); } }, textContent: '' };
        const summaryEl = { textContent: '' };
        const gridEl = { innerHTML: '' };
        const fullTabEl = { innerHTML: allPageHtmlHidden };
        sandbox.document.getElementById = (id) => {
            if (id === 'speaker-hide-generic-btn') return hideBtnEl;
            if (id === 'speaker-generic-summary') return summaryEl;
            if (id === 'map-tab') return fullTabEl;
            return null;
        };
        sandbox.document.querySelector = (sel) => (sel === '.speaker-grid' ? gridEl : null);

        QMM.appearanceMap = appearanceMap;
        QMM.npcCatalog = sampleNpcCatalog;
        QMM.speakerIdentityRules = sampleRules;
        QMM.speakerSubTab = 'all';
        QMM.speakerSearchQuery = '';
        QMM.hideGenericNpc = true;

        QMM.handleHideGenericNpcToggle();
        assert.strictEqual(QMM.hideGenericNpc, false, '點擊切換應將 hideGenericNpc 改為 false');
        assert.strictEqual(hideBtnEl.classList._active, false, '按鈕 active 狀態應同步關閉');
        assert(gridEl.innerHTML.includes('王宮騎士'), '切換為顯示全部後 grid 應立即包含王宮騎士');
        assert(summaryEl.textContent.includes('顯示全部 4 項角色'), '摘要文字應同步更新');
        assert.strictEqual(fullTabEl.innerHTML, allPageHtmlHidden, '局部更新不得重建整個 map-tab（保留搜尋框焦點）');
        console.log('  [PASS] 10. hideGenericNpc filtering, summary stats and QuestMapModule toggle');
    }

    console.log('\n✅ All SpeakerView tests passed successfully!');
})().catch(err => {
    console.error(err);
    process.exit(1);
});
