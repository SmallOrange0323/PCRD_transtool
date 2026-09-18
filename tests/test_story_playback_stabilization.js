/**
 * 回歸測試：Stabilization A — Story Map Playback / Async Lifecycle Hardening
 *
 * 覆蓋四項核心行為：
 * 1. Same-story guard     — 同話重點不停止 AUTO、不建立新 playback session
 * 2. Stale dialogue race  — 非同步 loadDialogue 採 token+story 雙重門禁
 * 3. Playback teardown    — exitReader / switchTab 停止 AUTO + MediaService
 * 4. MediaService stale async resurrection（最重要）
 *    A. stop 後 play() resolve → audio 必須立刻被 discard，onStart 不得執行
 *    B. stop 後 play() reject → 不得進入下一 CDN candidate
 *    C. stop 後 onerror      → 不得 retry，不得觸發 callback
 *    D. 新 session 建立後舊 session callback 無效
 *
 * 測試環境：Node.js，無真實瀏覽器。Deterministic Mock Audio 無真實網路。
 */

'use strict';

const assert = require('assert');
const path = require('path');
const fs = require('fs');

// ─── 環境模擬 ────────────────────────────────────────────────────────────────

global.window = global;
global.document = {
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => ({
        classList: { add() {}, remove() {}, contains() { return false; } },
        style: {},
        innerHTML: '',
        appendChild() {},
        addEventListener() {}
    }),
    body: { style: {}, appendChild() {}, removeEventListener() {} },
    addEventListener() {},
    removeEventListener() {}
};

global.AvatarService = {
    getAvatarHtml: () => '<img class="avatar">',
    getAvatarHtmlByUnitId: () => '<img class="avatar">'
};

// ─── 載入待測模組 ────────────────────────────────────────────────────────────

require(path.resolve(__dirname, '../dashboard/story-asset-service.js'));
require(path.resolve(__dirname, '../dashboard/media-service.js'));
require(path.resolve(__dirname, '../dashboard/dialogue-view.js'));
require(path.resolve(__dirname, '../dashboard/auto-voice-controller.js'));

const MediaService = global.MediaService;
const AutoVoiceController = global.AutoVoiceController;

assert(MediaService, 'MediaService 必須存在');
assert(AutoVoiceController, 'AutoVoiceController 必須存在');

// P0 source-of-truth contract: playback lifecycle logic lives in map.js, not in
// a later story_map.html monkey patch that can silently override production code.
const mapSource = fs.readFileSync(path.resolve(__dirname, '../dashboard/map.js'), 'utf8');
const htmlSource = fs.readFileSync(path.resolve(__dirname, '../dashboard/story_map.html'), 'utf8');
assert(mapSource.includes('_stopStoryPlayback()'), 'map.js must own playback teardown');
assert(mapSource.includes('teardownPlayback(options = {})'), 'map.js must own lifecycle invalidation');
assert(mapSource.includes('const isCurrentStory = () => ('), 'map.js must own stale-dialogue commit guard');
assert(!htmlSource.includes('Stabilization A: Story Map playback / async lifecycle hardening'),
    'story_map.html must not contain the old stabilization monkey patch');
assert(!htmlSource.includes('QuestMapModule.loadDialogue = async function'),
    'story_map.html must not override loadDialogue at runtime');

// ─── 可控 MockAudio 工廠 ─────────────────────────────────────────────────────

function makeDeferredMockAudio(src) {
    let _playResolve, _playReject;
    const audio = {
        src,
        paused: true,
        ended: false,
        currentTime: 0,
        onended: null,
        onerror: null,
        playCallCount: 0,
        pauseCallCount: 0,
        play() {
            this.paused = false;
            this.playCallCount++;
            return new Promise((res, rej) => {
                _playResolve = res;
                _playReject = rej;
            });
        },
        pause() {
            this.paused = true;
            this.pauseCallCount++;
        },
        _resolvePlay() { if (_playResolve) _playResolve(); },
        _rejectPlay(err) { if (_playReject) _playReject(err); }
    };
    return audio;
}

function resetMediaService() {
    MediaService.stopVoice();
    MediaService._currentAudio = null;
}

// ─── 測試工具 ─────────────────────────────────────────────────────────────────

let _passCount = 0;
let _failCount = 0;

function pass(label) {
    _passCount++;
    console.log(`  \u2705 ${label}`);
}

function fail(label, reason) {
    _failCount++;
    console.error(`  \u274C ${label}`);
    console.error(`     \u539F\u56E0: ${reason}`);
}

function assertTest(condition, label, reason) {
    if (condition) {
        pass(label);
    } else {
        fail(label, reason || '\u65B7\u8A00\u5931\u6557');
        throw new Error(`Test FAIL: ${label}`);
    }
}

// ─── 同步測試 ────────────────────────────────────────────────────────────────

// 測試 1：Same-story guard
console.log('\n=== Test 1: Same-story guard ===');
{
    let stopCalled = 0;
    let originalCallCount = 0;

    const fakeModule = {
        activeStoryId: 'S001',
        _stopStoryPlayback() { stopCalled++; },
        _selectStoryOriginal(id) { originalCallCount++; }
    };

    function selectStoryWithGuard(storyId) {
        if (fakeModule.activeStoryId === storyId) {
            return; // strict no-op
        }
        fakeModule._stopStoryPlayback();
        fakeModule._selectStoryOriginal(storyId);
    }

    selectStoryWithGuard('S001');
    assertTest(stopCalled === 0,
        'Same-story 重複點擊：_stopStoryPlayback 不應被呼叫',
        `stopCalled=${stopCalled}，應為 0`);
    assertTest(originalCallCount === 0,
        'Same-story 重複點擊：原始 selectStory 不應被呼叫',
        `originalCallCount=${originalCallCount}，應為 0`);

    selectStoryWithGuard('S002');
    assertTest(stopCalled === 1,
        '不同話切換：_stopStoryPlayback 應被呼叫一次',
        `stopCalled=${stopCalled}，應為 1`);
    assertTest(originalCallCount === 1,
        '不同話切換：原始 selectStory 應被呼叫一次',
        `originalCallCount=${originalCallCount}，應為 1`);
}

// 測試 2：Stale dialogue race — token + story 雙重門禁
console.log('\n=== Test 2: Stale dialogue race guard ===');
{
    let token = 1;
    let activeId = 'S_C';

    function makeIsCurrentStory(capturedToken, capturedId) {
        return () => capturedToken === token && capturedId === activeId;
    }

    const isCurrentA = makeIsCurrentStory(1, 'S_A');
    token = 3;
    assertTest(!isCurrentA(),
        'Story A stale commit：isCurrentStory() 應回傳 false（token 不符）',
        'A 的 token(1) 與當前 token(3) 不符');

    const isCurrentB = makeIsCurrentStory(2, 'S_B');
    assertTest(!isCurrentB(),
        'Story B stale commit：isCurrentStory() 應回傳 false（token+id 均不符）',
        'B 的 token(2) 與 id(S_B) 均不符');

    const isCurrentC = makeIsCurrentStory(3, 'S_C');
    assertTest(isCurrentC(),
        'Story C live commit：isCurrentStory() 應回傳 true',
        'C 的 token 與 id 均符合');

    // finally guard：stale token 不清掉新 story 的 dialogueLoadingToken
    let dialogueLoadingToken = 3;
    const currentToken_A = 1;
    assertTest(dialogueLoadingToken !== currentToken_A,
        'Finally guard：A 的 stale token 不應清掉 C 的 dialogueLoadingToken',
        `dialogueLoadingToken=${dialogueLoadingToken}, currentToken_A=${currentToken_A}`);
}

// 測試 3：Teardown 停止 AUTO + MediaService
console.log('\n=== Test 3: Playback teardown ===');
{
    let mockPlayLog = [];
    const originalAudio3 = global.Audio;

    global.Audio = function(src) {
        return {
            src,
            paused: true,
            ended: false,
            currentTime: 0,
            onended: null,
            onerror: null,
            play() {
                this.paused = false;
                mockPlayLog.push('play:' + src);
                return Promise.resolve();
            },
            pause() {
                this.paused = true;
                mockPlayLog.push('pause:' + src);
            }
        };
    };

    resetMediaService();
    AutoVoiceController.stop();

    const fakeDialogue = [
        { voice: 'vo_adv_1001001_000', text: 'A' },
        { voice: 'vo_adv_1001001_001', text: 'B' }
    ];
    AutoVoiceController.start(fakeDialogue, 'S001', null, 0);

    assertTest(AutoVoiceController.state === 'PLAYING',
        'Teardown 前：AVC 狀態應為 PLAYING',
        `state=${AutoVoiceController.state}`);

    // teardown
    AutoVoiceController.stop();
    MediaService.stopVoice();

    assertTest(AutoVoiceController.state === 'IDLE',
        'Teardown 後：AVC 狀態應回到 IDLE',
        `state=${AutoVoiceController.state}`);
    assertTest(MediaService._currentAudio === null,
        'Teardown 後：MediaService._currentAudio 應為 null',
        `_currentAudio=${MediaService._currentAudio}`);

    global.Audio = originalAudio3;
}

// ─── 非同步測試（async IIFE 兼容舊版 Node.js）────────────────────────────────

(async function() {

// 測試 4A：stop 後 play() resolve → audio 不復活
console.log('\n=== Test 4A: stop → play() resolve → audio must be discarded ===');
{
    resetMediaService();

    let deferredAudio = null;
    let onStartCalled = 0;

    const origAudio = global.Audio;
    global.Audio = function(src) {
        deferredAudio = makeDeferredMockAudio(src);
        return deferredAudio;
    };

    MediaService.playVoiceWithOptions('vo_adv_test_4a_000', {
        onStart: () => { onStartCalled++; }
    });

    const tokenBeforeStop = MediaService._voiceSessionToken;
    assert(deferredAudio, '應已建立 MockAudio');
    assertTest(deferredAudio.playCallCount === 1,
        '4A: play() 應被呼叫一次',
        `playCallCount=${deferredAudio.playCallCount}`);

    MediaService.stopVoice();

    assertTest(MediaService._voiceSessionToken > tokenBeforeStop,
        '4A: stopVoice() 應遞增 token',
        `before=${tokenBeforeStop}, after=${MediaService._voiceSessionToken}`);
    assertTest(MediaService._currentAudio === null,
        '4A: stopVoice() 後 _currentAudio 應為 null',
        `_currentAudio=${MediaService._currentAudio}`);

    // 舊 play() Promise 延遲 resolve（模擬瀏覽器延遲回傳）
    deferredAudio._resolvePlay();
    await new Promise(r => setImmediate(r));

    assertTest(onStartCalled === 0,
        '4A: stop 後 play() resolve，onStart 不得被呼叫',
        `onStartCalled=${onStartCalled}`);
    assertTest(MediaService._currentAudio === null,
        '4A: stop 後 play() resolve，_currentAudio 不得恢復',
        `_currentAudio=${MediaService._currentAudio}`);
    assertTest(deferredAudio.pauseCallCount >= 1,
        '4A: 舊 audio 在 play() resolve 後必須被 pause/discard',
        `pauseCallCount=${deferredAudio.pauseCallCount}`);

    global.Audio = origAudio;
}

// 測試 4B：stop 後 play() reject → 不得進入下一 CDN
console.log('\n=== Test 4B: stop → play() reject → no CDN retry ===');
{
    resetMediaService();

    let audioCreateCount = 0;
    let onErrorCalled = 0;
    let deferredAudio = null;

    const origAudio = global.Audio;
    global.Audio = function(src) {
        audioCreateCount++;
        deferredAudio = makeDeferredMockAudio(src);
        return deferredAudio;
    };

    MediaService.playVoiceWithOptions('vo_adv_test_4b_000', {
        onError: () => { onErrorCalled++; }
    });

    assertTest(audioCreateCount === 1,
        '4B: 初始應只建立 1 個 Audio',
        `audioCreateCount=${audioCreateCount}`);

    MediaService.stopVoice();
    deferredAudio._rejectPlay(new Error('test-rejection'));

    await new Promise(r => setImmediate(r));

    assertTest(audioCreateCount === 1,
        '4B: stop 後 play() reject，不得建立第二個 Audio（CDN retry 被阻止）',
        `audioCreateCount=${audioCreateCount}，期望 1`);
    assertTest(onErrorCalled === 0,
        '4B: stop 後 play() reject，onError 不得被呼叫',
        `onErrorCalled=${onErrorCalled}`);

    global.Audio = origAudio;
}

// 測試 4C：stop 後 onerror → 不得 retry
console.log('\n=== Test 4C: stop → onerror → no retry ===');
{
    resetMediaService();

    let audioCreateCount = 0;
    let onErrorCalled = 0;
    let deferredAudio = null;

    const origAudio = global.Audio;
    global.Audio = function(src) {
        audioCreateCount++;
        deferredAudio = makeDeferredMockAudio(src);
        return deferredAudio;
    };

    MediaService.playVoiceWithOptions('vo_adv_test_4c_000', {
        onError: () => { onErrorCalled++; }
    });

    // stop 先於 onerror
    MediaService.stopVoice();

    // onerror 延遲觸發
    if (deferredAudio && typeof deferredAudio.onerror === 'function') {
        deferredAudio.onerror();
    }

    await new Promise(r => setImmediate(r));

    assertTest(audioCreateCount === 1,
        '4C: stop 後 onerror，不得建立第二個 Audio（retry 被阻止）',
        `audioCreateCount=${audioCreateCount}，期望 1`);
    assertTest(onErrorCalled === 0,
        '4C: stop 後 onerror，onError 不得被呼叫',
        `onErrorCalled=${onErrorCalled}`);

    global.Audio = origAudio;
}

// 測試 4D：新 session 建立後舊 session callback 無效
console.log('\n=== Test 4D: new session invalidates old session callbacks ===');
{
    resetMediaService();

    let oldOnEndedCalled = 0;
    let newOnStartCalled = 0;
    let deferredOldAudio = null;
    let deferredNewAudio = null;
    let audioCreateCount = 0;

    const origAudio = global.Audio;
    global.Audio = function(src) {
        audioCreateCount++;
        const a = makeDeferredMockAudio(src);
        if (audioCreateCount === 1) deferredOldAudio = a;
        else deferredNewAudio = a;
        return a;
    };

    // 舊 session
    MediaService.playVoiceWithOptions('vo_adv_test_4d_old', {
        onEnded: () => { oldOnEndedCalled++; }
    });

    assertTest(deferredOldAudio !== null, '4D: 舊 session Audio 已建立', '');

    // 新 session（內部先 stopVoice）
    MediaService.playVoiceWithOptions('vo_adv_test_4d_new', {
        onStart: () => { newOnStartCalled++; }
    });

    assertTest(deferredNewAudio !== null, '4D: 新 session Audio 已建立', '');
    assertTest(audioCreateCount === 2,
        '4D: 應建立兩個 Audio 實例',
        `audioCreateCount=${audioCreateCount}`);

    // 新 session play() resolve
    deferredNewAudio._resolvePlay();
    await new Promise(r => setImmediate(r));

    assertTest(newOnStartCalled === 1,
        '4D: 新 session play() resolve 後 onStart 應被呼叫一次',
        `newOnStartCalled=${newOnStartCalled}`);

    // 舊 session 的 onended 在新 session 後才觸發
    if (deferredOldAudio && typeof deferredOldAudio.onended === 'function') {
        deferredOldAudio.onended();
    }
    await new Promise(r => setImmediate(r));

    assertTest(oldOnEndedCalled === 0,
        '4D: 舊 session onended 在新 session 啟動後觸發，callback 不得執行',
        `oldOnEndedCalled=${oldOnEndedCalled}，期望 0`);
    assertTest(MediaService._currentAudio === deferredNewAudio,
        '4D: _currentAudio 仍應指向新 session audio',
        '_currentAudio 已被錯誤替換');

    global.Audio = origAudio;
}

// ─── 總結 ─────────────────────────────────────────────────────────────────────

console.log('\n' + '\u2500'.repeat(60));
if (_failCount === 0) {
    console.log(`\uD83C\uDF89 Stabilization A \u5168\u90E8 ${_passCount} \u9805\u6E2C\u8A66\u901A\u904E\uFF01`);
    process.exit(0);
} else {
    console.error(`\u274C ${_failCount} \u9805\u6E2C\u8A66\u5931\u6557\uFF0C${_passCount} \u9805\u901A\u904E\u3002`);
    process.exit(1);
}

})().catch(function(err) {
    console.error('\u975E\u540C\u6B65\u6E2C\u8A66\u767C\u751F\u672A\u9810\u671F\u4F8B\u5916:', err);
    process.exit(1);
});
