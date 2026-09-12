console.log("auto-voice-controller.js loaded");
/**
 * PCRD Data Hub - 劇情對白自動語音連播控制器 (AutoVoiceController)
 * 負責單話內多句語音連續播放調度 (Sequential Voice Playback Orchestration)、
 * 狀態機維護 (IDLE / PLAYING / PAUSED)、非同步 Session Token 防護、
 * 以及播放中對白行之 DOM 狀態與捲動同步。
 * 
 * 本模組遵循單一職責原則 (SRP)：
 * 1. 語音 URL 解析與音訊播放：委派予 MediaService。
 * 2. 對白 DOM 渲染與高亮捲動：委派予 DialogueView。
 * 3. 話數生命週期與導航：由 QuestMapModule 呼叫 teardown。
 */

(function() {
    const AutoVoiceController = {
        state: 'IDLE', // 'IDLE' | 'PLAYING' | 'PAUSED'
        dialogueList: [],
        currentIndex: -1,
        sessionToken: 0,
        storyId: null,
        boardEl: null,

        // 外部狀態變更監聽回呼 (供 QuestMapModule 更新按鈕 UI)
        onStateChange: null,

        /**
         * 啟動 AUTO 語音連播 (從話數第一句有語音的對白開始)
         * @param {Array<Object>} dialogueList - 當前話數對白列表
         * @param {number|string} storyId - 當前話數 ID
         * @param {HTMLElement} [boardEl] - 對白看板容器元素
         */
        start(dialogueList, storyId, boardEl) {
            this.stop(); // 確保舊 Session 徹底結束

            if (!dialogueList || !Array.isArray(dialogueList) || dialogueList.length === 0) {
                console.warn('[AutoVoiceController] 無可播放的對白列表');
                return;
            }

            this.dialogueList = dialogueList;
            this.storyId = storyId;
            this.boardEl = boardEl || (typeof document !== 'undefined' ? document.getElementById('dialogue-board') : null);

            const firstVoicedIndex = this.findNextVoicedIndex(0);
            if (firstVoicedIndex === -1) {
                console.warn('[AutoVoiceController] 當前話數無任何語音對白');
                this._notifyState('IDLE');
                return;
            }

            this.sessionToken++;
            this.state = 'PLAYING';
            this._notifyState('PLAYING');

            this._playIndex(firstVoicedIndex, this.sessionToken);
        },

        /**
         * 暫停 AUTO 連播 (保留當前播放進度與高亮)
         */
        pause() {
            if (this.state !== 'PLAYING') return;

            if (window.MediaService && typeof window.MediaService.pauseVoice === 'function') {
                window.MediaService.pauseVoice();
            }

            this.state = 'PAUSED';
            this._notifyState('PAUSED');
        },

        /**
         * 接續 AUTO 連播 (從當前暫停進度繼續)
         */
        resume() {
            if (this.state !== 'PAUSED') return;

            let resumed = false;
            if (window.MediaService && typeof window.MediaService.resumeVoice === 'function') {
                const playPromise = window.MediaService.resumeVoice();
                if (playPromise) {
                    resumed = true;
                    if (typeof playPromise.catch === 'function') {
                        playPromise.catch(err => {
                            console.warn('[AutoVoiceController] 接續播放失敗:', err);
                            if (err && err.name === 'NotAllowedError') {
                                this.stop();
                            }
                        });
                    }
                }
            }

            if (resumed) {
                this.state = 'PLAYING';
                this._notifyState('PLAYING');
            } else {
                // 若無 current Audio 可接續，但當前對白有效，嘗試重新發起該句播放；否則停止
                if (this.currentIndex >= 0 && this.dialogueList && this.dialogueList[this.currentIndex]) {
                    this.state = 'PLAYING';
                    this._notifyState('PLAYING');
                    this._playIndex(this.currentIndex, this.sessionToken);
                } else {
                    this.stop();
                }
            }
        },

        /**
         * 徹底終止 AUTO 連播，使舊 Session 回呼完全失效並清理視圖
         */
        stop() {
            this.sessionToken++; // 使非同步回呼 (ended / error / promise) 立即失效

            if (window.MediaService && typeof window.MediaService.stopVoice === 'function') {
                window.MediaService.stopVoice();
            }

            if (window.DialogueView && typeof window.DialogueView.clearDialogueHighlight === 'function') {
                const board = this.boardEl || (typeof document !== 'undefined' ? document.getElementById('dialogue-board') : null);
                if (board) {
                    window.DialogueView.clearDialogueHighlight(board);
                }
            }

            this.state = 'IDLE';
            this.currentIndex = -1;
            this.dialogueList = [];
            this.storyId = null;

            this._notifyState('IDLE');
        },

        /**
         * 從指定索引往後搜尋下一個具備語音的對白索引
         * @param {number} fromIndex - 開始搜尋的索引
         * @returns {number} 找到的索引，若無則返回 -1
         */
        findNextVoicedIndex(fromIndex) {
            if (!this.dialogueList || !Array.isArray(this.dialogueList)) return -1;
            const start = Math.max(0, fromIndex || 0);
            for (let i = start; i < this.dialogueList.length; i++) {
                const item = this.dialogueList[i];
                if (item && item.voice && typeof item.voice === 'string' && item.voice.trim()) {
                    return i;
                }
            }
            return -1;
        },

        /**
         * 播放指定索引之對白語音
         * @private
         * @param {number} index - 對白索引
         * @param {number} token - Session Token Guard
         */
        _playIndex(index, token) {
            if (token !== this.sessionToken || this.state !== 'PLAYING') return;

            const item = this.dialogueList[index];
            if (!item || !item.voice) {
                // 若當前行無語音，推進至下一句
                this._stepNext(index, token);
                return;
            }

            this.currentIndex = index;

            // 更新 DOM 高亮與自動捲動
            const board = this.boardEl || (typeof document !== 'undefined' ? document.getElementById('dialogue-board') : null);
            if (board && window.DialogueView && typeof window.DialogueView.highlightDialogueLine === 'function') {
                window.DialogueView.highlightDialogueLine(board, index);
            }

            if (!window.MediaService || typeof window.MediaService.playVoiceWithOptions !== 'function') {
                console.error('[AutoVoiceController] MediaService 缺少 playVoiceWithOptions 介面');
                this.stop();
                return;
            }

            window.MediaService.playVoiceWithOptions(item.voice, {
                onEnded: () => {
                    if (token !== this.sessionToken || this.state !== 'PLAYING') return;
                    this._stepNext(index, token);
                },
                onError: (err) => {
                    if (token !== this.sessionToken || this.state !== 'PLAYING') return;

                    if (err && err.name === 'NotAllowedError') {
                        console.warn('[AutoVoiceController] 瀏覽器 Autoplay 政策封鎖，終止 AUTO。');
                        this.stop();
                        return;
                    }

                    console.warn(`[AutoVoiceController] 對白語音播放失敗 (${item.voice})，自動跳過本句。`);
                    this._stepNext(index, token);
                }
            });
        },

        /**
         * 推進至下一句具備語音之對白
         * @private
         * @param {number} currentIndex - 當前索引
         * @param {number} token - Session Token Guard
         */
        _stepNext(currentIndex, token) {
            if (token !== this.sessionToken || this.state !== 'PLAYING') return;

            const nextIndex = this.findNextVoicedIndex(currentIndex + 1);
            if (nextIndex !== -1) {
                this._playIndex(nextIndex, token);
            } else {
                // 已抵達故事結尾 (無更多語音)
                this.stop();
            }
        },

        /**
         * 手動播放語音時的攔截處置 (AUTO 終止)
         */
        onManualVoicePlay() {
            if (this.state !== 'IDLE') {
                this.stop();
            }
        },

        /**
         * 是否正在進行 AUTO 連播 (含 PLAYING 與 PAUSED)
         * @returns {boolean}
         */
        isActive() {
            return this.state !== 'IDLE';
        },

        /**
         * 是否正在實際播放中 (不含 PAUSED)
         * @returns {boolean}
         */
        isPlaying() {
            return this.state === 'PLAYING';
        },

        /**
         * 通知外部監聽器狀態變更
         * @private
         * @param {string} newState
         */
        _notifyState(newState) {
            if (typeof this.onStateChange === 'function') {
                try {
                    this.onStateChange(newState, this);
                } catch (e) {
                    console.error('[AutoVoiceController] onStateChange 執行異常:', e);
                }
            }
        }
    };

    // 掛載至全域環境
    if (typeof window !== 'undefined') {
        window.AutoVoiceController = AutoVoiceController;
    } else if (typeof global !== 'undefined') {
        global.AutoVoiceController = AutoVoiceController;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = AutoVoiceController;
    }
})();
