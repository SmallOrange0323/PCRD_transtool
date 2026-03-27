// --- 2. 繁簡轉換與通用工具 ---

const S2T_STR_S = "队战业开场预设点击关连打後轉換個別角色說明總凱留帆希萝茜薇欧莉特萨拉亞里倫蒂娜始源琴堇普蕾西亚夏若菜栞游侠菲娅凤凰涅妃星界咏裝聖學園陸王實裝詛咒靈風萬聖華鏡妮卡似花矛依里備註蘭忍傷害階段自動全對應輸出手動簡單容易優化調整補充貓羅龍員";
const S2T_STR_T = "隊戰業開場預設點擊關連打後轉換個別角色說明總凱留帆希蘿茜薇歐莉特薩拉亞里倫蒂娜始源琴堇普蕾西亞夏若菜栞遊俠菲婭鳳凰涅妃星界泳裝聖學園陸王實裝詛咒靈風萬聖華鏡妮卡似花矛依里備註蘭忍傷害階段自動全對應輸出手動簡單容易優化調整補充貓羅龍員";
const S2T_MAP = {};
for(let i=0; i<S2T_STR_S.length; i++) { S2T_MAP[S2T_STR_S[i]] = S2T_STR_T[i]; }
const COMMON_S2T = { "发": "發", "门": "門", "无": "無", "报": "報", "记": "記", "时": "時", "间": "間", "轴": "軸", "对": "對", "态": "態", "备": "備" };
Object.assign(S2T_MAP, COMMON_S2T);

/**
 * 繁簡轉換與全形數字正規化
 * @param {string} str 原始字串
 * @returns {string} 轉換後的繁體字串
 */
function s2t(str) {
    if (!str) return "";
    let res = str.split('').map(char => S2T_MAP[char] || char).join('');
    // 全形數字轉半形
    res = res.replace(/[０-９]/g, s => String.fromCharCode(s.charCodeAt(0) - 0xFEE0));
    return res;
}
