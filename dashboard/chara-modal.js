console.log("chara-modal.js loaded");
/**
 * PCRD Data Hub - 角色檔案彈窗模組 (CharaModalView)
 * 負責角色個人 Profile 檔案彈窗 (Modal) 之 DOM 單例管理、HTML 組裝與顯示。
 * 本模組為純視圖模組，不直接操作資料庫 SQL 查詢或應用程式導航路由。
 */

window.CharaModalView = {
    /**
     * 取得或建立角色彈窗 DOM 容器單例
     * @returns {HTMLElement} 彈窗 DOM 元素
     */
    getCharaModal() {
        let modalEl = document.getElementById('game-chara-modal');
        if (!modalEl) {
            modalEl = document.createElement('div');
            modalEl.id = 'game-chara-modal';
            modalEl.className = 'game-modal-overlay';
            modalEl.onclick = function(event) {
                if (event.target === modalEl) {
                    modalEl.classList.remove('active');
                }
            };
            // 支援 Escape 鍵關閉
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    const m = document.getElementById('game-chara-modal');
                    if (m && m.classList.contains('active')) {
                        m.classList.remove('active');
                    }
                }
            });
            document.body.appendChild(modalEl);
        }
        return modalEl;
    },

    /**
     * 渲染登場話數按鈕列表 HTML
     * @param {number[]} appearances - 登場話數 ID 陣列
     * @param {Function} resolveStoryLabel - 話數標籤轉換函式 (storyId) => string
     * @returns {string} 登場話數按鈕 HTML 字串
     */
    renderAppearancesHtml(appearances, resolveStoryLabel) {
        if (!appearances || appearances.length === 0) {
            return `<div style="color: var(--text-secondary); font-size: 0.85rem; font-style: italic;">暫無登場話數統計數據。</div>`;
        }
        return appearances.map(storyId => {
            let label = `ID: ${storyId}`;
            if (resolveStoryLabel) {
                label = resolveStoryLabel(storyId) || label;
            }
            return `<button class="chara-appear-btn" onclick="QuestMapModule.jumpToStory(${storyId}, 'game-chara-modal')" style="background: rgba(232,56,117,0.07); border: 1px solid rgba(232,56,117,0.2); border-radius: 8px; padding: 6px 12px; color: var(--accent-color); cursor: pointer; font-size: 0.82rem; font-weight: 600; transition: all 0.2s; display: inline-block;">${label}</button>`;
        }).join('');
    },

    /**
     * 渲染角色基本資料設定表格 HTML
     * @param {Object|null} profile - 角色 Profile 資料物件
     * @returns {string} 基本資料 HTML 字串
     */
    renderProfileDetailsHtml(profile) {
        if (!profile) {
            return `
                <div style="flex: 1; min-width: 200px; display: flex; flex-direction: column; justify-content: center;">
                    <div style="color: var(--text-secondary); font-size: 0.9rem; font-style: italic; border: 1px dashed rgba(232, 56, 117, 0.2); padding: 15px; border-radius: 8px; background: rgba(232, 56, 117, 0.03);">
                        ℹ️ 此角色為劇中登場人物或 NPC，尚無設定集數據。
                    </div>
                </div>
            `;
        }

        const guild = profile.guild || "未知";
        const race = profile.race || "未知";
        const rawAge = profile.age || "";
        const age = rawAge ? `${rawAge}歲` : "未知";
        const rawHeight = profile.height || "";
        const height = rawHeight ? `${rawHeight}cm` : "未知";
        const rawWeight = profile.weight || "";
        const weight = rawWeight ? `${rawWeight}kg` : "未知";
        const birth = (profile.birth_month) ? `${profile.birth_month}月${profile.birth_day}日` : "未知";
        const cv = profile.voice || "未知";

        return `
            <div style="flex: 1; min-width: 200px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.88rem; color: var(--text-primary);">
                    <tr>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600; width: 60px;">公會：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${guild}</td>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600; width: 60px;">種族：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${race}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">年齡：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${age}</td>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">生日：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${birth}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">身高：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${height}</td>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">體重：</td>
                        <td style="padding: 4px 0; color: var(--text-primary); font-weight: 500;">${weight}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: var(--accent-color); font-weight: 600;">聲優：</td>
                        <td colspan="3" style="padding: 4px 0; color: var(--accent-color); font-weight: bold;">${cv}</td>
                    </tr>
                </table>
            </div>
        `;
    },

    /**
     * 渲染角色自我介紹與標語 HTML
     * @param {Object|null} profile - 角色 Profile 資料物件
     * @param {Function} escapeHtml - HTML 轉義函式
     * @returns {string} 自我介紹 HTML 字串
     */
    renderProfileBioHtml(profile, escapeHtml) {
        if (!profile) return "";
        const catchCopy = profile.catch_copy || "";
        const selfText = escapeHtml 
            ? escapeHtml(profile.self_text || "暫無自我介紹。").replace(/\\n/g, '<br>')
            : (profile.self_text || "暫無自我介紹。").replace(/\\n/g, '<br>');

        return `
            ${catchCopy ? `<div style="font-style: italic; color: var(--accent-color); font-size: 0.9rem; margin-bottom: 10px; text-align: left;">「${catchCopy}」</div>` : ''}
            <div style="background: rgba(94, 107, 125, 0.04); padding: 12px; border-radius: 8px; border: 1px solid rgba(232, 56, 117, 0.08); font-size: 0.85rem; line-height: 1.6; color: var(--text-primary); margin-bottom: 15px; text-align: left;">
                ${selfText}
            </div>
        `;
    },

    /**
     * 渲染並開啟角色 Profile 彈窗
     * @param {Object} options - 依賴注入選項
     * @param {string} options.realCharaName - 角色真實名稱
     * @param {Object|null} options.profile - 角色 Profile 資料
     * @param {number[]} options.appearances - 登場話數 ID 陣列
     * @param {Object} options.speakerAvatars - 角色頭像映射
     * @param {Object} options.avatarService - AvatarService 實體
     * @param {Function} options.resolveStoryLabel - 話數標籤轉換函式
     * @param {Function} options.escapeHtml - HTML 轉義函式
     */
    renderModal(options) {
        const {
            realCharaName,
            profile,
            appearances,
            speakerAvatars,
            avatarService,
            resolveStoryLabel,
            escapeHtml
        } = options || {};

        const modalEl = this.getCharaModal();
        const appListHtml = this.renderAppearancesHtml(appearances, resolveStoryLabel);
        const detailsHtml = this.renderProfileDetailsHtml(profile);
        const bioHtml = this.renderProfileBioHtml(profile, escapeHtml);
        const avatarHtml = avatarService 
            ? avatarService.getAvatarHtml(realCharaName, speakerAvatars)
            : "";

        modalEl.innerHTML = `
            <div class="game-modal-content" style="max-height: 85vh; overflow-y: auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(94, 107, 125, 0.1); padding-bottom: 12px; margin-bottom: 15px;">
                    <h3 style="margin: 0; color: var(--accent-color); font-size: 1.25rem;">🔍 角色檔案：${realCharaName}</h3>
                    <span class="game-modal-close-btn" onclick="document.getElementById('game-chara-modal').classList.remove('active')" style="cursor: pointer; font-size: 1.5rem; color: var(--text-secondary); transition: transform 0.2s;"
                           onmouseover="this.style.transform='rotate(90deg)'" onmouseout="this.style.transform='none'">&times;</span>
                </div>

                <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 15px;">
                    <div style="width: 100px; height: 100px; border-radius: 12px; overflow: hidden; border: 2px solid rgba(232, 56, 117, 0.15); background: #ffffff; display: flex; align-items: center; justify-content: center; padding: 0;">
                        ${avatarHtml}
                    </div>
                    ${detailsHtml}
                </div>

                ${bioHtml}

                <div style="border-top: 1px solid rgba(94, 107, 125, 0.1); padding-top: 15px;">
                    <h4 style="margin: 0 0 10px 0; color: var(--text-primary); font-size: 0.95rem;">📖 登場話數 (點擊直接跳轉放映)：</h4>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; max-height: 150px; overflow-y: auto; padding: 5px;">
                        ${appListHtml}
                    </div>
                </div>
            </div>
        `;

        modalEl.classList.add('active');
    }
};
