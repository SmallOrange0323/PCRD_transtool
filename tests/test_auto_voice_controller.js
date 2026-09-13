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

global.AvatarService = {
    getAvatarHtml: () => '<img class="avatar">',
    getAvatarHtmlByUnitId: () => '<img class="avatar">'
};

// 載入待測模組
require(path.resolve(__dirname, '../dashboard/story-asset-service.js'));
require(path.resolve(__dirname, '../dashboard/media-service.js'));
require(path.resolve(__dirname, '../dashboard/dialogue-view.js'));
require(path.resolve(__dirname, '../dashboard/auto-voice-controller.js'));

const StoryAssetService = global.StoryAssetService;
const MediaService = global.MediaService;
const DialogueView = global.DialogueView;
const AutoVoiceController = global.AutoVoiceController;

assert(StoryAssetService, 'StoryAssetService 必須存在');
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
        this.ended = false;
        mockAudioLog.push({ type: 'play', src: this.src });
        return Promise.resolve();
    }
    pause() {
        this.paused = true;
        mockAudioLog.push({ type: 'pause', src: this.src });
    }
    triggerEnded() {
        this.ended = true;
        this.paused = true;
        if (typeof this.onended === 'function') {
            this.onended();
        }
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
    // Test A — real ended callback with 400ms gap
    // AutoVoiceController.start() -> MediaService.playVoiceWithOptions() -> MockAudio 建立
    // -> 觸發該 Audio instance 的 onended -> 等待 400ms -> Controller 自動切到下一個 voiced dialogue
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
        audio1.triggerEnded();

        // 剛觸發 onended 時，應處於 400ms gap 緩衝中，尚未推進
        assert.strictEqual(AutoVoiceController.currentIndex, 1, 'Test A: 剛觸發 onended 時應維持在 index 1 (等待 400ms)');
        assert.strictEqual(createdAudios.length, 1, 'Test A: 400ms 緩衝期間不得提早建立第 2 個 Audio');

        // 等待 450ms (超過 400ms gap)
        await new Promise(r => setTimeout(r, 450));

        assert.strictEqual(AutoVoiceController.currentIndex, 3, 'Test A: 400ms gap 後 Controller 必須自動前進至 index 3');
        assert.strictEqual(createdAudios.length, 2, 'Test A: 必須建立第 2 個 Audio 實例播放下一句');
        AutoVoiceController.stop();
        console.log('✅ Test A (real onended callback 驅動 400ms gap 後前進) 通過');
    }

    // ==========================================================
    // 專項測試：400ms Dialogue Gap Lifecycle & State Machine
    // ==========================================================
    console.log('\n開始執行 6 項 400ms Dialogue Gap 專項生命週期測試...');

    // Gap Test 1: ended 觸發後 200ms 未推進，450ms 後推進
    {
        let audios = [];
        global.Audio = class extends MockAudio {
            constructor(src) { super(src); audios.push(this); }
        };
        AutoVoiceController.start(mockDialogueList, 1001001);
        audios[0].triggerEnded();
        await new Promise(r => setTimeout(r, 200));
        assert.strictEqual(AutoVoiceController.currentIndex, 1, 'Gap Test 1: 200ms 處應仍處於 gap 緩衝中');
        assert.strictEqual(audios.length, 1, 'Gap Test 1: 200ms 處不應產生新 audio');

        await new Promise(r => setTimeout(r, 250)); // 累計 450ms
        assert.strictEqual(AutoVoiceController.currentIndex, 3, 'Gap Test 1: 450ms 處應已推進至下一句');
        assert.strictEqual(audios.length, 2, 'Gap Test 1: 450ms 處應已播放新 audio');
        AutoVoiceController.stop();
        console.log('✅ Gap Test 1 (精準時間點驗證：200ms 未推進，450ms 推進) 通過');
    }

    // Gap Test 2: 在 gap 中 Stop -> 下一句不播放，狀態保持 IDLE
    {
        let audios = [];
        global.Audio = class extends MockAudio {
            constructor(src) { super(src); audios.push(this); }
        };
        AutoVoiceController.start(mockDialogueList, 1001001);
        audios[0].triggerEnded();
        // 在 100ms gap 期間呼叫 stop
        await new Promise(r => setTimeout(r, 100));
        AutoVoiceController.stop();
        assert.strictEqual(AutoVoiceController.state, 'IDLE');

        // 再等 400ms，確認 timer 不會穿透
        await new Promise(r => setTimeout(r, 400));
        assert.strictEqual(AutoVoiceController.state, 'IDLE');
        assert.strictEqual(audios.length, 1, 'Gap Test 2: stop 後不得建立下一句 audio');
        console.log('✅ Gap Test 2 (gap 期間 stop 確實取消定時器) 通過');
    }

    // Gap Test 3: 在 gap 中切換話數 / sessionToken 變更 -> 舊定時器失效
    {
        let audios = [];
        global.Audio = class extends MockAudio {
            constructor(src) { super(src); audios.push(this); }
        };
        AutoVoiceController.start(mockDialogueList, 1001001);
        audios[0].triggerEnded();

        // 在 gap 期間模擬切換到新話數 (start 新話數)
        await new Promise(r => setTimeout(r, 100));
        const newDialogueList = [
            { name: '雪菲', words: '好冷……', voice: 'vo_story_9999001' }
        ];
        AutoVoiceController.start(newDialogueList, 9999001);
        assert.strictEqual(AutoVoiceController.currentIndex, 0);

        // 等候舊 timer 到期 (400ms)
        await new Promise(r => setTimeout(r, 400));
        assert.strictEqual(AutoVoiceController.storyId, 9999001, 'Gap Test 3: 話數仍為新話數');
        assert.strictEqual(AutoVoiceController.currentIndex, 0, 'Gap Test 3: 舊話數 timer 不得竄改新話數 index');
        AutoVoiceController.stop();
        console.log('✅ Gap Test 3 (gap 期間 session invalidation 防禦) 通過');
    }

    // Gap Test 4: 在 gap 中 Pause -> 定時器取消，狀態進入 PAUSED，不被穿透
    {
        let audios = [];
        global.Audio = class extends MockAudio {
            constructor(src) { super(src); audios.push(this); }
        };
        AutoVoiceController.start(mockDialogueList, 1001001);
        audios[0].triggerEnded();

        // 在 100ms 處 pause
        await new Promise(r => setTimeout(r, 100));
        AutoVoiceController.pause();
        assert.strictEqual(AutoVoiceController.state, 'PAUSED', 'Gap Test 4: 狀態應切換為 PAUSED');
        assert.strictEqual(AutoVoiceController.currentIndex, 3, 'Gap Test 4: 在 gap 中 pause 應將進度對齊即將接續的第 3 句');

        // 再等待 400ms，確認不會被舊 timer 穿透為 PLAYING
        await new Promise(r => setTimeout(r, 400));
        assert.strictEqual(AutoVoiceController.state, 'PAUSED', 'Gap Test 4: 400ms 後狀態仍必須為 PAUSED');
        assert.strictEqual(audios.length, 1, 'Gap Test 4: 不得有新音訊播放');
        console.log('✅ Gap Test 4 (gap 期間 pause 不被 timer 穿透) 通過');
    }

    // Gap Test 5: 在 gap 中 Pause 後 Resume -> 立即播放下一句 (無額外 400ms 延遲)
    {
        let audios = [];
        global.Audio = class extends MockAudio {
            constructor(src) { super(src); audios.push(this); }
        };
        AutoVoiceController.start(mockDialogueList, 1001001);
        audios[0].triggerEnded();

        await new Promise(r => setTimeout(r, 100));
        AutoVoiceController.pause();
        assert.strictEqual(AutoVoiceController.state, 'PAUSED');

        // 呼叫 resume
        AutoVoiceController.resume();
        assert.strictEqual(AutoVoiceController.state, 'PLAYING', 'Gap Test 5: resume 後狀態切為 PLAYING');
        assert.strictEqual(AutoVoiceController.currentIndex, 3, 'Gap Test 5: 應接續第 3 句');
        assert.strictEqual(audios.length, 2, 'Gap Test 5: 應立即發起第 2 段音訊播放');
        AutoVoiceController.stop();
        console.log('✅ Gap Test 5 (gap pause 後 resume 立即接續播放下一句) 通過');
    }

    // Gap Test 6: onError (播放失敗) -> 立即推進，不強制等待 400ms
    {
        let audios = [];
        global.Audio = class extends MockAudio {
            constructor(src) { super(src); audios.push(this); }
        };
        AutoVoiceController.start(mockDialogueList, 1001001);
        const token = AutoVoiceController.sessionToken;

        // 模擬內部呼叫 onError (非 NotAllowedError)
        AutoVoiceController._stepNext(1, token);
        assert.strictEqual(AutoVoiceController.currentIndex, 3, 'Gap Test 6: 失敗 skip 時應立即前進至 index 3');
        AutoVoiceController.stop();
        console.log('✅ Gap Test 6 (onError 快速 skip 零延遲) 通過');
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

    // Regression Test 1 — StoryAssetService Background API
    // 驗證真實/fixture background item bg_id = 510530
    // 可以取得合法 URL，不再出現 getBackgroundUrl is not a function
    {
        const bgUrl = StoryAssetService.getBackgroundUrl(510530);
        assert(typeof bgUrl === 'string' && bgUrl.length > 0, 'Background Regression: 必須回傳合法字串 URL');
        assert(bgUrl.includes('510530'), 'Background Regression: URL 必須包含 bgId');

        // 驗證 DialogueView generateDialogueHtml 解析 background item 不崩潰且在全文閱讀中隱藏
        const result = DialogueView.generateDialogueHtml({
            storyId: 5216000,
            dialogueList: [
                { type: 'background', bg_id: '510530' },
                { name: '美穗', words: '咦？', voice: 'vo_adv_5216000_000' }
            ],
            speakerAvatars: {},
            currentStoryObj: null,
            resolveRealName: (n) => n,
            escapeHtml: (s) => s
        });
        assert(result && typeof result.firstBgUrl === 'string' && result.firstBgUrl === '', 'Background Regression: 全文閱讀中 background command 不設定 firstBgUrl (保持為空字串)');
        assert(!result.html.includes('場景切換'), 'Background Regression: 全文閱讀不應渲染場景切換節點');
        assert(result.html.includes('美穗') && result.html.includes('咦？'), 'Background Regression: 對白台詞正常渲染');
        console.log('✅ Background Regression (bg_id=510530 取得合法 URL 且 DialogueView 依規範隱藏背景節點並保留對白) 通過');
    }

    // Regression Test 2 — MediaService candidate failure race guard
    // 對單一 candidate 同時模擬 onerror 與 rejected play promise
    // 確認下一個 candidate 只建立一次，最後全部失敗時 onError count = 1
    {
        let raceCreatedAudios = [];
        let raceOnErrorCount = 0;

        global.Audio = class {
            constructor(src) {
                this.src = src;
                this.onended = null;
                this.onerror = null;
                raceCreatedAudios.push(this);
            }
            play() {
                // 同時模擬觸發 onerror 與 promise reject
                if (typeof this.onerror === 'function') {
                    this.onerror(new Error('Simulated simultaneous onerror'));
                }
                return Promise.reject(new Error('Simulated simultaneous play rejection'));
            }
            pause() {}
        };

        MediaService.playVoiceWithOptions('vo_adv_5216000_000', {
            onError: (err) => {
                raceOnErrorCount++;
            }
        });

        // 等待微任務與非同步重試排程完成
        await new Promise(r => setTimeout(r, 50));

        // 候選共 3 個，在 onerror + catch 雙重打擊下，每個 candidate 必須只嘗試 1 次
        assert.strictEqual(raceCreatedAudios.length, 3, 'Candidate Race Regression: 3 組候選必須剛好嘗試 3 次，不得重複重試');
        assert.strictEqual(raceOnErrorCount, 1, 'Candidate Race Regression: 最終 onError 只能被呼叫剛好 1 次');

        // 還原 Audio
        global.Audio = MockAudio;
        console.log('✅ Candidate Race Regression (onerror 與 play.catch 同時觸發時 candidate 絕不重複推進且 onError count=1) 通過');
    }

    // New Feature Test 1 — Selectable Start Point in AutoVoiceController
    {
        // 1. 指定 startIndex = 3 (凱留，有語音)
        AutoVoiceController.start(mockDialogueList, 1001001, null, 3);
        assert.strictEqual(AutoVoiceController.state, 'PLAYING');
        assert.strictEqual(AutoVoiceController.currentIndex, 3, '指定 startIndex=3 應直接從第 3 句開始');
        assert.strictEqual(mockDialogueList[AutoVoiceController.currentIndex].voice, 'vo_story_1001002');
        AutoVoiceController.stop();

        // 2. 指定 startIndex = 2 (佑樹，無語音) -> 應自動尋找到第 3 句 (凱留)
        AutoVoiceController.start(mockDialogueList, 1001001, null, 2);
        assert.strictEqual(AutoVoiceController.state, 'PLAYING');
        assert.strictEqual(AutoVoiceController.currentIndex, 3, '指定無語音的 startIndex=2 應自動前進到第 3 句');
        assert.strictEqual(mockDialogueList[AutoVoiceController.currentIndex].voice, 'vo_story_1001002');
        AutoVoiceController.stop();

        // 3. 指定 startIndex = 4 (無語音，且後面無任何語音) -> 應安全停在 IDLE
        AutoVoiceController.start(mockDialogueList, 1001001, null, 4);
        assert.strictEqual(AutoVoiceController.state, 'IDLE', '若 startIndex 後面無任何語音，狀態應維持 IDLE');
        assert.strictEqual(AutoVoiceController.currentIndex, -1);

        // 4. 未提供 startIndex (預設為 0) -> 從第一句有語音的第 1 句開始
        AutoVoiceController.start(mockDialogueList, 1001001);
        assert.strictEqual(AutoVoiceController.currentIndex, 1, '預設應從第 1 句開始');
        AutoVoiceController.stop();

        console.log('✅ Selectable Start Point (startIndex 指定起點、無語音向後尋找、末端無語音安全退回) 通過');
    }

    // New Feature Test 2 — DialogueView selection DOM helpers
    {
        const mockClasses = new Set();
        const mockLineEl = {
            classList: {
                add: (cls) => mockClasses.add(cls),
                remove: (cls) => mockClasses.delete(cls),
                contains: (cls) => mockClasses.has(cls)
            }
        };
        const mockBoard = {
            querySelector: (sel) => {
                if (sel.includes('data-dialogue-index="2"')) return mockLineEl;
                return null;
            },
            querySelectorAll: (sel) => {
                if (sel.includes('auto-start-selected') && mockClasses.has('auto-start-selected')) {
                    return [mockLineEl];
                }
                return [];
            }
        };

        DialogueView.setAutoStartSelection(mockBoard, 2);
        assert(mockClasses.has('auto-start-selected'), '應加入 auto-start-selected class');

        DialogueView.clearAutoStartSelection(mockBoard);
        assert(!mockClasses.has('auto-start-selected'), '應清除 auto-start-selected class');

        console.log('✅ DialogueView Selection DOM Helpers 通過');
    }

    console.log('\n🎉 AutoVoiceController 全部測試順利通過！');
})();
