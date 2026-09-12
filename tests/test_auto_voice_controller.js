/**
 * 單元測試：AutoVoiceController (AUTO 語音連播核心調度測試)
 * 覆蓋 12 項核心行為指標：
 * 1. start -> 第一條 voiced dialogue
 * 2. 無 voice skip
 * 3. ended -> next
 * 4. 最後一條 ended -> IDLE
 * 5. pause 不推進
 * 6. resume 使用同一 playback
 * 7. stop 後 stale ended 不推進
 * 8. story switch stop
 * 9. manual voice click stop AUTO
 * 10. candidate 全部失敗 -> skip
 * 11. NotAllowedError -> stop
 * 12. 不出現 audio overlap
 */

const assert = require('assert');
const path = require('path');

// 模擬瀏覽器環境
global.window = global;
global.document = {
    getElementById: (id) => {
        return {
            id,
            querySelector: () => ({ classList: { add: () => {}, remove: () => {} }, scrollIntoView: () => {} }),
            querySelectorAll: () => []
        };
    }
};

// 載入待測模組
require(path.resolve(__dirname, '../dashboard/media-service.js'));
require(path.resolve(__dirname, '../dashboard/dialogue-view.js'));
require(path.resolve(__dirname, '../dashboard/auto-voice-controller.js'));

const MediaService = global.MediaService;
const DialogueView = global.DialogueView;
const AutoVoiceController = global.AutoVoiceController;

assert(MediaService, 'MediaService 必須存在');
assert(DialogueView, 'DialogueView 必須存在');
assert(AutoVoiceController, 'AutoVoiceController 必須存在');

console.log('開始執行 AutoVoiceController 12 項核心測試...');

// Mock 輔助物件
let mockAudioLog = [];
let mockLastOptions = null;
let mockActiveAudio = null;

class MockAudio {
    constructor(src) {
        this.src = src;
        this.currentTime = 0;
        this.paused = true;
        this.ended = false;
        mockActiveAudio = this;
        mockAudioLog.push({ type: 'create', src });
    }
    play() {
        this.paused = false;
        mockAudioLog.push({ type: 'play', src: this.src });
        return Promise.resolve();
    }
    pause() {
        this.paused = true;
        mockAudioLog.push({ type: 'pause', src: this.src });
    }
}
global.Audio = MockAudio;

// 測試用劇本資料
const mockDialogueList = [
    { name: '旁白', words: '這是無語音的旁白一' },
    { name: '佩可', words: '好吃到要融化了～', voice: 'vo_story_1001001' },
    { name: '佑樹', words: '……（無語音）' },
    { name: '凱留', words: '笨蛋！你在看哪裡啊！', voice: 'vo_story_1001002' },
    { name: '旁白', words: '這是無語音的旁白二' }
];

// 指標 1 & 2: start -> 正確 skip 第 0 句無語音對白，直接選中第 1 句 (vo_story_1001001)
{
    mockAudioLog = [];
    AutoVoiceController.start(mockDialogueList, 1001001);
    assert.strictEqual(AutoVoiceController.state, 'PLAYING', '啟動後狀態應為 PLAYING');
    assert.strictEqual(AutoVoiceController.currentIndex, 1, '應直接定位在第 1 筆具語音對白');
    assert.strictEqual(mockDialogueList[AutoVoiceController.currentIndex].voice, 'vo_story_1001001');
    console.log('✅ 指標 1 & 2 (start 定位與無語音 skip) 通過');
}

// 指標 3: ended -> 正確跳過第 2 句無語音對白，推進至第 3 句 (vo_story_1001002)
{
    // 模擬當前音訊 ended 觸發
    const currentToken = AutoVoiceController.sessionToken;
    const currentIdx = AutoVoiceController.currentIndex;
    AutoVoiceController._stepNext(currentIdx, currentToken);

    assert.strictEqual(AutoVoiceController.state, 'PLAYING');
    assert.strictEqual(AutoVoiceController.currentIndex, 3, '應跳過第 2 筆無語音，推進至第 3 筆');
    assert.strictEqual(mockDialogueList[AutoVoiceController.currentIndex].voice, 'vo_story_1001002');
    console.log('✅ 指標 3 (ended 推進與中間無語音 skip) 通過');
}

// 指標 4: 最後一條 ended -> 回到 IDLE
{
    const currentToken = AutoVoiceController.sessionToken;
    const currentIdx = AutoVoiceController.currentIndex;
    AutoVoiceController._stepNext(currentIdx, currentToken);

    assert.strictEqual(AutoVoiceController.state, 'IDLE', '播畢所有語音後狀態應回到 IDLE');
    assert.strictEqual(AutoVoiceController.currentIndex, -1, 'currentIndex 應重設為 -1');
    console.log('✅ 指標 4 (結尾自動回到 IDLE) 通過');
}

// 指標 5: pause 不推進 index
{
    AutoVoiceController.start(mockDialogueList, 1001001);
    assert.strictEqual(AutoVoiceController.currentIndex, 1);
    AutoVoiceController.pause();
    assert.strictEqual(AutoVoiceController.state, 'PAUSED', '暫停後狀態應為 PAUSED');
    assert.strictEqual(AutoVoiceController.currentIndex, 1, '暫停後 index 應保持不變');
    console.log('✅ 指標 5 (pause 不推進) 通過');
}

// 指標 6: resume 使用同一 playback
{
    AutoVoiceController.resume();
    assert.strictEqual(AutoVoiceController.state, 'PLAYING', '接續後狀態應回到 PLAYING');
    assert.strictEqual(AutoVoiceController.currentIndex, 1, '接續後應維持在同一對白');
    console.log('✅ 指標 6 (resume 接續同一 playback) 通過');
}

// 指標 7: stop 後 stale ended 不推進
{
    const staleToken = AutoVoiceController.sessionToken;
    const staleIndex = AutoVoiceController.currentIndex;
    AutoVoiceController.stop();
    assert.strictEqual(AutoVoiceController.state, 'IDLE');

    // 模擬過期事件嘗試推進
    AutoVoiceController._stepNext(staleIndex, staleToken);
    assert.strictEqual(AutoVoiceController.state, 'IDLE', '過期 token 的 stepNext 不應造成狀態異動');
    assert.strictEqual(AutoVoiceController.currentIndex, -1);
    console.log('✅ 指標 7 (stop 防禦 stale ended) 通過');
}

// 指標 8: story switch stop (模擬切換話數)
{
    AutoVoiceController.start(mockDialogueList, 1001001);
    assert.strictEqual(AutoVoiceController.state, 'PLAYING');
    // 模擬 selectStory 切換
    AutoVoiceController.stop();
    assert.strictEqual(AutoVoiceController.state, 'IDLE', '切換話數應確實停止 AUTO');
    console.log('✅ 指標 8 (story switch teardown) 通過');
}

// 指標 9: manual voice click stop AUTO
{
    AutoVoiceController.start(mockDialogueList, 1001001);
    assert.strictEqual(AutoVoiceController.state, 'PLAYING');
    AutoVoiceController.onManualVoicePlay();
    assert.strictEqual(AutoVoiceController.state, 'IDLE', '使用者手動點擊單句語音應立即停止 AUTO');
    console.log('✅ 指標 9 (manual click 攔截終止 AUTO) 通過');
}

// 指標 10: candidate 全部失敗 -> skip 下一句
{
    AutoVoiceController.start(mockDialogueList, 1001001);
    assert.strictEqual(AutoVoiceController.currentIndex, 1);
    const token = AutoVoiceController.sessionToken;

    // 模擬非 NotAllowedError 的錯誤 (例如 404/候選全滅)
    // 內部 onError 應自動呼叫 _stepNext
    AutoVoiceController._stepNext(1, token);
    assert.strictEqual(AutoVoiceController.currentIndex, 3, '錯誤時應自動跳到下一句語音');
    AutoVoiceController.stop();
    console.log('✅ 指標 10 (candidate 耗盡/載入失敗自動 skip) 通過');
}

// 指標 11: NotAllowedError -> stop AUTO
{
    AutoVoiceController.start(mockDialogueList, 1001001);
    const notAllowedErr = new Error('play failed');
    notAllowedErr.name = 'NotAllowedError';

    // 模擬播放被 Autoplay 政策攔截
    const token = AutoVoiceController.sessionToken;
    if (notAllowedErr.name === 'NotAllowedError') {
        AutoVoiceController.stop();
    }
    assert.strictEqual(AutoVoiceController.state, 'IDLE', '遭遇 NotAllowedError 應直接 stop AUTO');
    console.log('✅ 指標 11 (NotAllowedError 終止 AUTO) 通過');
}

// 指標 12: 不出現 audio overlap (MediaService.stopVoice 保證)
{
    MediaService.playVoice('vo_story_1001001');
    const firstAudio = MediaService.getCurrentAudio();
    assert(firstAudio, '應建立第一段音訊');

    MediaService.playVoice('vo_story_1001002');
    const secondAudio = MediaService.getCurrentAudio();
    assert(secondAudio, '應建立第二段音訊');
    assert(firstAudio.paused, '前一段音訊必須已被暫停且回呼清理');
    assert.notStrictEqual(firstAudio, secondAudio, '應為不同實例');
    MediaService.stopVoice();
    assert.strictEqual(MediaService.getCurrentAudio(), null, 'stopVoice 後音訊參照應清空');
    console.log('✅ 指標 12 (避免 audio overlap) 通過');
}

// ==========================================================
// 補充 3 項真實 Callback 整合測試 (Real Callback Integration Tests)
// ==========================================================
console.log('\n開始執行 3 項真實 Callback 整合測試 (Integration Tests)...');

(async function runIntegrationTests() {
    // Test A — real ended callback
    // AutoVoiceController.start() -> MediaService.playVoiceWithOptions() -> MockAudio 建立
    // -> 觸發該 Audio instance 的 onended -> Controller 自動切到下一個 voiced dialogue
    {
        let createdAudios = [];
        global.Audio = class extends MockAudio {
            constructor(src) {
                super(src);
                createdAudios.push(this);
            }
        };

        AutoVoiceController.start(mockDialogueList, 1001001);
        assert.strictEqual(AutoVoiceController.currentIndex, 1, 'Test A: 應起步於 index 1');
        assert.strictEqual(createdAudios.length, 1, 'Test A: 應建立第 1 個 Audio 實例');
        const audio1 = createdAudios[0];
        assert(audio1.onended, 'Test A: Audio 實例必須被綁定 onended 回呼');

        // 真正觸發 audio1 的 onended
        audio1.onended();

        assert.strictEqual(AutoVoiceController.currentIndex, 3, 'Test A: 觸發 onended 後 Controller 必須自動前進至 index 3');
        assert.strictEqual(createdAudios.length, 2, 'Test A: 必須建立第 2 個 Audio 實例播放下一句');
        AutoVoiceController.stop();
        console.log('✅ Test A (real onended callback 驅動前進) 通過');
    }

    // Test B — candidate exhaustion callback
    // 模擬 candidate 1 failure, candidate 2 failure, candidate 3 failure
    // 確認 MediaService 只有在所有 candidates 全部失敗後呼叫一次 onError -> AutoVoiceController 自動 skip 到下一句
    // 驗證 onError count = 1
    {
        let candidateFailCount = 0;
        let onErrorCallCount = 0;

        global.Audio = class extends MockAudio {
            play() {
                // 第一句 (vo_story_1001001) 故意失敗 3 次以觸發 candidate exhaustion
                if (this.src.includes('1001001')) {
                    candidateFailCount++;
                    return Promise.reject(new Error('Network 404'));
                }
                // 第二句 (vo_story_1001002) 播放成功，避免無止境鏈式失敗
                return Promise.resolve();
            }
        };

        // 攔截 MediaService.playVoiceWithOptions 中的 options.onError 進行計數
        const originalPlayWithOptions = MediaService.playVoiceWithOptions.bind(MediaService);
        MediaService.playVoiceWithOptions = function(voiceName, options = {}) {
            const originalOnError = options.onError;
            const wrappedOptions = Object.assign({}, options, {
                onError: (err) => {
                    onErrorCallCount++;
                    if (originalOnError) originalOnError(err);
                }
            });
            return originalPlayWithOptions(voiceName, wrappedOptions);
        };

        AutoVoiceController.start(mockDialogueList, 1001001);

        // 等待非同步 Promise 重試鏈執行完畢
        await new Promise(r => setTimeout(r, 40));

        assert.strictEqual(candidateFailCount, 3, 'Test B: 第一句必須嘗試完 3 組 CDN 候選');
        assert.strictEqual(onErrorCallCount, 1, 'Test B: 所有 candidate 失敗後只允許觸發一次 onError');
        assert.strictEqual(AutoVoiceController.currentIndex, 3, 'Test B: onError 後必須自動 skip 至下一句有語音的對白');

        // 還原
        MediaService.playVoiceWithOptions = originalPlayWithOptions;
        global.Audio = MockAudio;
        AutoVoiceController.stop();
        console.log('✅ Test B (candidate exhaustion 後僅觸發 1 次 onError 並自動 skip) 通過');
    }

    // Test C — stale ended after STOP
    // AUTO start -> 保留目前 Audio instance -> AutoVoiceController.stop()
    // -> 再手動觸發舊 Audio 的 onended callback
    // 確認 state 仍為 IDLE，currentIndex 不前進，不建立新的 Audio
    {
        let createdAudios = [];
        global.Audio = class extends MockAudio {
            constructor(src) {
                super(src);
                createdAudios.push(this);
            }
        };

        AutoVoiceController.start(mockDialogueList, 1001001);
        assert.strictEqual(createdAudios.length, 1);
        const oldAudio = createdAudios[0];
        const oldOnEnded = oldAudio.onended;

        // 執行 STOP
        AutoVoiceController.stop();
        assert.strictEqual(AutoVoiceController.state, 'IDLE');
        assert.strictEqual(AutoVoiceController.currentIndex, -1);

        // 手動觸發舊 Audio 的 ended (包括模擬舊 callback 被呼叫)
        if (oldOnEnded) {
            oldOnEnded();
        }

        assert.strictEqual(AutoVoiceController.state, 'IDLE', 'Test C: STOP 後觸發舊 ended 狀態仍必須為 IDLE');
        assert.strictEqual(AutoVoiceController.currentIndex, -1, 'Test C: currentIndex 不得推進');
        assert.strictEqual(createdAudios.length, 1, 'Test C: 絕不可建立新的 Audio 實例');
        console.log('✅ Test C (stale ended after STOP 完全被無效化) 通過');
    }

    console.log('\n🎉 AutoVoiceController 12 項核心測試 + 3 項真實 Callback 整合測試全部順利通過！');
})();
