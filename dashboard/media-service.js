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
         * 播放指定語音，自動暫停前一段音訊並依序嘗試鏡像站點
         * @param {string} voiceName - 語音檔案標籤
         */
        playVoice(voiceName) {
            if (!voiceName) return;
            const cdnList = this.getVoiceCandidates(voiceName);
            if (cdnList.length === 0) return;

            if (this._currentAudio) {
                this._currentAudio.pause();
            }

            const tryPlay = (index) => {
                if (index >= cdnList.length) {
                    console.warn('[MediaService] 該劇情的語音檔在遠端鏡像站尚未同步更新。');
                    return;
                }
                const audio = new Audio(cdnList[index]);
                audio.play().catch(err => {
                    if (err.name === 'NotAllowedError') {
                        console.warn('[MediaService] 語音播放被瀏覽器自動播放政策封鎖。');
                        return;
                    }
                    tryPlay(index + 1);
                });
                this._currentAudio = audio;
            };

            tryPlay(0);
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
