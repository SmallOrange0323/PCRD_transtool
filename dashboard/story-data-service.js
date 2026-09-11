/**
 * PCRD Story Data Service (M3A Official Story Metadata Runtime)
 * 負責官方故事話數元數據 (official_story_metadata.json) 的非同步快取與獲取。
 * 遵守 D2 / M3A Loading, Cache & Concurrency Contract:
 * 1. 取得 build info: fetch("data/db_info.json", { cache: "no-store" })
 * 2. 若存在 info.metadata_version，請求 official_story_metadata.json?v=${metadata_version}
 * 3. 若 404 / 失敗 / 缺失 metadata_version，以 no-store fetch("data/official_story_metadata.json", { cache: "no-store" })
 * 4. 嚴格禁止 fallback 到 db_version
 * 5. 並行請求共享單一 Promise；若失敗重設 _loadingPromise 以利 retry，且不 throw crash UI
 * 6. 最小形狀防禦 (Minimal Runtime Shape Guard)
 */
(function() {
    'use strict';

    class StoryDataService {
        constructor() {
            this._metadataCache = null;
            this._loadingPromise = null;
        }

        /**
         * 確保官方元數據已載入至記憶體快取。
         * @returns {Promise<Object|null>} episodes map 或 null (若載入失敗)
         */
        async ensureMetadataLoaded() {
            if (this._metadataCache !== null) {
                return this._metadataCache;
            }
            if (this._loadingPromise !== null) {
                return this._loadingPromise;
            }

            this._loadingPromise = (async () => {
                try {
                    let metadataUrl = "data/official_story_metadata.json";
                    let fetchOptions = { cache: "no-store" };

                    // 1. 探測 db_info.json 取得 metadata_version
                    try {
                        const infoRes = await fetch("data/db_info.json", { cache: "no-store" });
                        if (infoRes.ok) {
                            const info = await infoRes.json();
                            if (info && typeof info.metadata_version === "string" && info.metadata_version.trim()) {
                                metadataUrl = `data/official_story_metadata.json?v=${encodeURIComponent(info.metadata_version.trim())}`;
                                fetchOptions = {}; // 具備版本號時允許瀏覽器快取
                            }
                        }
                    } catch (e) {
                        // db_info 探測失敗時保持 no-store 直連
                    }

                    // 2. 請求 official_story_metadata.json
                    const res = await fetch(metadataUrl, fetchOptions);
                    if (!res.ok) {
                        console.warn(`[StoryDataService] 官方元數據側車載入失敗 (HTTP ${res.status}): ${metadataUrl}`);
                        return null;
                    }

                    const data = await res.json();

                    // 3. Minimal Runtime Shape 防禦
                    if (!data || typeof data !== "object" || Array.isArray(data)) {
                        console.warn("[StoryDataService] 官方元數據側車頂層結構無效 (非物件)");
                        return null;
                    }

                    const episodes = data.episodes;
                    if (!episodes || typeof episodes !== "object" || Array.isArray(episodes)) {
                        console.warn("[StoryDataService] 官方元數據側車 episodes 結構無效 (非字典物件)");
                        return null;
                    }

                    this._metadataCache = episodes;
                    return this._metadataCache;
                } catch (err) {
                    console.warn("[StoryDataService] 載入官方元數據側車發生異常:", err);
                    return null;
                } finally {
                    this._loadingPromise = null;
                }
            })();

            return this._loadingPromise;
        }

        /**
         * 取得指定話數之官方元數據物件。
         * @param {number|string} storyId
         * @returns {Promise<Object|null>}
         */
        async getEpisodeMetadata(storyId) {
            if (storyId === undefined || storyId === null) return null;
            const episodes = await this.ensureMetadataLoaded();
            if (!episodes) return null;
            const sidStr = String(storyId);
            const ep = episodes[sidStr];
            return (ep && typeof ep === "object") ? ep : null;
        }

        /**
         * 取得指定話數之官方大綱文字 (cmd1)。
         * @param {number|string} storyId
         * @returns {Promise<string|null>}
         */
        async getOfficialSynopsis(storyId) {
            const ep = await this.getEpisodeMetadata(storyId);
            if (!ep || typeof ep.official_synopsis !== "string") return null;
            return ep.official_synopsis.trim() || null;
        }

        /**
         * 取得指定話數之官方章節大標題 (cmd0)。
         * @param {number|string} storyId
         * @returns {Promise<string|null>}
         */
        async getChapterTitle(storyId) {
            const ep = await this.getEpisodeMetadata(storyId);
            if (!ep || typeof ep.chapter_title !== "string") return null;
            return ep.chapter_title.trim() || null;
        }

        /**
         * 取得指定話數之官方副標題 (cmd32)。
         * @param {number|string} storyId
         * @returns {Promise<string|null>}
         */
        async getSubtitle(storyId) {
            const ep = await this.getEpisodeMetadata(storyId);
            if (!ep || typeof ep.subtitle !== "string") return null;
            return ep.subtitle.trim() || null;
        }
    }

    // 掛載至全域 window
    window.StoryDataService = new StoryDataService();
})();
