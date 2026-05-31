console.log("db.js loaded");
/**
 * PCR 數據導航站 - DB 引擎
 * 負責下載、快取與查詢 SQLite 資料庫
 */

window.PCRDatabase = {
    db: null,
    currentRegion: localStorage.getItem('pcr_region') || 'tw',

    /**
     * 切換區域
     */
    async switchRegion(region) {
        if (this.currentRegion === region) return;
        
        console.log(`[PCRDatabase] Switching to ${region}...`);
        localStorage.setItem('pcr_region', region);
        
        // 物理隔離：直接重新整理頁面，確保所有 JS 變數與資料庫連接完全重置
        location.reload();
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

        try {
            // 1. 初始化 SQL 引擎 (WebAssembly)
            if (onProgress) onProgress('正在初始化 SQL 引擎...', 10);
            const SQL = await initSqlJs({
                locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${file}`
            });

            // 2. 嘗試從 IndexedDB 讀取 (快取隔離)
            const cachedDB = await this.loadFromIDB(dbKey);
            if (cachedDB) {
                if (onProgress) onProgress(`正在載入本地 ${this.currentRegion.toUpperCase()} 快取...`, 50);
                this.db = new SQL.Database(new Uint8Array(cachedDB));
                console.log(`[PCRDatabase] Loaded ${this.currentRegion} from IndexedDB`);
                return this.db;
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
                await this.saveToIDB(dbKey, dbData);
                console.log(`[PCRDatabase] Successfully initialized ${this.currentRegion} DB`);
                return this.db;
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
    }
};
