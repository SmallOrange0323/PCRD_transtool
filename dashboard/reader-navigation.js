/* Reading position stays on this device; shared links contain only story/line IDs. */
(function () {
    'use strict';
    const ReaderNavigation = {
        storageKey: 'pcrd_reader_position_v1',
        readyStoryId: null,
        restore: null,
        routeRequest: 0,

        sessionPromptKey: 'pcrd_reader_prompt_seen_v1',

        parsePosition(value) {
            if (!value || !/^\d{1,9}$/.test(String(value.storyId))) return null;
            const storyId = Number(value.storyId);
            const line = Number(value.line ?? 0);
            if (storyId <= 0 || !Number.isInteger(line) || line < 0 || line > 100000) return null;
            return { storyId, line };
        },

        readSaved() {
            try { return this.parsePosition(JSON.parse(localStorage.getItem(this.storageKey))); }
            catch (_) { return null; }
        },

        getResumeTarget() {
            const saved = this.readSaved();
            if (!saved || !this.map) return null;
            const story = this.map.getStoryById(saved.storyId);
            if (!story) return null;
            return { position: saved, story };
        },

        formatResumeLabel(story) {
            if (!story) return '';
            const chapter = (story.chapter || '').trim();
            const title = (story.title || '').trim();
            const type = story.type;
            const isEvent = story.isEvent;

            // 1. 角色劇情：如 "優衣 第6話" -> "優衣・角色劇情 第6話"
            if (type === 'chara') {
                const m = chapter.match(/^(.*?)\s*第(\d+)話/);
                if (m) {
                    return `${m[1].trim()}・角色劇情 第${m[2]}話`;
                }
                const baseName = story.charaName ? `${story.charaName}・角色劇情` : '角色劇情';
                return chapter ? `${baseName} ${chapter}` : baseName;
            }

            // 2. 活動劇情：如 "初音的禮物大作戰 第4話" -> "活動：初音的禮物大作戰・第4話"
            if (isEvent || type === 'event') {
                const m = chapter.match(/^(.*?)\s*第(\d+)話/);
                if (m) {
                    return `活動：${m[1].trim()}・第${m[2]}話`;
                }
                return `活動：${chapter || title || '活動劇情'}`;
            }

            // 3. 主線劇情：
            // 第2部、第3部必須保留部別：如 "第2部 第1章 第1話" -> "主線劇情 第2部・第1章・第1話"
            // 第1部若未明寫第1部：如 "第15章 第3話" -> "主線劇情 第15章・第3話"（不硬補第1部）
            if (type === 'main') {
                const mPart = chapter.match(/^(第[23]部)\s*(第\d+章)\s*(第\d+話)/);
                if (mPart) {
                    return `主線劇情 ${mPart[1]}・${mPart[2]}・${mPart[3]}`;
                }
                const mChapter = chapter.match(/^(?:第1部\s*)?(第\d+章)\s*(第\d+話)/);
                if (mChapter) {
                    return `主線劇情 ${mChapter[1]}・${mChapter[2]}`;
                }
                if (chapter.includes('序章')) {
                    return `主線劇情 序章${title ? `・${title}` : ''}`;
                }
                if (chapter.startsWith('幕間')) {
                    return `主線劇情 ${chapter}`;
                }
                return `主線劇情 ${chapter || title || ''}`.trim();
            }

            // 4. 公會劇情：如 "美食殿堂 第1話" -> "公會：美食殿堂・第1話"
            if (type === 'guild') {
                const m = chapter.match(/^(.*?)\s*第(\d+)話/);
                if (m) {
                    return `公會：${m[1].trim()}・第${m[2]}話`;
                }
                return `公會劇情 ${chapter || title || ''}`.trim();
            }

            // 5. 額外 / 露娜塔等其他類型
            if (chapter) return chapter;
            if (title) return title;
            return `劇情 ${story.id || ''}`.trim();
        },

        async resumeToLastStory() {
            this.dismissPrompt();
            const target = this.getResumeTarget();
            if (target) {
                await this.open(target.position);
            }
        },

        dismissPrompt() {
            try { sessionStorage.setItem(this.sessionPromptKey, '1'); } catch (_) {}
            const toast = document.getElementById('reader-resume-toast');
            if (toast) toast.remove();
        },

        showResumePrompt(target) {
            if (!target || !target.story) return;
            // 檢查本 session 是否已顯示過（seen flag）
            try {
                if (sessionStorage.getItem(this.sessionPromptKey) === '1') return;
            } catch (_) {}

            const label = this.formatResumeLabel(target.story);
            if (!label) return;

            // 成功顯示前立即記錄 seen flag，確保本 session 不再主動重複顯示
            try { sessionStorage.setItem(this.sessionPromptKey, '1'); } catch (_) {}

            // 若目前已有 toast，先移除舊的
            const existing = document.getElementById('reader-resume-toast');
            if (existing) existing.remove();

            const toast = document.createElement('div');
            toast.id = 'reader-resume-toast';
            toast.className = 'reader-resume-toast';
            toast.setAttribute('role', 'region');
            toast.setAttribute('aria-label', '上次閱讀提醒');

            const header = document.createElement('div');
            header.className = 'reader-resume-toast-header';
            header.innerHTML = `<span>📖 上次閱讀</span>`;

            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className = 'reader-resume-toast-close';
            closeBtn.setAttribute('aria-label', '關閉提醒');
            closeBtn.textContent = '×';
            closeBtn.addEventListener('click', () => this.dismissPrompt());
            header.appendChild(closeBtn);

            const body = document.createElement('div');
            body.className = 'reader-resume-toast-body';
            body.textContent = label;

            const actions = document.createElement('div');
            actions.className = 'reader-resume-toast-actions';

            const dismissBtn = document.createElement('button');
            dismissBtn.type = 'button';
            dismissBtn.className = 'reader-resume-toast-btn-dismiss';
            dismissBtn.textContent = '關閉';
            dismissBtn.addEventListener('click', () => this.dismissPrompt());

            const resumeBtn = document.createElement('button');
            resumeBtn.type = 'button';
            resumeBtn.className = 'reader-resume-toast-btn-resume';
            resumeBtn.textContent = '繼續閱讀';
            resumeBtn.addEventListener('click', () => this.resumeToLastStory());

            actions.appendChild(dismissBtn);
            actions.appendChild(resumeBtn);

            toast.appendChild(header);
            toast.appendChild(body);
            toast.appendChild(actions);

            document.body.appendChild(toast);
        },

        readHash() {
            const params = new URLSearchParams(window.location.hash.slice(1));
            return this.parsePosition({ storyId: params.get('story'), line: params.get('line') ?? 0 });
        },

        readInitialDeepLink() {
            if (!window.location.hash) return null;
            const params = new URLSearchParams(window.location.hash.slice(1));
            if (!params.has('line')) return null;
            return this.readHash();
        },

        setStatus(message) {
            const status = document.getElementById('reader-navigation-status');
            if (status) status.textContent = message;
        },

        init(map) {
            if (this.map) return;
            this.map = map;
            const host = document.querySelector('.nav-right');
            if (host) {
                host.innerHTML = `<button type="button" id="reader-resume" class="reader-nav-button">繼續閱讀</button>
                    <button type="button" id="reader-share" class="reader-nav-button" disabled>分享本話</button>`;
                document.getElementById('reader-resume').addEventListener('click', () => this.resumeToLastStory());
                document.getElementById('reader-share').addEventListener('click', () => this.share());
            }
            const status = document.createElement('p');
            status.id = 'reader-navigation-status';
            status.className = 'reader-navigation-status';
            status.setAttribute('role', 'status');
            document.querySelector('main').prepend(status);
            this.updateResume();
            document.addEventListener('scroll', () => {
                clearTimeout(this.scrollTimer);
                this.scrollTimer = setTimeout(() => this.savePosition(), 250);
            }, { capture: true, passive: true });
            window.addEventListener('pagehide', () => this.savePosition());
            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'hidden') this.savePosition();
            });
            window.addEventListener('hashchange', () => {
                if (!window.location.hash) {
                    this.routeRequest++;
                    this.restore = null;
                    map.exitReader();
                } else {
                    const position = this.readHash();
                    if (position) this.open(position);
                    else this.setStatus('連結格式無效，請從目錄選擇劇情。');
                }
            });

            // 初始載入路由判斷：
            // A. Explicit shared deep-link: 必須包含明確 'line' 參數（如 #story=...&line=0 或 line=42），
            //    視為使用者明確點擊分享連結進入，直接導向該話並抑制 resume prompt。
            // B. Internal reader route: 若僅有 #story=...（無 line 參數），視為上一次站內瀏覽殘留之 stale hash，
            //    絕不自動 open，使用 replaceState 清除 hash 保持 landing page，並在有 saved progress 時提示 resume prompt。
            // C. 無效 hash: 提示連結格式無效，不自動跳轉，有 saved progress 仍可提示 resume prompt。
            // D. 無 hash: landing page，有 saved progress 則提示 resume prompt。
            const initialDeepLink = this.readInitialDeepLink();
            if (initialDeepLink) {
                this.open(initialDeepLink);
            } else {
                const parsedAny = this.readHash();
                if (parsedAny) {
                    // 屬於情境 B：帶有 story 但無 line 參數的 stale internal route，清除 hash 保持 landing page
                    try {
                        const url = new URL(window.location.href);
                        url.hash = '';
                        window.history.replaceState(window.history.state, '', url);
                    } catch (_) {}
                } else if (window.location.hash) {
                    // 屬於情境 C：無法解析為 story 的無效 hash
                    this.setStatus('連結格式無效，請從目錄選擇劇情。');
                }

                const target = this.getResumeTarget();
                if (target && target.position.storyId !== this.map.activeStoryId) {
                    this.showResumePrompt(target);
                }
            }
        },

        updateResume() {
            const button = document.getElementById('reader-resume');
            if (!button) return;
            const target = this.getResumeTarget();
            button.disabled = !target;
            if (target) {
                const label = this.formatResumeLabel(target.story);
                button.title = label ? `上次閱讀：${label}` : `上次閱讀：${target.position.storyId}`;
            } else {
                button.title = '尚無閱讀紀錄';
            }
        },

        beforeSelect() {
            if (!this.map) return;
            this.dismissPrompt();
            this.savePosition();
            this.readyStoryId = null;
        },

        selected(storyId) {
            if (!this.map) return;
            if (this.restore && this.restore.storyId !== storyId) this.restore = null;
            const current = this.readHash();
            if (!current || current.storyId !== storyId) {
                const url = new URL(window.location.href);
                url.hash = `story=${storyId}`;
                window.history.pushState(null, '', url);
            }
            const button = document.getElementById('reader-share');
            if (button) button.disabled = false;
            this.setStatus('');
            this.updateResume();
        },

        left() {
            if (!this.map) return;
            this.savePosition();
            this.readyStoryId = null;
            this.restore = null;
            this.routeRequest++;
            const button = document.getElementById('reader-share');
            if (button) button.disabled = true;
            if (window.location.hash) {
                const url = new URL(window.location.href);
                url.hash = '';
                window.history.pushState(null, '', url);
            }
            this.updateResume();
        },

        async open(position) {
            if (!position || !this.map.getStoryById(position.storyId)) {
                this.setStatus('此話目前未收錄，請從目錄選擇其他劇情。');
                return;
            }
            const request = ++this.routeRequest;
            while (this.map.isRendering) {
                await new Promise(resolve => setTimeout(resolve, 50));
                if (request !== this.routeRequest) return;
            }
            this.savePosition();
            this.restore = position;
            if (typeof window.switchTab === 'function') window.switchTab('map');
            if (this.map.activeStoryId === position.storyId && this.readyStoryId === position.storyId) {
                this.dialogueReady(position.storyId);
                return;
            }
            this.readyStoryId = null;
            await this.map.jumpToStory(position.storyId);
        },

        dialogueReady(storyId) {
            if (!this.map) return;
            const token = this.map._storyRenderToken;
            // Wait until the reader's initial scroll-to-top has finished.
            requestAnimationFrame(() => requestAnimationFrame(() => {
                if (this.map.activeStoryId !== storyId || this.map._storyRenderToken !== token) return;
                const board = document.getElementById('dialogue-board');
                const lines = board && [...board.querySelectorAll('[data-dialogue-index]')];
                if (!lines) return;
                const pending = this.restore;
                if (pending && pending.storyId === storyId && lines.length) {
                    const index = Math.min(pending.line, lines.length - 1);
                    const line = board.querySelector(`[data-dialogue-index="${index}"]`) || lines[0];
                    line.scrollIntoView({ block: 'start', behavior: 'auto' });
                    this.restore = null;
                    this.setStatus(`已回到上次指定的位置（第 ${index + 1} 段），可直接繼續閱讀。`);
                }
                if (!lines.length) this.restore = null;
                this.readyStoryId = storyId;
                this.savePosition();
            }));
        },

        currentPosition() {
            if (!this.map || !this.readyStoryId || this.readyStoryId !== this.map.activeStoryId) return null;
            const tab = document.getElementById('map-tab');
            if (!tab?.classList.contains('active')) return null;
            const board = document.getElementById('dialogue-board');
            const lines = board && [...board.querySelectorAll('[data-dialogue-index]')];
            if (!lines) return null;
            if (!lines.length) return { storyId: this.readyStoryId, line: 0 };
            const top = Math.max(90, board.getBoundingClientRect().top);
            const line = lines.find(el => el.getBoundingClientRect().bottom > top) || lines[lines.length - 1];
            return { storyId: this.readyStoryId, line: Number(line.dataset.dialogueIndex) };
        },

        savePosition() {
            const position = this.currentPosition();
            if (!position) return;
            try {
                localStorage.setItem(this.storageKey, JSON.stringify(position));
                this.updateResume();
            } catch (_) { /* Reading and sharing still work without storage. */ }
        },

        async share() {
            const storyId = this.map.activeStoryId;
            if (!storyId) return;
            const position = this.currentPosition() || { storyId, line: 0 };
            const url = new URL(window.location.href);
            url.hash = `story=${position.storyId}&line=${position.line}`;
            try {
                await navigator.clipboard.writeText(url.href);
                this.setStatus('已複製本話連結，可貼給朋友直接閱讀。');
            } catch (_) {
                // A selectable field also works in browsers without clipboard permission.
                const status = document.getElementById('reader-navigation-status');
                if (!status) return;
                status.textContent = '請複製連結：';
                const input = document.createElement('input');
                input.type = 'text';
                input.readOnly = true;
                input.value = url.href;
                input.setAttribute('aria-label', '本話分享連結');
                status.appendChild(input);
                input.focus();
                input.select();
            }
        }
    };
    window.ReaderNavigation = ReaderNavigation;
})();
