console.log("chapter-data.js loaded");
/**
 * PCRD Data Hub - 章節資料服務
 * 載入並提供章節標題、摘要、順序等中繼資料
 * 資料來源：dashboard/data/chapters.json
 */

window.ChapterDataService = {
    data: null,
    loaded: false,

    async load() {
        if (this.loaded) return this.data;
        try {
            const resp = await fetch('data/chapters.json?v=' + Date.now());
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            this.data = await resp.json();
            this.loaded = true;
            console.log('[ChapterDataService] 成功載入章節資料', Object.keys(this.data).length, '部');
        } catch (e) {
            console.error('[ChapterDataService] 載入失敗:', e);
            this.data = { 1: {}, 2: {}, 3: {} };
            this.loaded = true;
        }
        return this.data;
    },

    // 取得章節資訊
    // part: 1|2|3, groupId: story_group_id (如 2001, 2007, 2201, 3001)
    getChapterInfo(part, groupId) {
        if (!this.data) return null;
        const partData = this.data[String(part)] || {};
        const gid = String(groupId);
        // 不分部別，均自 game_world 與 interlude 中尋找對應的群組資料
        return partData.game_world?.[gid] || partData.interlude?.[gid] || partData[gid] || null;
    },

    // 取得章節標題
    getChapterTitle(part, groupId) {
        const info = this.getChapterInfo(part, groupId);
        return info ? info.title : "";
    },

    // 取得章節標題
    getTitle(part, groupId) {
        const info = this.getChapterInfo(part, groupId);
        return info?.title || null;
    },

    // 取得章節摘要
    getSummary(part, groupId) {
        const info = this.getChapterInfo(part, groupId);
        return info?.summary || null;
    },

    // 取得章節顯示順序（用於排序）
    getOrder(part, groupId) {
        const info = this.getChapterInfo(part, groupId);
        return info?.order ?? 999;
    },

    // 取得所有章節
    getAllChapters(part) {
        if (!this.data) return [];
        const partData = this.data[String(part)] || {};
        let entries = [];
        
        // 提取 game_world 與 interlude 下的項目
        const gw = Object.entries(partData.game_world || {}).map(([gid, info]) => ({ groupId: parseInt(gid), ...info }));
        const il = Object.entries(partData.interlude || {}).map(([gid, info]) => ({ groupId: parseInt(gid), ...info }));
        
        // 如果外層有直接定義的 flat 資料，也一併提取作為相容性支援
        const flat = Object.entries(partData)
            .filter(([k]) => k !== 'game_world' && k !== 'interlude')
            .map(([gid, info]) => ({ groupId: parseInt(gid), ...info }));

        entries = [...gw, ...il, ...flat];
        return entries.sort((a, b) => a.order - b.order);
    },

    // 由 groupId 推斷部別
    // 2000-2015 → Part 1, 2101-2116 → Part 2, 2201-2215 → Part 3, 3000+ → Part 3
    getPartFromGroupId(groupId) {
        if (groupId >= 2201 && groupId <= 2215) return 3;
        if (groupId >= 2101 && groupId <= 2116) return 2;
        if (groupId >= 3000) return 3;
        if (groupId >= 2000 && groupId <= 2015) return 1;
        return 1;
    },

    // 由 groupId 取得章節鍵名（用於 chapters 物件的 key）
    getChapterKey(part, groupId, fallbackTitle) {
        const info = this.getChapterInfo(part, groupId);
        if (info?.key) return info.key;

        // 回退：依規則生成
        if (part === 1) {
            if (groupId === 2000) return "序章";
            return `第${groupId - 2000}章`;
        }
        if (part === 2) {
            return `第${groupId - 2100}章`;
        }
        if (part === 3) {
            if (groupId >= 2201 && groupId <= 2215) return `第${groupId - 2200}章`;
            if (groupId >= 3001 && groupId <= 3022) return `幕間 ${groupId - 3000}`;
            if (groupId >= 4000) return `幕間 ${groupId - 4000}`;
            return fallbackTitle || `群組 ${groupId}`;
        }
        return fallbackTitle || `群組 ${groupId}`;
    },
};