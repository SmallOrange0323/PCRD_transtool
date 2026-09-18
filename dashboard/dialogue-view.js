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
         * 將對白與大綱中的玩家名稱佔位符統一規格化為「佑樹」
         * 支援 token: {player}, {0}, {player_name}, (O), (o), （O）, （o）
         * @param {string} text - 原始文本
         * @returns {string} 規格化後文本
         */
        normalizePlayerName(text) {
            if (!text || typeof text !== 'string') return text || "";
            return text.replace(/\{player\}|\{0\}|\{player_name\}|\([Oo]\)|（[Oo]）/g, "佑樹");
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
            const normalizedSpeakerNames = (speakerNames || []).map(n => this.normalizePlayerName(n));
            const validSpeakers = normalizedSpeakerNames.filter(n => n !== "旁白" && n !== "【系統】" && !n.includes("【選擇肢】") && !n.includes("【選擇】") && n !== "？？？");
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
                const displayName = this.normalizePlayerName(realName);
                badgeHtmls.push(`
                    <div class="game-chara-avatar-badge" title="${this.escapeHtml(displayName)}" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realName).replace(/"/g, '&quot;')})">
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

            (dialogueList || []).forEach((item, index) => {
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
                    // 全文閱讀模式依官方遊戲規格，不渲染場景切換卡片與背景圖
                    return;
                }

                if (item.type === 'movie') {
                    const movieId = item.movie_id || item.movie;
                    if (movieId) {
                        const cleanMovieId = String(movieId).replace('movie_', '').replace('story_', '');
                        const thumbUrl = `https://redive.estertion.win/card/story/${cleanMovieId}.webp`;
                        html += `
                            <div class="game-dialogue-movie-card">
                                <div class="game-film-frame" onclick="QuestMapModule.openMoviePopup('${cleanMovieId}')" title="點擊播放 1080p 劇情過場動畫">
                                    <div class="film-perfs film-perfs-left">
                                        <span></span><span></span><span></span><span></span>
                                    </div>
                                    <div class="film-screen">
                                        <img src="${thumbUrl}" class="film-thumb" alt="動畫預覽" onerror="this.onerror=null; this.src='https://redive.estertion.win/card/full/${cleanMovieId}.webp';"/>
                                        <div class="film-play-overlay">
                                            <div class="film-play-btn">▶</div>
                                        </div>
                                    </div>
                                    <div class="film-perfs film-perfs-right">
                                        <span></span><span></span><span></span><span></span>
                                    </div>
                                </div>
                                <div class="game-film-caption">
                                    <span class="film-icon">🎬</span> 劇情過場動畫 <span class="film-hd-tag">1080p 繁中</span>
                                </div>
                            </div>
                        `;
                    }
                    return;
                }

                // 顯示文字與角色身份分離：玩家 placeholder 只在 UI 顯示為「佑樹」，
                // avatar / modal / unit_id 查找仍使用官方原始 speaker key（例如 {0}）。
                const rawSpeaker = item.name || "旁白";
                const displaySpeaker = this.normalizePlayerName(rawSpeaker);
                const safeSpeaker = escapeFn(displaySpeaker);
                const normalizedRawWords = this.normalizePlayerName(item.words || "");
                const words = escapeFn(normalizedRawWords)
                    .replace(/\\n/g, "<br>")
                    .replace(/\n/g, "<br>");

                let speakerClass = "";
                let isNarrator = rawSpeaker === "旁白" || rawSpeaker === "【系統】" || rawSpeaker === "？？？";
                let isChoice = rawSpeaker.includes("【選擇肢】") || rawSpeaker.includes("【選擇】");

                if (isNarrator) speakerClass = "role-narrator";
                else if (isChoice) speakerClass = "role-choice";

                const realNameForBtn = (isNarrator || isChoice) ? "" : (resolveRealName ? resolveRealName(rawSpeaker) : rawSpeaker);

                const numUnitId = Number(item.unit_id);
                const hasExplicitUnitId = Number.isInteger(numUnitId) && numUnitId > 0;
                const modalUnitIdArg = hasExplicitUnitId ? `, ${numUnitId}` : "";

                let avatarHtml = "";
                if (!isNarrator && !isChoice) {
                    const realName = realNameForBtn;
                    let avatarContent = "";

                    if (hasExplicitUnitId) {
                        // A. 顯式 Canonical unit_id 絕對優先 (EXPLICIT ALWAYS WINS)
                        // 絕不進行 realityAvatarMap 或 13830* 改寫，直接調用 exact 解析
                        avatarContent = window.AvatarService.getAvatarHtmlByUnitId(numUnitId, realName, speakerAvatars);
                    } else {
                        // B. 無有效顯式 unit_id 之推斷相容路徑 (INFERENCE-ONLY LEGACY COMPATIBILITY)
                        let inferredAvatars = speakerAvatars;
                        const isRealityStory = [2210102, 2211102, 2212103, 2212104, 2213104, 2214101, 2215102].includes(Number(storyId));
                        if (isRealityStory && window.AvatarService && window.AvatarService.realityAvatarMap) {
                            const realityId = window.AvatarService.realityAvatarMap[realName] || window.AvatarService.realityAvatarMap[rawSpeaker];
                            if (realityId) {
                                inferredAvatars = Object.assign({}, speakerAvatars, { [realName]: realityId });
                            }
                        } else if (realName === "貪吃佩可" && String(storyId).startsWith("13830")) {
                            inferredAvatars = Object.assign({}, speakerAvatars, { [realName]: 138331 });
                        }

                        avatarContent = window.AvatarService.getAvatarHtml(realName, inferredAvatars);
                    }

                    avatarHtml = `
                        <div class="game-chara-avatar-wrapper" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realName).replace(/"/g, '&quot;')}${modalUnitIdArg})" style="cursor: pointer;">
                             <div class="game-chara-avatar">
                                 ${avatarContent}
                             </div>
                        </div>
                    `;
                }

                const voiceBtn = item.voice ? `<button type="button" class="dialogue-voice-btn" onclick="event.stopPropagation(); QuestMapModule.playVoice('${item.voice}')" title="播放語音" aria-label="播放語音">🔊</button>` : '';
                const voiceAttr = item.voice ? ` data-voice="${item.voice}"` : '';

                html += `
                    <div class="game-dialogue-line ${speakerClass}" data-dialogue-index="${index}"${voiceAttr} onclick="QuestMapModule.handleDialogueLineClick(${index}, event)">
                        ${avatarHtml}
                        <div class="game-dialogue-content">
                            <div class="game-dialogue-speaker-wrap">
                                <span class="game-dialogue-speaker" onclick="QuestMapModule.showCharaModal(${JSON.stringify(realNameForBtn).replace(/"/g, '&quot;')}${modalUnitIdArg})" style="cursor: pointer;" title="查看角色資料">
                                    ${safeSpeaker}
                                </span>
                                ${voiceBtn}
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
        },

        /**
         * 高亮指定對白行並平滑捲動至可見區域
         * @param {HTMLElement} boardEl - 對白看板容器
         * @param {number} index - 對白索引
         */
        highlightDialogueLine(boardEl, index) {
            if (!boardEl) return;
            this.clearDialogueHighlight(boardEl);
            const lineEl = boardEl.querySelector(`.game-dialogue-line[data-dialogue-index="${index}"]`);
            if (lineEl) {
                lineEl.classList.add('auto-voice-active');
                try {
                    lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                } catch (e) {
                    lineEl.scrollIntoView(true);
                }
            }
        },

        /**
         * 清除看板內所有對白行的高亮樣式
         * @param {HTMLElement} boardEl - 對白看板容器
         */
        clearDialogueHighlight(boardEl) {
            if (!boardEl) return;
            const activeLines = boardEl.querySelectorAll('.game-dialogue-line.auto-voice-active');
            activeLines.forEach(el => el.classList.remove('auto-voice-active'));
        },

        /**
         * 設定指定對白行之 AUTO 起點標記
         * @param {HTMLElement} boardEl - 對白看板容器
         * @param {number} index - 對白索引
         */
        setAutoStartSelection(boardEl, index) {
            if (!boardEl) return;
            this.clearAutoStartSelection(boardEl);
            if (index === null || index === undefined || index < 0) return;
            const lineEl = boardEl.querySelector(`.game-dialogue-line[data-dialogue-index="${index}"]`);
            if (lineEl) {
                lineEl.classList.add('auto-start-selected');
            }
        },

        /**
         * 清除看板內所有對白行之 AUTO 起點標記
         * @param {HTMLElement} boardEl - 對白看板容器
         */
        clearAutoStartSelection(boardEl) {
            if (!boardEl) return;
            const selectedLines = boardEl.querySelectorAll('.game-dialogue-line.auto-start-selected');
            selectedLines.forEach(el => el.classList.remove('auto-start-selected'));
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
