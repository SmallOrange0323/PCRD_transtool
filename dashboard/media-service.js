console.log("media-service.js loaded");
/**
 * PCRD Data Hub - 多媒體服務模組 (MediaService)
 * 負責語音播放控制 (Voice Playback, CDN 鏡像降級重試, Autoplay 政策防護)
 * 與劇院 CG 插畫全螢幕放大彈窗 (Still Popup DOM 單例與互動事件)。
 * 
 * 本模組自帶私有音訊與鍵盤事件狀態，不依賴 QuestMapModule 內部業務邏輯。
 */

(function() {
    const MediaService = {
        _currentAudio: null,
        _stillPopupKeyHandler: null,

        /**
         * 根據 voiceName 產生語音候選 URL 列表 (依優先順序：本地 -> 鏡像 1 -> 鏡像 2)
         * @param {string} voiceName - 語音檔案標籤 (例如: vo_story_1001001)
         * @returns {string[]} 候選 URL 陣列
         */
        getVoiceCandidates(voiceName) {
            if (!voiceName || typeof voiceName !== 'string') return [];
            const groupId = voiceName.substring(7, 14);
            return [
                `sound/story_vo/${voiceName}.m4a`,
                `https://prcn-sound.estertion.win/story_vo/${groupId}/${voiceName}.m4a`,
                `https://redive.estertion.win/sound/story_vo/${groupId}/${voiceName}.m4a`
            ];
        },

        /**
         * 播放指定語音 (向後相容包裝)
         * @param {string} voiceName - 語音檔案標籤
         * @param {Object} [options] - 播放選項
         */
        playVoice(voiceName, options = {}) {
            return this.playVoiceWithOptions(voiceName, options);
        },

        /**
         * 播放指定語音並支援生命週期回呼 (AUTO 連播使用)
         * @param {string} voiceName - 語音檔案標籤
         * @param {Object} [options] - 選項 { onStart, onEnded, onError }
         */
        playVoiceWithOptions(voiceName, options = {}) {
            if (!voiceName) {
                if (typeof options.onError === 'function') {
                    options.onError(new Error('Missing voiceName'));
                }
                return;
            }
            const cdnList = this.getVoiceCandidates(voiceName);
            if (cdnList.length === 0) {
                if (typeof options.onError === 'function') {
                    options.onError(new Error('No candidate URLs for voiceName: ' + voiceName));
                }
                return;
            }

            // 停止並清理前一段音訊，避免事件重疊
            this.stopVoice();

            let isDisposed = false;

            const tryPlay = (index) => {
                if (isDisposed) return;

                if (index >= cdnList.length) {
                    console.warn('[MediaService] 該劇情的語音檔在遠端鏡像站尚未同步更新: ' + voiceName);
                    if (typeof options.onError === 'function') {
                        options.onError(new Error('All CDN candidates failed for: ' + voiceName));
                    }
                    return;
                }

                const audio = new Audio(cdnList[index]);
                this._currentAudio = audio;

                // 綁定結束事件
                audio.onended = () => {
                    if (isDisposed) return;
                    if (typeof options.onEnded === 'function') {
                        options.onEnded();
                    }
                };

                let failureHandled = false;
                const handleFailure = (err) => {
                    if (isDisposed || failureHandled) return;
                    failureHandled = true;

                    audio.onended = null;
                    audio.onerror = null;

                    if (err && err.name === 'NotAllowedError') {
                        console.warn('[MediaService] 語音播放被瀏覽器自動播放政策封鎖。');
                        if (typeof options.onError === 'function') {
                            options.onError(err);
                        }
                        return;
                    }

                    tryPlay(index + 1);
                };

                // 若載入中途出錯，嘗試下一候選 (防重守護)
                audio.onerror = () => {
                    handleFailure(new Error('Audio load error'));
                };

                audio.play().then(() => {
                    if (isDisposed) {
                        audio.pause();
                        return;
                    }
                    if (typeof options.onStart === 'function') {
                        options.onStart(audio);
                    }
                }).catch(err => {
                    handleFailure(err);
                });
            };

            tryPlay(0);
        },

        /**
         * 暫停目前正在播放的語音 (保留 currentTime)
         * @returns {boolean} 是否成功執行暫停
         */
        pauseVoice() {
            if (this._currentAudio && !this._currentAudio.paused) {
                this._currentAudio.pause();
                return true;
            }
            return false;
        },

        /**
         * 接續播放目前已暫停的語音 (從 currentTime 繼續)
         * @returns {Promise<void>|null}
         */
        resumeVoice() {
            if (this._currentAudio && this._currentAudio.paused && !this._currentAudio.ended) {
                return this._currentAudio.play();
            }
            return null;
        },

        /**
         * 徹底停止目前語音播放並清理回呼與實例
         */
        stopVoice() {
            if (this._currentAudio) {
                const audio = this._currentAudio;
                audio.onended = null;
                audio.onerror = null;
                try {
                    audio.pause();
                    audio.currentTime = 0;
                } catch (e) {
                    // 忽略跨來源或未就緒之例外
                }
                this._currentAudio = null;
            }
        },

        /**
         * 檢查目前是否正在播放語音
         * @returns {boolean}
         */
        isPlayingVoice() {
            return !!(this._currentAudio && !this._currentAudio.paused && !this._currentAudio.ended);
        },

        /**
         * 檢查目前是否為暫停狀態
         * @returns {boolean}
         */
        isPausedVoice() {
            return !!(this._currentAudio && this._currentAudio.paused && !this._currentAudio.ended && this._currentAudio.currentTime > 0);
        },

        /**
         * 取得目前 Audio 實例
         * @returns {Audio|null}
         */
        getCurrentAudio() {
            return this._currentAudio;
        },

        /**
         * 開啟 CG 插畫全螢幕放大預覽彈窗
         * @param {Event} event - 點擊事件
         */
        openStillPopup(event) {
            if (!event || !event.target) return;
            const container = event.target.closest('.game-dialogue-still');
            if (!container) return;
            const imgEl = container.querySelector('img');
            if (!imgEl || !imgEl.src) return;

            let overlay = document.getElementById('still-popup-overlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'still-popup-overlay';
                overlay.className = 'still-popup-overlay';
                overlay.onclick = (e) => {
                    if (e.target === overlay) {
                        this.closeStillPopup();
                    }
                };

                const closeBtn = document.createElement('button');
                closeBtn.className = 'still-popup-close-btn';
                closeBtn.innerHTML = '&times;';
                closeBtn.onclick = () => {
                    this.closeStillPopup();
                };

                const popupImg = document.createElement('img');
                popupImg.id = 'still-popup-img';
                popupImg.onclick = (e) => { e.stopPropagation(); };

                overlay.appendChild(popupImg);
                overlay.appendChild(closeBtn);
                document.body.appendChild(overlay);
            }

            const popupImg = document.getElementById('still-popup-img');
            popupImg.src = imgEl.src;

            if (imgEl.dataset.candidates) {
                popupImg.dataset.candidates = imgEl.dataset.candidates;
                popupImg.dataset.step = imgEl.dataset.step || "0";
                popupImg.onerror = function() {
                    window.StoryAssetService.handleImageError(this);
                };
            } else {
                popupImg.removeAttribute('data-candidates');
                popupImg.removeAttribute('data-step');
                popupImg.onerror = null;
            }

            requestAnimationFrame(() => {
                overlay.classList.add('active');
            });

            this._stillPopupKeyHandler = (e) => {
                if (e.key === 'Escape') this.closeStillPopup();
            };
            document.addEventListener('keydown', this._stillPopupKeyHandler);
        },

        /**
         * 正規化動畫 ID，去除 movie_ 或 story_ 前綴
         * @param {string|number} movieId - 動畫 ID
         * @returns {string} 正規化後的乾淨 ID
         */
        normalizeMovieId(movieId) {
            if (!movieId) return "";
            return String(movieId).replace(/^movie_/, '').replace(/^story_/, '').trim();
        },

        /**
         * 從映射表中查詢對應的 Google Drive File ID
         * @param {string|number} movieId - 動畫 ID
         * @param {Object} movieLinks - ID 映射字典
         * @returns {string|null} Google Drive File ID 或 null
         */
        lookupMovieGdriveId(movieId, movieLinks) {
            if (!movieLinks || typeof movieLinks !== 'object') return null;
            const cleanId = this.normalizeMovieId(movieId);
            if (!cleanId) return null;
            return movieLinks[cleanId] || movieLinks[`story_${cleanId}`] || null;
        },

        /**
         * 取得 Google Drive 內嵌預覽 URL (預設啟用自動播放)
         * @param {string} gdriveId - Google Drive File ID
         * @param {boolean} autoplay - 是否啟用自動播放
         * @returns {string|null} 預覽 URL 或 null
         */
        getMoviePreviewUrl(gdriveId, autoplay = true) {
            if (!gdriveId || typeof gdriveId !== 'string') return null;
            const base = `https://drive.google.com/file/d/${gdriveId}/preview`;
            return autoplay ? `${base}?autoplay=1` : base;
        },

        /**
         * 產生未映射/尚未上傳動畫的 Fallback 提示 HTML
         * @param {string} cleanId - 正規化後的動畫 ID
         * @returns {string} HTML 字串
         */
        getMovieFallbackHtml(cleanId) {
            return `
                <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #fff; background: #162030; padding: 24px; text-align: center;">
                    <div style="font-size: 2.6rem; margin-bottom: 12px; animation: pulse 2s infinite;">☁️</div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #60a5fa; margin-bottom: 8px;">動畫標識：story_${cleanId}</div>
                    <div style="font-size: 0.88rem; color: #cbd5e1; max-width: 480px; line-height: 1.6;">
                        此動畫正在準備上傳至 Google Drive 雲端中，或尚未同步至映射表。<br>
                        點擊遮罩任意處即可關閉。
                    </div>
                </div>
            `;
        },

        /**
         * 開啟過場動畫全螢幕/視窗播放彈窗 (純淨沉浸式影音播放，無外框標題列)
         * @param {string|number} movieId - 動畫 ID
         * @param {Object} movieLinks - 映射字典
         * @param {Document} doc - DOM Document 對象 (預設為全域 document)
         */
        openMoviePopup(movieId, movieLinks, doc) {
            if (!movieId) return;
            const targetDoc = doc || (typeof document !== 'undefined' ? document : null);
            if (!targetDoc) return;

            const cleanId = this.normalizeMovieId(movieId);
            const gdriveId = this.lookupMovieGdriveId(movieId, movieLinks);

            let modal = targetDoc.getElementById('movie-player-modal');
            if (!modal) {
                modal = targetDoc.createElement('div');
                modal.id = 'movie-player-modal';
                modal.className = 'movie-player-modal';
                modal.innerHTML = `
                    <div class="movie-player-box">
                        <div class="movie-player-body" id="movie-player-body"></div>
                    </div>
                `;
                targetDoc.body.appendChild(modal);
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) this.closeMoviePopup(targetDoc);
                });
            }

            // 綁定 ESC 鍵關閉
            if (!this._movieEscHandler) {
                this._movieEscHandler = (e) => {
                    if (e.key === 'Escape' || e.keyCode === 27) {
                        this.closeMoviePopup(targetDoc);
                    }
                };
                targetDoc.addEventListener('keydown', this._movieEscHandler);
            }

            const bodyEl = targetDoc.getElementById('movie-player-body');
            if (!bodyEl) return;

            if (gdriveId) {
                const previewUrl = this.getMoviePreviewUrl(gdriveId, true);
                bodyEl.innerHTML = `<iframe src="${previewUrl}" allow="autoplay; fullscreen; encrypted-media" allowfullscreen></iframe>`;
            } else {
                bodyEl.innerHTML = this.getMovieFallbackHtml(cleanId);
            }

            modal.classList.add('active');
            if (targetDoc.body && targetDoc.body.style) {
                targetDoc.body.style.overflow = 'hidden';
            }
        },

        /**
         * 關閉過場動畫彈窗並清空 iframe/body
         * @param {Document} doc - DOM Document 對象
         */
        closeMoviePopup(doc) {
            const targetDoc = doc || (typeof document !== 'undefined' ? document : null);
            if (!targetDoc) return;

            const modal = targetDoc.getElementById('movie-player-modal');
            if (modal) {
                modal.classList.remove('active');
                const bodyEl = targetDoc.getElementById('movie-player-body');
                if (bodyEl) bodyEl.innerHTML = '';
            }
            if (targetDoc.body && targetDoc.body.style) {
                targetDoc.body.style.overflow = '';
            }
            if (this._movieEscHandler) {
                targetDoc.removeEventListener('keydown', this._movieEscHandler);
                this._movieEscHandler = null;
            }
        },

        /**
         * 關閉 CG 插畫彈窗並清理鍵盤監聽事件
         */
        closeStillPopup() {
            const overlay = document.getElementById('still-popup-overlay');
            if (overlay) {
                overlay.classList.remove('active');
            }
            if (this._stillPopupKeyHandler) {
                document.removeEventListener('keydown', this._stillPopupKeyHandler);
                this._stillPopupKeyHandler = null;
            }
        }
    };

    // 掛載至全域環境
    if (typeof window !== 'undefined') {
        window.MediaService = MediaService;
    } else if (typeof global !== 'undefined') {
        global.MediaService = MediaService;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = MediaService;
    }
})();
