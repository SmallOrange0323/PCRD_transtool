console.log("db.js loaded");
if (localStorage.getItem('pcr_region') !== 'tw') {
    localStorage.setItem('pcr_region', 'tw');
}
/**
 * PCR 數據導航站 - DB 引擎
 * 負責下載、快取與查詢 SQLite 資料庫
 */

window.PCRDatabase = {
    db: null,
    currentRegion: 'tw',

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
        const remoteUrl = `https://wthee.xyz/db/redive_${this.currentRegion}.db`;
        const localPath = `./redive_${this.currentRegion}.db`;
        const sizeKey = `pcr_db_size_${this.currentRegion}`;

        try {
            // 1. 初始化 SQL 引擎 (WebAssembly)
            if (onProgress) onProgress('正在初始化 SQL 引擎...', 10);
            
            if (typeof initSqlJs === 'undefined') {
                throw new Error("無法載入 SQL 引擎元件 (initSqlJs 未定義)。請嘗試按 Ctrl+F5 強制重新整理頁面。");
            }

            const sqlPromise = initSqlJs({
                locateFile: file => `${file}`
            });

            const timeoutPromise = new Promise((_, reject) => 
                setTimeout(() => reject(new Error("初始化 SQL 引擎逾時 (10秒)。可能是網路連線不穩定，或是瀏覽器不支援 WebAssembly/WASM。")), 10000)
            );

            const SQL = await Promise.race([sqlPromise, timeoutPromise]);

            // 獲取最新 size
            let size = 0;
            try {
                const headRes = await fetch(localPath, { method: 'HEAD' });
                if (headRes.ok) {
                    const cl = headRes.headers.get('content-length');
                    if (cl) size = parseInt(cl, 10);
                }
            } catch (e) {
                console.warn(`[PCRDatabase] HEAD ${localPath} failed, trying ${remoteUrl}...`, e);
            }
            if (size <= 0) {
                try {
                    const headRes = await fetch(remoteUrl, { method: 'HEAD' });
                    if (headRes.ok) {
                        const cl = headRes.headers.get('content-length');
                        if (cl) size = parseInt(cl, 10);
                    }
                } catch (e) {
                    console.warn(`[PCRDatabase] HEAD ${remoteUrl} failed...`, e);
                }
            }

            const cachedSize = localStorage.getItem(sizeKey);
            let forceReload = false;
            if (size > 0 && String(size) !== String(cachedSize)) {
                console.log(`[PCRDatabase] Size mismatch for ${this.currentRegion} (current: ${size}, cached: ${cachedSize}). Force reload.`);
                forceReload = true;
                await this.removeFromIDB(dbKey);
            }

            // 2. 嘗試從 IndexedDB 讀取 (快取隔離)
            let cachedDB = null;
            if (!forceReload) {
                cachedDB = await this.loadFromIDB(dbKey);
            }

            if (cachedDB) {
                if (onProgress) onProgress(`正在載入本地 ${this.currentRegion.toUpperCase()} 快取...`, 50);
                this.db = new SQL.Database(new Uint8Array(cachedDB));
                
                // 驗證快取是否有效與完整
                if (this.verifyDatabase()) {
                    console.log(`[PCRDatabase] Loaded and verified ${this.currentRegion} from IndexedDB`);
                    return this.db;
                } else {
                    console.warn(`[PCRDatabase] 快取資料庫無效或損壞，將強制重載...`);
                    this.db = null;
                }
            }

            // 3. 嘗試從本地目錄取得 (繞過 CORS)
            if (onProgress) onProgress(`正在檢查本地 ${this.currentRegion.toUpperCase()} 檔案...`, 20);
            let dbData = await this.downloadDB(localPath).catch(() => null);

            // 4. 嘗試從遠端下載
            if (!dbData) {
                if (onProgress) onProgress(`正在下載遠端 ${this.currentRegion.toUpperCase()} 資料庫 (約 20MB)...`, 30);
                dbData = await this.downloadDB(remoteUrl, (pct) => {
                    if (onProgress) onProgress(`正在下載資料庫... ${pct}%`, 30 + (pct * 0.6));
                });
            }

            if (dbData) {
                this.db = new SQL.Database(new Uint8Array(dbData));
                if (this.verifyDatabase()) {
                    await this.saveToIDB(dbKey, dbData);
                    const finalSize = size > 0 ? size : dbData.byteLength;
                    localStorage.setItem(sizeKey, finalSize);
                    console.log(`[PCRDatabase] Successfully initialized and verified ${this.currentRegion} DB`);
                    return this.db;
                } else {
                    // 【修正 Bug 6】驗證失敗時清除無效的 this.db，避免後續操作在無效資料庫上執行
                    this.db = null;
                    throw new Error("載入的資料庫格式有誤，找不到劇情資料表。");
                }
            }

            throw new Error(`資料庫載入失敗。`);
        } catch (error) {
            console.error('Database Init Error:', error);
            if (onProgress) onProgress(`載入失敗: ${error.message}`, 0);
            throw error;
        }
    },


    /**
     * 下載資料庫文件（帶進度回調）
     */
    async downloadDB(dbUrl, onProgress) {
        try {
            console.log(`正在嘗試從 ${dbUrl} 取得資料庫...`);
            const response = await fetch(dbUrl);
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

    async saveToIDB(key, buffer) {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('PCRD_DB_STORE', 1);
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('files')) {
                    db.createObjectStore('files');
                }
            };
            request.onsuccess = (e) => {
                const db = e.target.result;
                const transaction = db.transaction('files', 'readwrite');
                const store = transaction.objectStore('files');
                store.put(buffer, key);
                transaction.oncomplete = () => resolve();
                transaction.onerror = () => reject(transaction.error);
            };
            request.onerror = () => reject(request.error);
        });
    },

    async loadFromIDB(key) {
        return new Promise((resolve) => {
            const request = indexedDB.open('PCRD_DB_STORE', 1);
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('files')) {
                    db.createObjectStore('files');
                }
            };
            request.onsuccess = (e) => {
                const db = e.target.result;
                const transaction = db.transaction('files', 'readonly');
                const store = transaction.objectStore('files');
                const getRequest = store.get(key);
                getRequest.onsuccess = () => resolve(getRequest.result);
                getRequest.onerror = () => resolve(null);
            };
            request.onerror = () => resolve(null);
        });
    },

    async removeFromIDB(key) {
        return new Promise((resolve) => {
            const request = indexedDB.open('PCRD_DB_STORE', 1);
            request.onsuccess = (e) => {
                const db = e.target.result;
                const transaction = db.transaction('files', 'readwrite');
                const store = transaction.objectStore('files');
                const deleteRequest = store.delete(key);
                deleteRequest.onsuccess = () => resolve();
                deleteRequest.onerror = () => resolve();
            };
            request.onerror = () => resolve();
        });
    }
};
