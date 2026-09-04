console.log("avatar-service.js loaded");
/**
 * PCRD Data Hub - 統一頭像服務
 * 集中管理角色頭像 URL 生成、降級邏輯、快取與預載
 */

const globalScope = typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this);
globalScope.AvatarService = {
    // Phase 6: Avatar Manifest 登錄表快取
    manifestMap: new Map(),
    manifestLoaded: false,
    manifestUnavailable: false,
    _manifestPromise: null,

    /**
     * 載入並快取 Avatar Manifest (avatar_assets.json)
     * @param {Object} manifestData - Manifest JSON 物件
     */
    loadManifest(manifestData) {
        if (!manifestData || !Array.isArray(manifestData.assets)) {
            this.manifestMap.clear();
            this.manifestLoaded = true;
            this.manifestUnavailable = true;
            return;
        }
        this.manifestMap.clear();
        for (const entry of manifestData.assets) {
            if (entry.unit_id != null) {
                this.manifestMap.set(Number(entry.unit_id), entry);
            }
        }
        this.manifestLoaded = true;
        this.manifestUnavailable = false;
    },

    /**
     * 異步確保 Manifest 已載入 (供前端與異步呼叫端使用，永不 Reject)
     * @returns {Promise<void>}
     */
    async ensureManifestLoaded() {
        if (this.manifestLoaded) return;
        if (this._manifestPromise) return this._manifestPromise;
        if (typeof fetch !== 'undefined') {
            this._manifestPromise = fetch('data/avatar_assets.json')
                .then(res => {
                    if (res.ok) return res.json();
                    throw new Error(`HTTP ${res.status}`);
                })
                .then(manifestData => {
                    this.loadManifest(manifestData);
                })
                .catch(err => {
                    console.warn('[AvatarService] Failed to fetch avatar_assets.json; failing closed to unavailable state:', err);
                    this.manifestMap.clear();
                    this.manifestLoaded = true;
                    this.manifestUnavailable = true;
                });
            return this._manifestPromise;
        }
    },

    /**
     * 【Phase 6 核心契約】顯式對白頭像解析 (Exact Dialogue Identity Resolution)
     * 嚴格保持顯式 unit_id，不進行百位規整化、不換裝替代、不查詢名字推斷
     * @param {number|string} unitId 
     * @param {Object} [options]
     * @param {boolean} [options.warnIfAbsent=true] - 當 unit_id 不在 Manifest 時是否發出 warning
     * @returns {Object|null} { status: 'active'|'placeholder_only'|'unknown_placeholder'|'manifest_unavailable', unitId: number, filename: string|null }
     */
    resolveExactDialoguePortrait(unitId, options = {}) {
        if (!unitId || (typeof unitId !== 'number' && typeof unitId !== 'string')) return null;
        const numId = Number(unitId);
        if (!Number.isInteger(numId) || numId < 100000) return null;

        // 若 Manifest 載入失敗/不可用，明確標記狀態並 Fail-Closed
        if (this.manifestUnavailable) {
            if (options.warnIfAbsent !== false) {
                console.warn(`[AvatarService] Avatar manifest is unavailable; failing closed explicit dialogue unit_id ${numId} to placeholder.`);
            }
            return {
                status: 'manifest_unavailable',
                unitId: numId,
                filename: null
            };
        }

        const entry = this.manifestMap.get(numId);
        if (entry) {
            if (entry.status === 'active') {
                return {
                    status: 'active',
                    unitId: numId,
                    filename: entry.filename || `${numId}.png`
                };
            }
            if (entry.status === 'placeholder_only') {
                return {
                    status: 'placeholder_only',
                    unitId: numId,
                    filename: null
                };
            }
        }

        // 顯式 ID 未在 Manifest 登錄：嚴格 Fail Closed 顯示佔位符，並在未被抑制時警告
        if (options.warnIfAbsent !== false) {
            console.warn(`[AvatarService] Explicit dialogue unit_id ${numId} is absent from avatar_assets.json; failing closed to placeholder.`);
        }
        return {
            status: 'unknown_placeholder',
            unitId: numId,
            filename: null
        };
    },

    /**
     * 通用/名字推斷對白頭像解析 (Generic / Inferred Identity Resolution)
     * 僅供無顯式 unit_id 之通用 UI、卡片、可玩角色名稱推斷時使用
     * @param {number|string} unitId 
     * @returns {Array<number>} 候選 ID 陣列 (優先序由前至後)
     */
    resolveDefaultPortraitIds(unitId) {
        if (!unitId || (typeof unitId !== 'number' && typeof unitId !== 'string')) return [];
        const numId = Number(unitId);
        if (!Number.isInteger(numId) || numId < 100000) return [];

        // 1. NPC 角色 (>= 190000)：維持 exact unit ID
        if (numId >= 190000) {
            return [numId];
        }

        // 2. 已知特殊 NPC / Exact-ID 角色 (如 107411 幻境龍后、107412、107431 等)
        if (this.exactPortraitIds.has(numId)) {
            return [numId];
        }

        // 3. 特殊 Exact-ID 優先角色 (如 138331 佩可 override、139231 美穗、139331 真穗、139431 艾麗卡)
        if (this.exactFirstWithBaseFallback.has(numId)) {
            const baseId = Math.floor(numId / 100) * 100;
            return [numId, baseId + 11];
        }

        // 4. 明確定義的現實專屬頭像 ID
        if (this.exactRealityIds.has(numId)) {
            const baseId = Math.floor(numId / 100) * 100;
            return [numId, baseId + 11];
        }

        // 5. 普通可玩角色與換裝 Variant (< 190000)
        const baseId = Math.floor(numId / 100) * 100;
        return [baseId + 11, baseId + 31];
    },
    // 【修正 Bug 4 & Bug 8】HTML 實體編碼輔助函數
    escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    // 【修正 Bug 8】用於 onerror 處理器中的字串跳脫
    escapeForJsString(str) {
        if (!str) return "";
        return String(str)
            .replace(/\\/g, "\\\\") // 先處理反斜線
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"');
    },
    // CDN 域名優先序（依序嘗試）
    cdnBases: [
        'https://redive.estertion.win/icon/unit/',
        'https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/icon/unit/',
    ],
    localBase: 'icon/unit/',

    // 手動補全：顯示名稱 -> unit_id (取 MIN(unit_id) 且 < 200000)
    customMap: {
        "涅婭": 123311,
        "涅雅": 123311,
        "安涅默涅": 129611,
        "普蕾西亞": 126112,
        "莉莉": 125811,
        "可璃": 126011,
        "可璃亞": 126011,
        "八斗神局長": 193631,
        "八斗金局長": 193631,
        "八斗": 193631,
        "八斗神": 193631,
        "剎鬼‧八斗神": 193631,
        "菲絲雷斯": 193732,
        "菲絲": 193732,
        "媞雅": 193211,
        "格魯尼": 194311,
        "羅蘭": 194211,
        "涅妃‧涅羅": 129711,
        "魏雅": 195211,
        "葛拉比亞": 193511,
        "葛拉菲拉": 193511,
        "澄花": 198211,
        "美穗": 139231,
        "真穗": 139331,
        "艾麗卡": 139431,
        "西住美穗": 139231,
        "西住真穗": 139331,
        "逸見艾麗卡": 139431,
    },

    // 集中定義明確指定之 Exact-Appearance 集合 (不執行普通 +11 normalization)
    exactPortraitIds: new Set([
        107411, 107412, 107431 // 幻境龍后等特殊 NPC/Boss 形態
    ]),

    // 集中定義 Exact-ID 優先並支援 Base+11 備選的特殊角色 (GuP 聯動、138331 專屬 override 等)
    exactFirstWithBaseFallback: new Set([
        138331, // dialogue-view 專屬指定之阿斯特賴亞佩可頭像 override
        139231, // 西住美穗 (GuP 官方發布之 canonical 頭像)
        139331, // 西住真穗 (GuP)
        139431  // 逸見艾麗卡 (GuP)
    ]),

    // 第 3 部分支劇情現實篇章之角色現實專屬頭像 ID 映射表
    realityAvatarMap: {
        "八斗神": 193631,
        "八斗神局長": 193631,
        "一之瀨 祈梨": 106631,
        "一之瀨祈梨": 106631,
        "一華 牡丹": 129631,
        "一華牡丹": 129631,
        "七七香": 101332,
        "七七香（夏日）": 101332,
        "七七香（萬聖節）": 101332,
        "三角 千歌": 104232,
        "三角千歌": 104232,
        "上喜 忍": 103132,
        "上喜忍": 103132,
        "丹野 七七香": 101332,
        "丹野七七香": 101332,
        "久央璃亞": 126031,
        "九朗 千惠": 126431,
        "九朗千惠": 126431,
        "亞里莎": 106331,
        "伊緒": 101832,
        "伊緒（夏日）": 101832,
        "伊緒（聖誕節）": 101832,
        "伊緒（黑暗）": 101832,
        "伊莉亞": 104431,
        "伊莉亞‧奧恩斯坦": 104431,
        "伊莉亞・奧恩斯坦": 104431,
        "伊莉亞（新年）": 104431,
        "伊莉亞（祭服）": 104431,
        "伊莉亞（聖誕節）": 104431,
        "似似花": 107032,
        "似似花（夏日）": 107032,
        "似似花（始源）": 107032,
        "似似花（新年）": 107032,
        "佐佐木 咲戀": 102832,
        "佐佐木咲戀": 102832,
        "佩可": 105831,
        "佩可莉姆": 105831,
        "依里": 102232,
        "依里（天使）": 102232,
        "依里（聖誕節）": 102232,
        "倉石 惠理子": 102732,
        "倉石惠理子": 102732,
        "倭": 130031,
        "優妮": 111032,
        "優妮（冬日）": 111032,
        "優妮（聖學祭）": 111032,
        "優花梨": 103432,
        "優花梨（夏日）": 103432,
        "優花梨（聖誕節）": 103432,
        "優花梨（露營）": 103432,
        "優衣": 100232,
        "優衣（公主）": 100232,
        "優衣（夏日）": 100232,
        "優衣（新年）": 100232,
        "優衣（星素）": 100232,
        "優衣（祭服）": 100232,
        "優衣（聖誕節）": 100232,
        "克莉絲提娜": 107131,
        "克莉絲提娜‧摩根": 107131,
        "克莉絲提娜・摩根": 107131,
        "克莉絲提娜（始源）": 107131,
        "克莉絲提娜（狂野）": 107131,
        "克莉絲提娜（聖誕節）": 107131,
        "克蕾琪塔": 118031,
        "克蕾琪塔（聖誕節）": 118031,
        "克蕾雅": 118031,
        "克蕾雅‧波洋希亞": 118031,
        "克蕾雅・波洋希亞": 118031,
        "克蘿依": 110832,
        "克蘿依（冬日）": 110832,
        "克蘿依（聖學祭）": 110832,
        "克蘿茜": 126431,
        "克蘿茜（航空）": 126431,
        "冰川 鏡華": 103633,
        "冰川鏡華": 103633,
        "凜": 112531,
        "凜（NGs）": 112531,
        "凱留": 106031,
        "凱留（公主）": 106031,
        "凱留（夏日）": 106031,
        "凱留（插班生）": 106031,
        "凱留（新年）": 106031,
        "凱留（超載）": 106031,
        "凱留（霸瞳天星）": 106031,
        "出雲 宮子": 100731,
        "出雲宮子": 100731,
        "初音": 101231,
        "初音（初音＆栞）": 101231,
        "初音（夏日）": 101231,
        "初音（新年）": 101231,
        "剎鬼": 135931,
        "劍持 志名都": 135631,
        "劍持志名都": 135631,
        "北条 綾音": 102332,
        "北条綾音": 102332,
        "北條 綾音": 102332,
        "北條綾音": 102332,
        "千歌": 104232,
        "千歌（夏日）": 104232,
        "千歌（祭服）": 104232,
        "千歌（聖誕節）": 104232,
        "千里 真那": 106931,
        "千里真那": 106931,
        "卯中 樞": 130931,
        "卯中樞": 130931,
        "卯之花 蘭": 118131,
        "卯之花蘭": 118131,
        "卯月": 112431,
        "卯月（NGs）": 112431,
        "厄莉絲": 129031,
        "厄莉絲（夏日）": 129031,
        "可可蘿": 105932,
        "可可蘿（公主）": 105932,
        "可可蘿（嚮導幼君）": 105932,
        "可可蘿（夏日）": 105932,
        "可可蘿（新年）": 105932,
        "可可蘿（祭服）": 105932,
        "可可蘿（遊俠）": 105932,
        "可璃亞": 126031,
        "可璃亞（墮落）": 126031,
        "可璃亞（夏日）": 126031,
        "吉塔": 105731,
        "吉塔（術士）": 105731,
        "咲戀": 102832,
        "咲戀（夏日）": 102832,
        "咲戀（新年）": 102832,
        "咲戀（秋乃＆咲戀）": 102832,
        "咲戀（聖誕節）": 102832,
        "咲戀（薩拉薩利亞）": 102832,
        "喜屋武 香織": 101732,
        "喜屋武香織": 101732,
        "嘉夜": 106532,
        "嘉夜（時空旅行）": 106532,
        "嘉夜（解放者）": 106532,
        "園上 矛依未": 106131,
        "園上矛依未": 106131,
        "埃拉": 135531,
        "士条 怜": 100332,
        "士条怜": 100332,
        "士條 怜": 100332,
        "士條怜": 100332,
        "大泉 美冬": 104833,
        "大泉美冬": 104833,
        "大神 美冬": 104833,
        "大神美冬": 104833,
        "大鳶 剎鬼": 135931,
        "大鳶剎鬼": 135931,
        "天坂‧露易絲‧真璃": 132331,
        "天坂・露易絲・真璃": 132331,
        "天野 鈴莓": 102531,
        "天野鈴莓": 102531,
        "太刀洗 流夏": 105632,
        "太刀洗流夏": 105632,
        "妮諾": 103031,
        "妮諾‧珠貝爾": 103031,
        "妮諾・珠貝爾": 103031,
        "妮諾（夏日）": 103031,
        "妮諾（大江戶）": 103031,
        "妮諾（萬聖節）": 103031,
        "姬宮 真步": 101032,
        "姬宮真步": 101032,
        "安涅默涅": 129631,
        "安涅默涅（夏日）": 129631,
        "安芸 真琴": 104331,
        "安芸真琴": 104331,
        "宮坂 珠希": 104632,
        "宮坂珠希": 104632,
        "宮子": 100731,
        "宮子（聖誕節）": 100731,
        "宮子（萬聖節）": 100731,
        "宵濱 深月": 105132,
        "宵濱深月": 105132,
        "尤絲蒂亞娜": 105831,
        "尤絲蒂亞娜‧F‧阿斯特賴亞": 105831,
        "尤絲蒂亞娜・F・阿斯特賴亞": 105831,
        "島村 卯月": 112431,
        "島村卯月": 112431,
        "布武機": 130231,
        "帆稀": 106731,
        "帆稀（夏日）": 106731,
        "帆稀（新年）": 106731,
        "希留耶": 106031,
        "幽野 飛白": 133032,
        "幽野飛白": 133032,
        "庫露露": 130931,
        "彩羽": 132431,
        "御久間 智": 103732,
        "御久間智": 103732,
        "德川 莉莉": 125831,
        "德川莉莉": 125831,
        "忍": 103132,
        "忍（夏日）": 103132,
        "忍（海盜）": 103132,
        "忍（萬聖節）": 103132,
        "志木場 寢亞": 123331,
        "志木場 禰羅": 129731,
        "志木場寢亞": 123331,
        "志木場禰羅": 129731,
        "志那都": 135631,
        "怜": 100332,
        "怜（公主）": 100332,
        "怜（夏日）": 100332,
        "怜（新年）": 100332,
        "怜（星素）": 100332,
        "怜（萬聖節）": 100332,
        "惠理子": 102732,
        "惠理子（夏日）": 102732,
        "惠理子（情人節）": 102732,
        "惠理子（指揮官）": 102732,
        "愛川 美里": 101533,
        "愛川美里": 101533,
        "拉比林斯達": 106832,
        "拉比林斯達（始源）": 106832,
        "拉比林斯達（超載）": 106832,
        "拿娜": 136231,
        "撫瑠無": 127831,
        "支倉 伊緒": 101832,
        "支倉伊緒": 101832,
        "日和": 100132,
        "日和（公主）": 100132,
        "日和（夏日）": 100132,
        "日和（新年）": 100132,
        "日和（星素）": 100132,
        "日和（薩拉薩利亞）": 100132,
        "星野 靜流": 104932,
        "星野靜流": 104932,
        "春咲 日和": 100132,
        "春咲日和": 100132,
        "普蕾西亞": 126131,
        "普蕾西亞‧懷茲曼": 126131,
        "普蕾西亞・懷茲曼": 126131,
        "普蕾西亞（墮落）": 126131,
        "普蕾西亞（夏日）": 126131,
        "晶": 106832,
        "智": 103732,
        "智（萬聖節）": 103732,
        "智（魔法少女）": 103732,
        "望": 102931,
        "望（夏日）": 102931,
        "望（聖誕節）": 102931,
        "望（解放者）": 102931,
        "望（鍊金術師）": 102931,
        "未央": 112631,
        "未央（NGs）": 112631,
        "本田 未央": 112631,
        "本田未央": 112631,
        "杏奈": 100931,
        "杏奈（夏日）": 100931,
        "杏奈（海盜）": 100931,
        "柊 杏奈": 100931,
        "柊杏奈": 100931,
        "柏崎 初音": 101231,
        "柏崎 栞": 103832,
        "柏崎初音": 101231,
        "柏崎栞": 103832,
        "栗林 胡桃": 102131,
        "栗林胡桃": 102131,
        "栞": 103832,
        "栞（冬日）": 103832,
        "栞（初音＆栞）": 103832,
        "栞（遊俠）": 103832,
        "栞（魔法少女）": 103832,
        "格蕾斯": 133032,
        "格蕾斯（兔女郎）": 133032,
        "梅杜莎": 133631,
        "棗 可蘿": 105932,
        "棗可蘿": 105932,
        "森近 鈴": 102632,
        "森近鈴": 102632,
        "模索路 晶": 106832,
        "模索路晶": 106832,
        "櫻": 136132,
        "櫻井 望": 102931,
        "櫻井望": 102931,
        "步未": 105532,
        "步未（奇幻）": 105532,
        "步未（怪盜）": 105532,
        "流 魅空": 118231,
        "流夏": 105632,
        "流夏（夏日）": 105632,
        "流夏（新年）": 105632,
        "流夏（薩拉薩利亞）": 105632,
        "流魅空": 118231,
        "涅妃‧涅羅": 129731,
        "涅妃‧涅羅（鬼面佛心）": 129731,
        "涅婭": 123331,
        "涅婭（夏日）": 123331,
        "深月": 105132,
        "深月（大江戶）": 105132,
        "深月（新年）": 105132,
        "源 櫻花": 136132,
        "源櫻花": 136132,
        "澀谷 凜": 112531,
        "澀谷凜": 112531,
        "烏爾姆": 127831,
        "燐人": 127731,
        "玉泉 美咲": 105032,
        "玉泉美咲": 105032,
        "珠希": 104632,
        "珠希（咖啡廳）": 104632,
        "珠希（夏日）": 104632,
        "珠希（工作服）": 104632,
        "班比": 122332,
        "現士場黑江": 107032,
        "現士實 似似花": 107032,
        "現士實似似花": 107032,
        "琪愛兒": 110932,
        "琪愛兒（冬日）": 110932,
        "琪愛兒（聖學祭）": 110932,
        "琳德": 127731,
        "璃乃": 101131,
        "璃乃（奇幻）": 101131,
        "璃乃（新年）": 101131,
        "璃乃（聖誕節）": 101131,
        "璃乃（靜流＆璃乃）": 101131,
        "白銀 純": 104732,
        "白銀純": 104732,
        "百地 希留耶": 106031,
        "百地希留耶": 106031,
        "真步": 101032,
        "真步（夏日）": 101032,
        "真步（夢想樂園）": 101032,
        "真步（探險家）": 101032,
        "真步（灰姑娘）": 101032,
        "真琴": 104331,
        "真琴（夏日）": 104331,
        "真琴（指揮官）": 104331,
        "真琴（灰姑娘）": 104331,
        "真行寺 由仁": 111032,
        "真行寺由仁": 111032,
        "真那": 106931,
        "真軌": 191031,
        "狂真咲 真軌": 191031,
        "狂真咲真軌": 191031,
        "真陽": 103332,
        "真陽（聖誕節）": 103332,
        "真陽（遊俠）": 103332,
        "矛依未": 106131,
        "矛依未（新年）": 106131,
        "矛依未（解放者）": 106131,
        "石動 彩羽": 132431,
        "石動 苑": 132531,
        "石動彩羽": 132431,
        "石動苑": 132531,
        "石橋 步未": 105532,
        "石橋步未": 105532,
        "碧": 104032,
        "碧卡拉": 125631,
        "碧卡拉（合作）": 125631,
        "碧（工作服）": 104032,
        "碧（插班生）": 104032,
        "碧（露營）": 104032,
        "碧（駕駛員）": 104032,
        "祈梨": 106631,
        "祈梨（怪盜）": 106631,
        "祈梨（新年）": 106631,
        "祈梨（時空旅行）": 106631,
        "祓樹 艾爾": 126532,
        "祓樹艾爾": 126532,
        "禊": 100432,
        "禊（夏日）": 100432,
        "禊（小小甜心）": 100432,
        "禊（萬聖節）": 100432,
        "秋乃": 103232,
        "秋乃（夏日）": 103232,
        "秋乃（秋乃＆咲戀）": 103232,
        "秋乃（聖誕節）": 103232,
        "穗高 禊": 100432,
        "穗高禊": 100432,
        "空花": 104532,
        "空花（夏日）": 104532,
        "空花（大江戶）": 104532,
        "空花（黑暗）": 104532,
        "純": 104732,
        "純（夏日）": 104732,
        "純（聖誕節）": 104732,
        "純（露營）": 104732,
        "紡希": 105432,
        "紡希（吉歐‧格黑納）": 105432,
        "紡希（夏日）": 105432,
        "紡希（萬聖節）": 105432,
        "紫苑 愛莉": 129031,
        "紫苑愛莉": 129031,
        "綾瀬 優花梨": 103432,
        "綾瀬優花梨": 103432,
        "綾音": 102332,
        "綾音（探險家）": 102332,
        "綾音（聖誕節）": 102332,
        "織原 茉莉": 100531,
        "織原茉莉": 100531,
        "繭宮 紡希": 105432,
        "繭宮紡希": 105432,
        "美冬": 104833,
        "美冬（夏日）": 104833,
        "美冬（工作服）": 104833,
        "美咲": 105032,
        "美咲（夏日）": 105032,
        "美咲（舞台）": 105032,
        "美咲（萬聖節）": 105032,
        "美波 鈴奈": 101632,
        "美波鈴奈": 101632,
        "美空": 118231,
        "美空（夏日）": 118231,
        "美空（聖誕節）": 118231,
        "美美": 102032,
        "美美（夏日）": 102032,
        "美美（小小甜心）": 102032,
        "美美（萬聖節）": 102032,
        "美里": 101533,
        "美里（夏日）": 101533,
        "美里（新年）": 101533,
        "胡桃": 102131,
        "胡桃（聖誕節）": 102131,
        "胡桃（舞台）": 102131,
        "花凜": 118531,
        "花凜（鍊金術師）": 118531,
        "花守 愛來": 135531,
        "花守愛來": 135531,
        "苑": 132531,
        "若菜": 130132,
        "若菜（冬日）": 130132,
        "茉莉": 100531,
        "茉莉（狂野）": 100531,
        "茉莉（萬聖節）": 100531,
        "茜 美美": 102032,
        "茜美美": 102032,
        "茜里": 100632,
        "茜里（天使）": 100632,
        "茜里（聖誕節）": 100632,
        "草野 優衣": 100232,
        "草野優衣": 100232,
        "莉瑪": 105231,
        "莉瑪（灰姑娘）": 105231,
        "莉莉": 125831,
        "莉莉（墮落）": 125831,
        "莉莉（夏日）": 125831,
        "莫妮卡": 105332,
        "莫妮卡‧拜斯溫特": 105332,
        "莫妮卡・拜斯溫特": 105332,
        "莫妮卡（咖啡廳）": 105332,
        "莫妮卡（新年）": 105332,
        "莫妮卡（魔法少女）": 105332,
        "菫": 133131,
        "華宮 鳳子": 134731,
        "華宮鳳子": 134731,
        "華音": 134931,
        "菲歐": 134031,
        "萊拉耶爾": 126532,
        "萊拉耶爾（完美帕菲）": 126532,
        "萊拉耶爾（聖誕節）": 126532,
        "薇歐莉特": 133131,
        "薇歐莉特（黃泉鯨命）": 133131,
        "藤堂 秋乃": 103232,
        "藤堂秋乃": 103232,
        "蘭法": 118131,
        "蘭法（夏日）": 118131,
        "蘭法（祭服）": 118131,
        "虹村 雪": 100832,
        "虹村雪": 100832,
        "蠻出井 倭": 130031,
        "蠻出井 布武機": 130231,
        "蠻出井 若菜": 130132,
        "蠻出井倭": 130031,
        "蠻出井布武機": 130231,
        "蠻出井若菜": 130132,
        "衣之咲 璃乃": 101131,
        "衣之咲璃乃": 101131,
        "觀崎 佳凜": 118531,
        "觀崎佳凜": 118531,
        "角野 斜": 136231,
        "角野斜": 136231,
        "貪吃佩可": 105831,
        "貪吃佩可（公主）": 105831,
        "貪吃佩可（夏日）": 105831,
        "貪吃佩可（新年）": 105831,
        "貪吃佩可（聖誕節）": 105831,
        "貪吃佩可（超載）": 105831,
        "貪吃佩可（阿斯特賴亞）": 105831,
        "遠見 空花": 104532,
        "遠見空花": 104532,
        "遠野 帆稀": 106731,
        "遠野帆稀": 106731,
        "野戶 真陽": 103332,
        "野戶真陽": 103332,
        "鈴": 102632,
        "鈴奈": 101632,
        "鈴奈（夏日）": 101632,
        "鈴奈（插班生）": 101632,
        "鈴奈（萬聖節）": 101632,
        "鈴莓": 102531,
        "鈴莓（夏日）": 102531,
        "鈴莓（新年）": 102531,
        "鈴莓（春日）": 102531,
        "鈴（萬聖節）": 102632,
        "鈴（遊俠）": 102632,
        "鏡華": 103633,
        "鏡華（哥德）": 103633,
        "鏡華（夏日）": 103633,
        "鏡華（小小甜心）": 103633,
        "鏡華（春日）": 103633,
        "鏡華（萬聖節）": 103633,
        "阿剌克涅": 136031,
        "阿賀斗 紫布菜": 106432,
        "阿賀斗紫布菜": 106432,
        "雙葉 碧": 104032,
        "雙葉碧": 104032,
        "雪": 100832,
        "雪白 幸乃": 135831,
        "雪白幸乃": 135831,
        "雪菲": 106432,
        "雪菲（公主）": 106432,
        "雪菲（夏日）": 106432,
        "雪菲（新年）": 106432,
        "雪野": 135831,
        "雪（大江戶）": 100832,
        "雪（祭服）": 100832,
        "霞": 101431,
        "霞（修女）": 101431,
        "霞（夏日）": 101431,
        "霞（新年）": 101431,
        "霞（魔法少女）": 101431,
        "霧原 霞": 101431,
        "霧原霞": 101431,
        "露娜": 111431,
        "露易絲瑪莉": 132331,
        "霸瞳": 106931,
        "霸瞳皇帝": 106931,
        "靜流": 104932,
        "靜流（夏日）": 104932,
        "靜流（情人節）": 104932,
        "靜流（新年）": 104932,
        "靜流（靜流＆璃乃）": 104932,
        "靜流（黑暗）": 104932,
        "風宮 依里": 102232,
        "風宮 茜里": 100632,
        "風宮依里": 102232,
        "風宮茜里": 100632,
        "風間 琪愛兒": 110932,
        "風間琪愛兒": 110932,
        "香織": 101732,
        "香織（夏日）": 101732,
        "香織（萬聖節）": 101732,
        "鬼道 嘉夜": 106532,
        "鬼道嘉夜": 106532,
        "鳳凰": 134731,
        "鵺之宮 伽音": 134931,
        "鵺之宮伽音": 134931,
        "黑土 夜雲": 136031,
        "黑土夜雲": 136031,
        "黑江": 107032,
        "黑江 花子": 110832,
        "黑江花子": 110832
    },

    // 明確定義的現實專屬頭像 ID 集合 (嚴格優先保留 exact ID)
    exactRealityIds: new Set([
        100132, 100232, 100332, 100432, 100531, 100632,
        100731, 100832, 100931, 101032, 101131, 101231,
        101332, 101431, 101533, 101632, 101732, 101832,
        102032, 102131, 102232, 102332, 102531, 102632,
        102732, 102832, 102931, 103031, 103132, 103232,
        103332, 103432, 103633, 103732, 103832, 104032,
        104232, 104331, 104431, 104532, 104632, 104732,
        104833, 104932, 105032, 105132, 105231, 105332,
        105432, 105532, 105632, 105731, 105831, 105932,
        106031, 106131, 106331, 106432, 106532, 106631,
        106731, 106832, 106931, 107031, 107032, 107131, 110832,
        110932, 111032, 111431, 112431, 112531, 112631,
        118031, 118131, 118231, 118531, 122332, 123331,
        125631, 125831, 126031, 126131, 126431, 126532,
        127731, 127831, 129031, 129631, 129731, 130031,
        130132, 130231, 130931, 132331, 132431, 132531,
        133032, 133131, 133631, 134031, 134731, 134931,
        135531, 135631, 135831, 135931, 136031, 136132,
        136231
    ]),

    // 快取：charaName -> { unitId, url, triedCdnIndex }
    cache: {},

    // 取得角色 unit_id（優先 customMap，再從外部傳入的 speakerAvatars 查找）
    getUnitId(charaName, externalAvatars = {}, isReality = false) {
        if (!charaName) return null;
        const cleanName = this.cleanName(charaName);
        if (isReality && (this.realityAvatarMap[charaName] || this.realityAvatarMap[cleanName])) {
            return this.realityAvatarMap[charaName] || this.realityAvatarMap[cleanName];
        }
        if (this.customMap[cleanName]) return this.customMap[cleanName];
        if (externalAvatars[cleanName]) return externalAvatars[cleanName];
        if (externalAvatars[charaName]) return externalAvatars[charaName];
        return null;
    },

    // 清理名稱（移除括號限定語、「的聲音」等）
    cleanName(name) {
        if (!name) return "";
        let clean = name.split(/[、＆&]|和|與/)[0].trim();
        clean = clean.replace(/（[^）]+）/g, "").replace(/\([^)]+\)/g, "").trim();
        if (clean.endsWith("的聲音")) clean = clean.replace(/的聲音$/, "");
        return clean;
    },

    /**
     * 核心 Helper：解析發言人/角色之對話立繪頭像 ID 優先序 (Identity & Tier Resolution)
     * 分離 Identity 解析與 Portrait Tier 決策，集中管理策略集合
     * @param {number|string} unitId 
     * @returns {Array<number>} 候選 ID 陣列 (優先序由前至後)
     */
    resolveDialoguePortraitIds(unitId, options = {}) {
        if (!unitId || (typeof unitId !== 'number' && typeof unitId !== 'string')) return [];
        const numId = Number(unitId);
        if (!Number.isInteger(numId) || numId < 100000) return [];

        // Phase 6: 顯式 Exact 優先判定
        const exact = this.resolveExactDialoguePortrait(numId, { warnIfAbsent: false });
        if (exact && (exact.status === 'active' || exact.status === 'placeholder_only')) {
            return [numId];
        }

        if (options.exact) {
            return (exact && exact.status === 'active') ? [numId] : [];
        }

        // 否則回退到通用預設解析
        return this.resolveDefaultPortraitIds(numId);
    },

    // 核心：生成頭像 URL 陣列（依優先序）
    getUrlCandidates(unitId) {
        if (!unitId || unitId < 100000) return [];
        const portraitIds = this.resolveDialoguePortraitIds(unitId);
        if (portraitIds.length === 0) return [];

        const candidates = [];
        
        // 1. webp 格式 (優先)
        portraitIds.forEach(id => {
            candidates.push(`${this.localBase}${id}.webp`);
            this.cdnBases.forEach(cdn => candidates.push(`${cdn}${id}.webp`));
        });

        // 2. png 格式 (降級備用，特別是 NPC 資源)
        portraitIds.forEach(id => {
            candidates.push(`${this.localBase}${id}.png`);
            this.cdnBases.forEach(cdn => candidates.push(`${cdn}${id}.png`));
        });

        return candidates;
    },

    getAvatarUrl(unitId) {
        if (!unitId) return 'https://redive.estertion.win/icon/unit/100001.webp';
        const portraitIds = this.resolveDialoguePortraitIds(unitId);
        const mainId = portraitIds.length > 0 ? portraitIds[0] : unitId;
        return `icon/unit/${mainId}.png`;
    },

    getCardUrl(unitId) {
        if (!unitId) return 'https://redive.estertion.win/card/full/100131.webp';
        const baseId = Math.floor(unitId / 100) * 100;
        const mainId = (unitId < 190000) ? (baseId + 31) : unitId;
        return `https://redive.estertion.win/card/full/${mainId}.webp`;
    },

    // 公開 API：取得最佳頭像 img 元素 HTML (根據角色名稱，通用推斷路徑)
    getAvatarHtml(charaName, externalAvatars = {}) {
        const cleanName = this.cleanName(charaName);
        const unitId = this.getUnitId(cleanName, externalAvatars);

        if (!unitId || unitId < 100000) {
            return this.getFallbackHtml(cleanName);
        }

        const portraitIds = this.resolveDefaultPortraitIds(unitId);
        const mainId = portraitIds.length > 0 ? portraitIds[0] : unitId;
        // 優先使用本地端的 .png 圖片
        const src = `icon/unit/${mainId}.png`;
        const safeName = this.escapeForJsString(cleanName);

        return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleError(this, '${safeName}', ${unitId})">`;
    },

    // 取得最佳頭像 img 元素 HTML (根據 unit_id)
    getAvatarHtmlByUnitId(unitId, charaName, externalAvatars = {}) {
        const cleanName = this.cleanName(charaName);
        const numId = Number(unitId);

        // A. 顯式對白 ID 路徑 (EXPLICIT DIALOGUE IDENTITY: unit_id >= 100000)
        if (Number.isInteger(numId) && numId >= 100000) {
            const resolved = this.resolveExactDialoguePortrait(numId);
            if (resolved.status === 'active') {
                const src = `icon/unit/${resolved.filename}`;
                const safeName = this.escapeForJsString(cleanName);
                return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleExactDialogueError(this, '${safeName}', ${numId})">`;
            }
            // placeholder_only 或未登錄 ID：直接輸出文字佔位符，不發送任何圖片請求
            return this.getFallbackHtml(cleanName);
        }

        // B. 通用推斷路徑 (INFERRED / NAME-ONLY)
        let finalUnitId = this.getUnitId(cleanName, externalAvatars);
        if (!finalUnitId || finalUnitId < 100000) {
            return this.getFallbackHtml(cleanName);
        }

        const portraitIds = this.resolveDefaultPortraitIds(finalUnitId);
        const mainId = portraitIds.length > 0 ? portraitIds[0] : finalUnitId;
        const src = `icon/unit/${mainId}.png`;
        const safeName = this.escapeForJsString(cleanName);

        return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleError(this, '${safeName}', ${finalUnitId})">`;
    },

    // 顯式對白專用立即 Fail-Closed 錯誤處理器 (不重試 CDN，不替換 ID)
    handleExactDialogueError(img, safeName, unitId) {
        img.style.display = 'none';
        if (img.parentNode) {
            const label = safeName ? safeName.substring(0, 2) : "??";
            img.parentNode.innerHTML = `<div class="npc-avatar-placeholder">${AvatarService.escapeHtml(label)}</div>`;
        }
    },

    // 靜態錯誤處理函式，用於逐步降級載入圖片或顯示文字佔位符
    handleError(img, safeName, arg3, arg4) {
        const finalUnitId = (arg4 !== undefined) ? arg4 : arg3;
        if (!img.dataset.step) {
            img.dataset.step = "1";
        }
        const step = parseInt(img.dataset.step, 10);
        const portraitIds = this.resolveDialoguePortraitIds(finalUnitId);
        const primaryId = portraitIds.length > 0 ? portraitIds[0] : finalUnitId;
        const secondaryId = portraitIds.length > 1 ? portraitIds[1] : null;

        if (step === 1) {
            img.dataset.step = "2";
            // 第一步：如果本地 primaryId png 失敗，嘗試 So-net 00500012 的 primaryId .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/icon/unit/${primaryId}.png`;
            return;
        }
        if (step === 2) {
            img.dataset.step = "3";
            // 第二步：如果 So-net 00500012 失敗，嘗試 So-net 00500015 的 primaryId .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500015/Jpn/AssetBundles/Android/icon/unit/${primaryId}.png`;
            return;
        }
        if (step === 3) {
            img.dataset.step = "4";
            // 第三步：如果 So-net 皆失敗，嘗試 EsterTion 的 primaryId .webp (EsterTion 頭像最齊全的格式)
            img.src = `https://redive.estertion.win/icon/unit/${primaryId}.webp`;
            return;
        }
        if (step === 4 && secondaryId) {
            img.dataset.step = "5";
            // 第四步：若 primaryId 均失敗且有 secondaryId (例如 +31 備選)，嘗試本地 secondaryId .png
            img.src = `icon/unit/${secondaryId}.png`;
            return;
        }
        if (step === 5 && secondaryId) {
            img.dataset.step = "6";
            // 第五步：嘗試 EsterTion 的 secondaryId .webp
            img.src = `https://redive.estertion.win/icon/unit/${secondaryId}.webp`;
            return;
        }

        // 最後失敗：隱藏圖片並顯示文字佔位符
        img.style.display = 'none';
        if (img.parentNode) {
            img.parentNode.innerHTML = `<div class="npc-avatar-placeholder">${safeName.substring(0, 2)}</div>`;
        }
    },

    // 文字佔位符
    getFallbackHtml(charaName) {
        const safeName = this.escapeHtml((charaName || "??").substring(0, 2)); // 【修正 Bug 4】編碼顯示文字
        return `<div class="npc-avatar-placeholder">${safeName}</div>`;
    },

    // 批次預載（可選）
    preload(charaNames, externalAvatars = {}) {
        charaNames.forEach(name => {
            const cleanName = this.cleanName(name);
            const unitId = this.getUnitId(cleanName, externalAvatars);
            if (!unitId) return;
            const candidates = this.getUrlCandidates(unitId);
            candidates.forEach(url => {
                const img = new Image();
                img.src = url;
            });
        });
    },

    // 註冊自定義映射（運行時動態補全）
    registerCustom(charaName, unitId) {
        this.customMap[charaName] = unitId;
    },

    // 取得技能圖示 HTML
    getSkillIconHtml(iconType) {
        if (!iconType) {
            return `<img src="https://redive.estertion.win/icon/unit/000000.png" style="width: 100%; height: 100%; object-fit: cover;">`;
        }
        // 優先使用本地端的 .png 圖片
        const src = `icon/skill/${iconType}.png`;
        return `<img src="${src}" style="width: 100%; height: 100%; object-fit: cover;" onerror="AvatarService.handleSkillError(this, ${iconType})">`;
    },

    // 技能圖示錯誤處理
    handleSkillError(img, iconType) {
        if (!img.dataset.step) {
            img.dataset.step = "1";
        }
        const step = parseInt(img.dataset.step, 10);

        if (step === 1) {
            img.dataset.step = "2";
            // 第一步：如果本地 png 失敗，嘗試 So-net 00500012 的 .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500012/Jpn/AssetBundles/Android/icon/skill/${iconType}.png`;
            return;
        }
        if (step === 2) {
            img.dataset.step = "3";
            // 第二步：如果 So-net 00500012 失敗，嘗試 So-net 00500015 的 .png
            img.src = `https://img-pc.so-net.tw/dl/Resources/00500015/Jpn/AssetBundles/Android/icon/skill/${iconType}.png`;
            return;
        }
        if (step === 3) {
            img.dataset.step = "4";
            // 第三步：如果 So-net 都失敗，嘗試 EsterTion 的 .webp
            img.src = `https://redive.estertion.win/icon/skill/${iconType}.webp`;
            return;
        }
        if (step === 4) {
            img.dataset.step = "5";
            // 第四步：嘗試 EsterTion 的 .png
            img.src = `https://redive.estertion.win/icon/skill/${iconType}.png`;
            return;
        }
        // 最後失敗：顯示 999999 佔位符（代表未知技能/裝備，這張圖在 EsterTion 上真實存在，是一張精美質感的問號圖案，比 000000 破圖好得多）
        img.src = 'https://redive.estertion.win/icon/equipment/999999.webp';
    }
};
// Node.js 環境自動載入 Manifest 支援單元測試與審查腳本
if (typeof process !== 'undefined' && process.versions && process.versions.node) {
    try {
        const fs = require('fs');
        const path = require('path');
        const manifestPath = path.resolve(__dirname, 'data', 'avatar_assets.json');
        if (fs.existsSync(manifestPath)) {
            const manifestData = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
            globalScope.AvatarService.loadManifest(manifestData);
        }
    } catch (e) {
        // Node 環境降級忽略
    }
}

// 瀏覽器環境自動嘗試載入 Manifest
if (typeof window !== 'undefined' && typeof window.fetch === 'function') {
    globalScope.AvatarService.ensureManifestLoaded();
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = globalScope.AvatarService;
}
