/* Reading position stays on this device; shared links contain only story/line IDs. */
(function () {
    'use strict';
    const ReaderNavigation = {
        storageKey: 'pcrd_reader_position_v1',
        readyStoryId: null,
        restore: null,
        routeRequest: 0,

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

        readHash() {
            const params = new URLSearchParams(window.location.hash.slice(1));
            return this.parsePosition({ storyId: params.get('story'), line: params.get('line') ?? 0 });
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
                document.getElementById('reader-resume').addEventListener('click', () => this.open(this.readSaved()));
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
            const position = this.readHash();
            if (position) this.open(position);
            else if (window.location.hash) this.setStatus('連結格式無效，請從目錄選擇劇情。');
        },

        updateResume() {
            const button = document.getElementById('reader-resume');
            if (!button) return;
            const saved = this.readSaved();
            const story = saved && this.map.getStoryById(saved.storyId);
            button.disabled = !story;
            button.title = story ? `繼續閱讀：${story.title || saved.storyId}` : '尚無閱讀紀錄';
        },

        beforeSelect() {
            if (!this.map) return;
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
            this.map.currentView = 'list';
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
            if (!this.map || this.readyStoryId !== this.map.activeStoryId) return null;
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
