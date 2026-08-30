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
