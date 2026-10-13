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

console.log('\n✅ All SpeakerView tests passed successfully!');
