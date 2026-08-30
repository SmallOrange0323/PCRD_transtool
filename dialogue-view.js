console.log("dialogue-view.js loaded");
/**
 * PCRD Data Hub - 劇情對白視圖模組 (DialogueView)
 * 負責劇情對白看板、角色頭像徽章列、特殊節點（插畫、背景、動畫、完結CG）
 * 以及載入中、空資料、載入失敗等各狀態之 HTML 生成與 DOM 渲染。
 * 
 * 本模組為純視圖（View）層，不持有應用程式業務狀態，不發起網路請求與資料庫查詢。
 * 對 AvatarService 與 StoryAssetService 為強制硬依賴（Fail Loudly），嚴禁防禦性靜默回退。
 */

(function() {
    const DialogueView = {
        /**
         * HTML 實體跳脫輔助函式
         * @param {string} str - 原始文字
         * @returns {string} 跳脫後文字
         */
        escapeHtml(str) {
            if (!str) return "";
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        },

        /**
         * 渲染載入中狀態 (Loading Spinner)
         * @param {HTMLElement} containerEl - 對白看板容器元素
         */
        renderLoading(containerEl) {
            if (!containerEl) return;
            containerEl.innerHTML = `
                <div style="text-align: center; color: rgba(255,255,255,0.5); padding: 40px 0; font-size: 0.9rem;">
                    <span class="loading-spinner" style="display: inline-block; animation: spin 1s linear infinite; margin-right: 5px;">🔄</span> 正在載入本地官方繁中對白，請稍候...
                </div>
            `;
        },

        /**
         * 渲染無對白空狀態
         * @param {HTMLElement} containerEl - 對白看板容器元素
         */
        renderEmpty(containerEl) {
            if (!containerEl) return;
            containerEl.innerHTML = `<div style="color: rgba(255,255,255,0.4); text-align: center; font-size: 0.9rem; padding: 20px;">本話無語音對白數據。</div>`;
        },

        /**
         * 渲染對白載入失敗錯誤提示盒與重試按鈕
         * @param {HTMLElement} containerEl - 對白看板容器元素
         * @param {number|string} storyId - 話數 ID
         */
        renderError(containerEl, storyId) {
            if (!containerEl) return;
            containerEl.innerHTML = `
                <div class="dialogue-error-box" style="padding: 15px; border-radius: 8px; background: rgba(230, 73, 73, 0.05); border: 1px dashed rgba(230, 73, 73, 0.2); text-align: left;">
                    <div style="color: #d63031; font-weight: 700; font-size: 0.88rem; margin-bottom: 6px;">⚠️ 台詞文本尚未下載</div>
                    <div style="color: var(--text-primary); font-size: 0.82rem; line-height: 1.5;">
                        本話的對白文本尚未下載到您的電腦中。<br>
                        請在本地專案根目錄中，執行命令下載全部對白：
                    </div>
                    <code style="display: block; margin-top: 8px; background: rgba(0,0,0,0.05); padding: 8px; border-radius: 4px; color: var(--accent-color); font-family: Consolas, monospace; font-size: 0.8rem; border: 1px solid rgba(94, 107, 125, 0.15);">
                        python tools/maintenance/download_stories_tw.py
                    </code>
                    <button onclick="QuestMapModule.loadDialogue(${storyId})" style="margin-top: 10px; padding: 8px 16px; background: var(--accent-color); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85rem;">🔄 重新載入</button>
                </div>
            `;
        },

        /**
         * 渲染上方登場角色徽章列
         * @param {HTMLElement} badgesBarEl - 徽章列容器元素
         * @param {Object} options - 參數選項
         */
        renderSpeakerBadges(badgesBarEl, options) {
            if (!badgesBarEl) return;
            const { speakerNames, speakerAvatars, resolveRealName } = options || {};
            const validSpeakers = (speakerNames || []).filter(n => n !== "旁白" && n !== "【系統】" && !n.includes("【選擇肢】") && !n.includes("【選擇】") && n !== "？？？");
            const playableSpeakers = validSpeakers.filter(name => {
                const realName = resolveRealName ? resolveRealName(name) : name;
                return !!(speakerAvatars && speakerAvatars[realName]);
            });

            if (playableSpeakers.length === 0) {
                badgesBarEl.style.display = "none";
                return;
            }

            badgesBarEl.style.display = "flex";
            const renderedSet = new Set();
            const badgeHtmls = [];

            playableSpeakers.forEach(name => {
                const realName = resolveRealName ? resolveRealName(name) : name;
                if (renderedSet.has(realName)) return;
                renderedSet.add(realName);
                const avatarHtml = window.AvatarService.getAvatarHtml(realName, speakerAvatars);
                badgeHtmls.push(`
                    <div class="game-chara-avatar-badge" title="${realName}" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realName).replace(/"/g, '&quot;')})">
                        ${avatarHtml}
                    </div>
                `);
            });
            badgesBarEl.innerHTML = badgeHtmls.join('');
        },

        /**
         * 生成整篇對白看板之 HTML 字串與首張背景圖 URL
         * @param {Object} options - 參數選項
         * @returns {{ html: string, firstBgUrl: string }}
         */
        generateDialogueHtml(options) {
            const {
                storyId,
                dialogueList,
                speakerAvatars,
                currentStoryObj,
                resolveRealName,
                escapeHtml
            } = options || {};

            const escapeFn = escapeHtml || this.escapeHtml.bind(this);
            let html = "";
            let firstBgUrl = "";

            (dialogueList || []).forEach(item => {
                if (item.type === 'still') {
                    const stillId = item.still_id || item.still;
                    if (stillId && String(stillId).trim().toLowerCase() !== 'end') {
                        const stillImgHtml = window.StoryAssetService.getStillHtml(stillId, 'dialogue-still-img still-clickable', '');
                        html += `
                            <div class="game-dialogue-still-wrap">
                                <div class="game-dialogue-still-label">✨ 劇情插畫</div>
                                <div class="game-dialogue-still" onclick="QuestMapModule.openStillPopup(event)">
                                    ${stillImgHtml}
                                </div>
                            </div>
                        `;
                    }
                    return;
                }

                if (item.type === 'background') {
                    const bgId = item.background_id || item.background || item.bg_id || item.bg;
                    if (bgId) {
                        const bgUrl = `https://redive.estertion.win/bg/jpg/${bgId}.jpg`;
                        if (!firstBgUrl) firstBgUrl = bgUrl;
                        html += `
                            <div class="game-dialogue-bg-change" data-bg="${bgUrl}" style="margin: 12px 0; padding: 8px 12px; font-size: 0.8rem; color: rgba(255,255,255,0.4); text-align: center; border-top: 1px dashed rgba(255,255,255,0.15); border-bottom: 1px dashed rgba(255,255,255,0.15); display: flex; align-items: center; justify-content: center; gap: 6px;">
                                🎬 場景切換：${bgId}
                            </div>
                        `;
                    }
                    return;
                }

                if (item.type === 'movie') {
                    const movieId = item.movie_id || item.movie;
                    if (movieId) {
                        const cleanMovieId = String(movieId).replace('movie_', '');
                        html += `
                            <div class="game-dialogue-movie-wrap" style="
                                margin: 20px 0;
                                padding: 18px;
                                background: rgba(232, 56, 117, 0.08);
                                border: 1px solid rgba(232, 56, 117, 0.2);
                                border-radius: 12px;
                                display: flex;
                                flex-direction: column;
                                align-items: center;
                                justify-content: center;
                                gap: 8px;
                                text-align: center;
                                box-shadow: inset 0 0 10px rgba(232, 56, 117, 0.05);
                            ">
                                <div style="font-size: 1.6rem; animation: pulse 2s infinite;">🎬</div>
                                <div style="font-size: 0.95rem; font-weight: 700; color: var(--accent-color);">過場動畫銜接：movie_${cleanMovieId}</div>
                                <div style="font-size: 0.8rem; color: var(--text-secondary); max-width: 450px; line-height: 1.4;">
                                    此處為遊戲內嵌之劇情動畫。本網頁不直接提供影片播放，您可使用 Python 提取工具解碼本地 USM 影片或在 YouTube/Bilibili 搜尋該動畫 ID 觀看。
                                </div>
                            </div>
                        `;
                    }
                    return;
                }

                const speaker = item.name || "旁白";
                const safeSpeaker = escapeFn(speaker);
                const words = escapeFn(item.words || "")
                    .replace(/\{player\}/g, "佑樹")
                    .replace(/\{0\}/g, "佑樹")
                    .replace(/\\n/g, "<br>")
                    .replace(/\n/g, "<br>");

                let speakerClass = "";
                let isNarrator = speaker === "旁白" || speaker === "【系統】" || speaker === "？？？";
                let isChoice = speaker.includes("【選擇肢】") || speaker.includes("【選擇】");

                if (isNarrator) speakerClass = "role-narrator";
                else if (isChoice) speakerClass = "role-choice";

                const realNameForBtn = (isNarrator || isChoice) ? "" : (resolveRealName ? resolveRealName(speaker) : speaker);

                let avatarHtml = "";
                if (!isNarrator && !isChoice) {
                    const realName = realNameForBtn;
                    let avatarContent = "";

                    let overrideUnitId = item.unit_id;
                    if (realName === "貪吃佩可" && String(storyId).startsWith("13830")) {
                        overrideUnitId = 138331;
                    }

                    if (overrideUnitId) {
                        avatarContent = window.AvatarService.getAvatarHtmlByUnitId(overrideUnitId, realName, speakerAvatars);
                    } else {
                        avatarContent = window.AvatarService.getAvatarHtml(realName, speakerAvatars);
                    }

                    avatarHtml = `
                        <div class="game-chara-avatar-wrapper" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realName).replace(/"/g, '&quot;')})" style="cursor: pointer;">
                             <div class="game-chara-avatar">
                                 ${avatarContent}
                             </div>
                        </div>
                    `;
                }

                const voiceBtn = item.voice ? `<span class="dialogue-voice-btn" onclick="event.stopPropagation(); QuestMapModule.playVoice('${item.voice}')" style="cursor: pointer; margin-left: 6px; font-size: 0.85rem; color: var(--accent-color); transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform='scale(1)'">🔊</span>` : '';

                html += `
                    <div class="game-dialogue-line ${speakerClass}">
                        ${avatarHtml}
                        <div class="game-dialogue-content">
                            <div class="game-dialogue-speaker" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realNameForBtn).replace(/"/g, '&quot;')})" style="cursor: pointer; display: inline-block;">
                                ${safeSpeaker}${voiceBtn}
                            </div>
                            <div class="game-dialogue-text">${words}</div>
                        </div>
                    </div>
                `;
            });

            // 如果該話擁有 CG 插畫且對白 JSON 內沒有 special still 節點，則自動在末端追加完結 CG 圖片
            if (currentStoryObj && (currentStoryObj.still_id || currentStoryObj.bg_id)) {
                const hasStillInList = (dialogueList || []).some(item => item.type === 'still');
                if (!hasStillInList) {
                    const bottomStillImgHtml = currentStoryObj.still_id
                        ? window.StoryAssetService.getStillHtml(currentStoryObj.still_id, 'dialogue-still-img still-clickable', '')
                        : window.StoryAssetService.getBackgroundHtml(currentStoryObj.bg_id, 'dialogue-still-img still-clickable', '');
                    html += `
                        <div class="game-dialogue-still-wrap" style="margin-top: 20px; margin-bottom: 10px;">
                            <div class="game-dialogue-still-label">✨ 劇情插畫</div>
                            <div class="game-dialogue-still" onclick="QuestMapModule.openStillPopup(event)">
                                ${bottomStillImgHtml}
                            </div>
                        </div>
                    `;
                }
            }

            return { html, firstBgUrl };
        },

        /**
         * 渲染完整對白看板與背景特效
         * @param {Object} options - 參數選項
         */
        renderDialogue(options) {
            const {
                boardEl,
                badgesBarEl,
                cinemaPanelEl,
                storyId,
                dialogueList,
                speakerNames,
                speakerAvatars,
                currentStoryObj,
                resolveRealName,
                escapeHtml
            } = options || {};

            // 1. 渲染上方角色徽章列
            this.renderSpeakerBadges(badgesBarEl, { speakerNames, speakerAvatars, resolveRealName });

            // 2. 生成對白 HTML 與首張背景圖 URL
            const { html, firstBgUrl } = this.generateDialogueHtml({
                storyId,
                dialogueList,
                speakerAvatars,
                currentStoryObj,
                resolveRealName,
                escapeHtml
            });

            // 3. 寫入看板並將捲軸歸零
            if (boardEl) {
                boardEl.innerHTML = html;
                boardEl.scrollTop = 0;
            }

            // 4. 切換劇院看板背景
            if (cinemaPanelEl) {
                if (firstBgUrl) {
                    cinemaPanelEl.style.backgroundImage = `url('${firstBgUrl}')`;
                } else {
                    cinemaPanelEl.style.backgroundImage = 'none';
                }
                cinemaPanelEl.style.backgroundSize = 'cover';
                cinemaPanelEl.style.backgroundPosition = 'center';
            }
        }
    };

    // 掛載至全域環境
    if (typeof window !== 'undefined') {
        window.DialogueView = DialogueView;
    } else if (typeof global !== 'undefined') {
        global.DialogueView = DialogueView;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = DialogueView;
    }
})();
