console.log("db.js loaded");
try { localStorage.setItem('pcr_region', 'tw'); } catch (_) { /* Storage is optional. */ }
/**
 * PCR 數據導航站 - DB 引擎
 * 負責下載、快取與查詢 SQLite 資料庫
 */

window.PCRDatabase = {
    db: null,
    currentRegion: 'tw',
    cacheWarning: '',

    async matchesRelease(buffer, size, version) {
        if (!buffer || (size > 0 && buffer.byteLength !== size)) return false;
        // Published versions contain the first 12 SHA-256 characters.
        const match = /^hash_([a-f0-9]{12})$/.exec(version || '');
        if (match) {
            if (!globalThis.crypto || !globalThis.crypto.subtle) {
                throw new Error('無法驗證資料庫版本，請使用 HTTPS 或 localhost 開啟網站。');
            }
            const digest = await globalThis.crypto.subtle.digest('SHA-256', buffer);
            const hash = Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('');
            return hash.startsWith(match[1]);
        }
        return true;
    },

    openVerifiedDatabase(SQL, buffer) {
        try {
            this.db = new SQL.Database(new Uint8Array(buffer));
            if (this.verifyDatabase()) return true;
        } catch (error) {
            console.warn('[PCRDatabase] 無法開啟資料庫:', error);
        }
        if (this.db && typeof this.db.close === 'function') this.db.close();
        this.db = null;
        return false;
    },

    /**
     * 切換區域 (目前僅支援台服，強制定向為 tw)
     */
    async switchRegion(region) {
        localStorage.setItem('pcr_region', 'tw');
        location.reload();
    },

    /**
     * 驗證資料庫結構完整性
     */
    verifyDatabase() {
        if (!this.db) return false;
        try {
            // 測試查詢 story_detail 表是否存在且有資料
            const res = this.runQuery("SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table' AND name='story_detail'");
            if (res && res.length > 0 && res[0].cnt > 0) {
                // 進一步檢查是否包含主線劇情資料
                const rows = this.runQuery("SELECT COUNT(*) as cnt FROM story_detail");
                return rows && rows.length > 0 && rows[0].cnt > 0;
            }
            return false;
        } catch (e) {
            console.error("[PCRDatabase] 驗證資料庫結構出錯:", e);
            return false;
        }
    },

    /**
     * 初始化資料庫
     * @param {Function} onProgress 進度回調 (message, percent)
     */
    async initDatabase(onProgress) {
        if (this.db) return this.db;

        const dbKey = `pcr_db_${this.currentRegion}`;
        const localPath = `./redive_${this.currentRegion}.db`;
        this.cacheWarning = '';

        try {
            // 1. 初始化 SQL 引擎 (WebAssembly)
            if (onProgress) onProgress('正在初始化 SQL 引擎...', 10);
            
            if (typeof initSqlJs === 'undefined') {
                throw new Error("無法載入 SQL 引擎元件 (initSqlJs 未定義)。請嘗試按 Ctrl+F5 強制重新整理頁面。");
            }

            const sqlPromise = initSqlJs({
                locateFile: file => `${file}`
            });

            let timer;
            const timeoutPromise = new Promise((_, reject) => {
                timer = setTimeout(() => reject(new Error('初始化 SQL 引擎逾時，請重新載入。')), 10000);
            });
            const SQL = await Promise.race([sqlPromise, timeoutPromise]).finally(() => clearTimeout(timer));

            // 從 data/db_info.json 一次性取得 size 與 db_version（合併為單一請求）
            let size = 0;
            let latestVersion = "";
            try {
                const infoRes = await fetch(`data/db_info.json?v=${Date.now()}`, { signal: AbortSignal.timeout(10000) });
                if (infoRes.ok) {
                    const info = await infoRes.json();
                    size = parseInt(info[`${this.currentRegion}_size`], 10) || 0;
                    latestVersion = info.db_version || "";
                    console.log(`[PCRDatabase] db_info: size=${size}, version=${latestVersion}`);
                }
            } catch (e) {
                console.warn("[PCRDatabase] 讀取 db_info.json 失敗，改用 HEAD 備用機制:", e);
            }

            // 若 db_info 無法取得 size，降級使用 HEAD 請求
            if (size <= 0) {
                try {
                    const headRes = await fetch(localPath, { method: 'HEAD', signal: AbortSignal.timeout(10000) });
                    if (headRes.ok) {
                        const cl = headRes.headers.get('content-length');
                        if (cl) size = parseInt(cl, 10);
                    }
                } catch (e) {
                    console.warn(`[PCRDatabase] HEAD ${localPath} failed...`, e);
                }
            }

            // Version and bytes live in one IDB record. Never erase the previous
            // release until the replacement has downloaded and passed validation.
            const cached = await this.loadFromIDB(dbKey);
            const record = cached && cached.format === 2 ? cached : null;
            const legacyHashCache = !record && /^hash_[a-f0-9]{12}$/.test(latestVersion);
            const cacheBytes = record ? record.buffer : cached;
            const sameVersion = record && latestVersion && record.version === latestVersion;
            if ((sameVersion || legacyHashCache) &&
                await this.matchesRelease(cacheBytes, size, latestVersion) &&
                this.openVerifiedDatabase(SQL, cacheBytes)) {
                this.dbVersion = latestVersion;
                if (onProgress) onProgress('已載入快取資料庫', 100);
                return this.db;
            }

            // Only use the database shipped with this site. A third-party mirror
            // may be a different release, even when its schema and size match.
            if (onProgress) onProgress('正在下載網站資料庫...', 20);
            const dbData = await this.downloadDB(`${localPath}?v=${encodeURIComponent(latestVersion || 'current')}`, pct => {
                if (onProgress) onProgress(`正在下載資料庫... ${pct}%`, 20 + pct * 0.7);
            });
            if (!await this.matchesRelease(dbData, size, latestVersion)) {
                throw new Error('資料庫與網站版本不一致，可能正在更新，請稍後重新載入。');
            }
            if (!this.openVerifiedDatabase(SQL, dbData)) {
                throw new Error('載入的資料庫格式有誤，找不到劇情資料表。');
            }
            this.dbVersion = latestVersion;
            try {
                await this.saveToIDB(dbKey, { format: 2, version: latestVersion, buffer: dbData });
            } catch (error) {
                this.cacheWarning = '無法保存資料庫快取，本次仍可閱讀；下次開啟會重新下載。';
                console.warn('[PCRDatabase]', this.cacheWarning, error);
            }
            if (onProgress) onProgress('資料庫已就緒', 100);
            return this.db;
        } catch (error) {
            console.error('Database Init Error:', error);
            if (onProgress) onProgress(`載入失敗: ${error.message}`, 0);
            throw error;
        }
    },


    /**
     * 載入特定的資料庫（專供比對使用，不覆蓋主 db）
     */
    async loadSpecificDatabase(type, onProgress) {
        const dbKey = `pcr_db_${type}`;
        const localPath = `./redive_${type}.db`;
        const sizeKey = `pcr_db_size_${type}`;

        try {
            if (onProgress) onProgress('正在初始化 SQL 引擎...', 10);
            
            if (typeof initSqlJs === 'undefined') {
                throw new Error("無法載入 SQL 引擎元件 (initSqlJs 未定義)。");
            }

            const SQL = await initSqlJs({
                locateFile: file => `${file}`
            });

            // 獲取檔案大小
            let size = 0;
            try {
                const headRes = await fetch(localPath, { method: 'HEAD' });
                if (headRes.ok) {
                    const cl = headRes.headers.get('content-length');
                    if (cl) size = parseInt(cl, 10);
                }
            } catch (e) {
                console.warn(`[PCRDatabase] HEAD ${localPath} failed.`, e);
            }

            const cachedSize = localStorage.getItem(sizeKey);
            let forceReload = false;
            if (size > 0 && String(size) !== String(cachedSize)) {
                console.log(`[PCRDatabase] Size mismatch for ${type}. Force reload.`);
                forceReload = true;
                await this.removeFromIDB(dbKey);
            }

            // 嘗試載入快取
            let cachedDB = null;
            if (!forceReload) {
                cachedDB = await this.loadFromIDB(dbKey);
            }

            if (cachedDB) {
                if (onProgress) onProgress(`正在載入本地 ${type.toUpperCase()} 快取...`, 50);
                const specificDb = new SQL.Database(new Uint8Array(cachedDB.format === 2 ? cachedDB.buffer : cachedDB));
                console.log(`[PCRDatabase] Loaded specific DB: ${type} from IndexedDB`);
                return specificDb;
            }

            // 下載檔案
            if (onProgress) onProgress(`正在下載 ${type.toUpperCase()} 資料庫...`, 20);
            const dbData = await this.downloadDB(localPath, (pct) => {
                if (onProgress) onProgress(`正在下載 ${type.toUpperCase()} 資料庫... ${pct}%`, 20 + (pct * 0.7));
            });

            if (dbData) {
                const specificDb = new SQL.Database(new Uint8Array(dbData));
                await this.saveToIDB(dbKey, dbData);
                const finalSize = size > 0 ? size : dbData.byteLength;
                localStorage.setItem(sizeKey, finalSize);
                console.log(`[PCRDatabase] Successfully loaded specific DB: ${type}`);
                return specificDb;
            }

            throw new Error(`無法取得 ${type} 資料庫數據`);
        } catch (error) {
            console.error(`loadSpecificDatabase Error (${type}):`, error);
            if (onProgress) onProgress(`載入 ${type} 失敗: ${error.message}`, 0);
            throw error;
        }
    },



    /**
     * 下載資料庫文件（帶進度回調）
     */
    async downloadDB(dbUrl, onProgress) {
        try {
            console.log(`正在嘗試從 ${dbUrl} 取得資料庫...`);
            const response = await fetch(dbUrl, { cache: 'no-cache', signal: AbortSignal.timeout(60000) });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const contentLength = response.headers.get('content-length');
            const total = parseInt(contentLength, 10);
            let loaded = 0;

            const reader = response.body.getReader();
            const chunks = [];

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                chunks.push(value);
                loaded += value.length;
                if (total && onProgress) {
                    onProgress(Math.round((loaded / total) * 100));
                }
            }

            const allChunks = new Uint8Array(loaded);
            let position = 0;
            for (const chunk of chunks) {
                allChunks.set(chunk, position);
                position += chunk.length;
            }
            console.log(`成功從 ${dbUrl} 載入資料庫`);
            return allChunks.buffer;
        } catch (e) {
            console.warn(`從 ${dbUrl} 下載失敗:`, e);
            throw e;
        }
    },

    /**
     * 執行 SQL 查詢並回傳物件陣列
     */
    runQuery(sql, params = []) {
        if (!this.db) throw new Error('資料庫尚未初始化');
        try {
            const stmt = this.db.prepare(sql);
            stmt.bind(params);
            const results = [];
            while (stmt.step()) {
                results.push(stmt.getAsObject());
            }
            stmt.free();
            return results;
        } catch (e) {
            console.error('Query Error:', e, sql);
            return [];
        }
    },

    // --- IndexedDB 存取邏輯 ---

    _openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('PCRD_DB_STORE', 2);
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('files')) {
                    db.createObjectStore('files');
                }
            };
            request.onsuccess = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('files')) {
                    reject(new Error("Object store 'files' not found in IndexedDB."));
                    return;
                }
                resolve(db);
            };
            request.onerror = (e) => reject(request.error);
        });
    },

    async saveToIDB(key, buffer) {
        try {
            const db = await this._openDB();
            return new Promise((resolve, reject) => {
                const transaction = db.transaction('files', 'readwrite');
                const store = transaction.objectStore('files');
                store.put(buffer, key);
                transaction.oncomplete = () => resolve();
                transaction.onerror = () => reject(transaction.error);
                transaction.onabort = () => reject(transaction.error || new Error('快取寫入已中止'));
                transaction.addEventListener('complete', () => db.close());
                transaction.addEventListener('abort', () => db.close());
            });
        } catch (e) {
            console.error("[PCRDatabase] saveToIDB 失敗:", e);
            throw e;
        }
    },

    async loadFromIDB(key) {
        try {
            const db = await this._openDB();
            return new Promise((resolve) => {
                const transaction = db.transaction('files', 'readonly');
                const store = transaction.objectStore('files');
                const getRequest = store.get(key);
                getRequest.onsuccess = () => resolve(getRequest.result);
                getRequest.onerror = () => resolve(null);
            });
        } catch (e) {
            console.warn("[PCRDatabase] loadFromIDB 失敗:", e);
            return null;
        }
    },

    async removeFromIDB(key) {
        try {
            const db = await this._openDB();
            return new Promise((resolve) => {
                const transaction = db.transaction('files', 'readwrite');
                const store = transaction.objectStore('files');
                const deleteRequest = store.delete(key);
                deleteRequest.onsuccess = () => resolve();
                deleteRequest.onerror = () => resolve();
            });
        } catch (e) {
            console.warn("[PCRDatabase] removeFromIDB 失敗:", e);
            return;
        }
    }
};
