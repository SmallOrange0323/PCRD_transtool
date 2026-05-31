// --- 1. 基礎數據與配置 ---

const CHARACTER_POSITIONS = {
    "愛梅斯": 805, "艾姬多娜（夏日）": 795, "艾姬多娜": 795,
    "可璃亞": 128, "可璃亞（夏日）": 128, "日和": 153, "日和（薩拉薩利亞）": 153, "日和（星界）": 168,
    "真琴": 165, "月月": 165, "真琴（指揮官）": 165, "月月（指揮官）": 165,
    "梅杜莎": 345, "小梅": 345, "格蕾斯": 345, "克莉絲提娜": 395, "克莉絲提娜（始源）": 395, "克": 395,
    "惠理子": 251, "病嬌": 251, "惠理子（指揮官）": 251, "病嬌（指揮官）": 251,
    "薇歐莉特": 535, "堇": 535, "若菜": 545, "普蕾西亞（夏日）": 575, "水豬妹": 575, "克蘿茜（風靈）": 622,
    "鳳凰": 685, "涅妃＝涅羅": 721, "栞（遊俠）": 735, "狼栞": 735, "帆稀": 761, "帆稀（夏日）": 782,
    "凱留（公主）": 795, "公黑": 795, "菲歐": 805, "涅婭（夏日）": 818, "志那都": 761, "可璃亞（學園）": 128
};

const NICKNAME_MAP = {
    "水豬妹": "普蕾西亞（夏日）", "泳豬": "普蕾西亞（夏日）", "水璃亞": "可璃亞（夏日）", "學碧": "可璃亞（學園）", "狼栞": "栞（遊俠）",
    "公黑": "凱留（公主）", "黑貓": "凱留（公主）", "黑猫": "凱留（公主）",
    "水莉莉": "莉莉（夏日）", "聖克": "克莉絲提娜（聖誕）", "圣克": "克莉絲提娜（聖誕）",
    "白貓": "凱留（公主）", "白猫": "凱留（公主）", "堇": "薇歐莉特", 
    "紫羅蘭": "薇歐莉特", "紫罗兰": "薇歐莉特", "月月": "真琴", 
    "小梅": "梅杜莎", "美杜莎": "梅杜莎", "病嬌": "惠理子（指揮官）", "惠理子": "惠理子（指揮官）",
    "真琴（指揮官）": "真琴（指揮官）", "月月（指揮官）": "真琴（指揮官）",
    "克": "克莉絲提娜", "始源克": "克莉絲提娜（始源）",
    "蘭法龍": "蘭法", "兰法龙": "蘭法", "蘭法": "蘭法", "兰法": "蘭法",
    "多娜": "艾姬多娜（夏日）", "水厄": "艾姬多娜（夏日）", "艾姬多娜(夏)": "艾姬多娜（夏日）",
    "聖姐": "愛梅斯", "天姐": "愛梅斯", "愛梅斯": "愛梅斯",
    "水優妮": "優妮（夏日）", "白菲": "雪菲", "切嚕": "琪愛兒", "流夏": "流夏"
};

const S2T_STR_S = "队战业开场预设点击关连打后转换个别角色说明总凱留帆希萝茜薇欧莉特萨拉亚里伦蒂娜始源琴堇普蕾西亚夏若菜栞游侠菲娅凤凰涅妃星界咏装圣学园陆王实装诅咒灵风万圣华镜妮卡似花矛依里备注兰忍伤害阶段自动全对应輸出手动簡單容易優化調整補充貓羅龍員击伤敌标护辅团联结协属设置参数据资库确认显示选项测试创建删码统系划计丽莉尔诺玛泽时间爱优怜恋丝儿纯铃绫静绪阳纺启叶猫龙华圣";
const S2T_STR_T = "隊戰業開場預設點擊關連打後轉換個別角色說明總凱留帆希蘿茜薇歐莉特薩拉亞里倫蒂娜始源琴堇普蕾西亞夏若菜栞遊俠菲婭鳳凰涅妃星界泳裝聖學園陸王實裝詛咒靈風萬聖華鏡妮卡似花矛依里備註蘭忍傷害階段自動全對應輸出手動簡單容易優化調整補充貓羅龍員擊傷敵標護輔團聯結協屬設置參數據資庫確認顯示選項測試創建刪碼系統劃計麗莉爾諾瑪澤時間愛優憐戀絲兒純鈴綾靜緒陽紡啟葉貓龍華聖";
const S2T_MAP = {};
for(let i=0; i<S2T_STR_S.length; i++) { S2T_MAP[S2T_STR_S[i]] = S2T_STR_T[i]; }
const COMMON_S2T = { "发": "發", "门": "門", "无": "無", "报": "報", "记": "記", "时": "時", "间": "間", "轴": "軸", "对": "對", "态": "態", "备": "備" };
Object.assign(S2T_MAP, COMMON_S2T);

function s2t(str) {
    if (!str) return "";
    let res = str.split('').map(char => S2T_MAP[char] || char).join('');
    // 全形數字轉半形
    res = res.replace(/[０-９]/g, s => String.fromCharCode(s.charCodeAt(0) - 0xFEE0));
    return res;
}

function getPosition(name) {
    if (!name) return 999;
    const mappedName = NICKNAME_MAP[name] || name;
    const clean = mappedName.replace(/[（(].*?[）)]/, '').trim();
    return CHARACTER_POSITIONS[clean] || CHARACTER_POSITIONS[mappedName] || 999;
}

function processConversion() {
    const sourceText = document.getElementById('sourceText');
    const resultPreview = document.getElementById('resultPreview');
    const hiddenResult = document.getElementById('hiddenResult');
    const smartSort = document.getElementById('smartSort').checked;
    if (!sourceText.value.trim()) { resultPreview.innerText = ""; return; }
    
    const lines = sourceText.value.split('\n');
    
    // 自動填入角色名 (抓取 5★ 開頭的行)
    const detectedChars = lines.filter(l => l.trim().match(/^[56]★/)).slice(0, 5);
    detectedChars.forEach((l, i) => {
        const name = l.trim().replace(/^[56]★/, '').trim();
        const input = document.getElementById('char' + (i+1));
        if(input && !input.value) input.value = name;
    });

    const charInputs = [
        document.getElementById('char1').value, document.getElementById('char2').value,
        document.getElementById('char3').value, document.getElementById('char4').value, document.getElementById('char5').value
    ];
    
    let characters = charInputs.map((val, idx) => ({
        name: val || `角色${idx+1}`,
        displayName: (NICKNAME_MAP[val] || val || `角色${idx+1}`).replace(/[（(].*?[）)]/, '').trim(),
        pos: getPosition(val),
        index: idx
    }));

    let mapping = [0, 1, 2, 3, 4];
    if (smartSort) {
        const sorted = [...characters].sort((a, b) => a.pos - b.pos);
        mapping = sorted.map(c => c.index);
    }

    let output = [];
    let currentStatus = "XXXXX";
    let currentAuto = false;
    let prevTimeVal = 999;
    
    function processInstruction(time, trigger, newStatus, suffix) {
        let warn = "";
        let tVal = parseInt(time, 10);
        if (tVal > prevTimeVal) warn += " ⚠️時間錯誤";
        prevTimeVal = tVal;

        let nextAuto = currentAuto;
        let autoExtra = "";
        
        if (suffix.includes("開auto") || suffix.includes("自動 ON") || suffix.includes("自動ON")) {
            nextAuto = true;
            autoExtra = " + 開auto";
        }
        if (suffix.includes("關auto") || suffix.includes("自動 OFF") || suffix.includes("自動OFF")) {
            nextAuto = false;
            autoExtra = " + 關auto";
        }
        currentAuto = nextAuto;

        let ons = [], offs = [];
        for (let i = 0; i < 5; i++) {
            if (currentStatus[i] !== newStatus[i]) {
                const char = characters[mapping[i]].displayName;
                newStatus[i] === 'O' ? ons.push(char) : offs.push(char);
            }
        }
        
        const cleanTrigger = trigger.split(/[→\->]/)[0].trim();
        let inst = [];
        if (ons.length) inst.push(`${ons.join('&')}on`);
        if (offs.length) inst.push(`${offs.join('&')}off`);
        
        output.push(`${time} ${cleanTrigger}→ ${inst.join(' + ') || "無狀態改變"}${autoExtra} (${newStatus}) ${warn}`.trimEnd());
        currentStatus = newStatus;
    }

    lines.forEach(line => {
        let l = line.trim();
        if (!l) { output.push(""); return; }
        if (l.match(/^[56]★/)) { output.push(l); return; }
        
        // 1. 處理開場行
        const openMatch = l.match(/^(\d{2,3})?\s*開場[：:]?\s*([開关自動]{2}\s*(ON|OFF)?)?\s*\+?\s*set\s*([OX]{5})/i);
        if (openMatch) {
            const [_, time, autoPart, dummy, status] = openMatch;
            currentStatus = status.toUpperCase();
            if (autoPart) {
                currentAuto = !(autoPart.includes("OFF") || autoPart.includes("關") || autoPart.includes("关"));
            }
            output.push(l);
            return;
        }

        // 2. 處理標準指令 (支援箭頭或單一空格分隔)
        const stateSuffixMatch = l.match(/^(\d{2,3})\s+(.*?)\(([OX]{5})\)(.*)/i);
        if (stateSuffixMatch) {
            const [_, time, trigger, newStatus, suffix] = stateSuffixMatch;
            processInstruction(time, trigger, newStatus.toUpperCase(), suffix);
        } else {
            // 嘗試匹配帶有箭頭或純空格的模式
            const m = l.match(/^(\d{2,3})\s+(.*?)\s*(?:[→\->]\s*)?([OX]{5})(.*)/i);
            if (m && m[3]) {
                const [_, time, trigger, newStatus, suffix] = m;
                processInstruction(time, trigger, newStatus.toUpperCase(), suffix);
            } else {
                output.push(l);
            }
        }
    });

    resultPreview.innerText = output.join('\n');
    hiddenResult.value = output.join('\n');
}

// --- UI 控制函式 ---

window.openTab = function(tabId) {
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if(btn.getAttribute('onclick').includes(tabId)) { btn.classList.add('active'); }
    });
};

window.copyResult = function() {
    const text = document.getElementById('hiddenResult').value;
    navigator.clipboard.writeText(text).then(() => alert("已複製結果"));
};

window.clearInput = function() {
    document.getElementById('sourceText').value = "";
    for(let i=1; i<=5; i++) document.getElementById('char' + i).value = "";
    processConversion();
};

window.runPreCleanup = function() {
    const src = document.getElementById('preSource');
    const res = document.getElementById('preResult');
    let rawText = src.value.trim();
    if(!rawText) { res.innerText = ""; return; }
    
    // 1. 預處理：符號與繁簡轉換
    let text = s2t(rawText);
    
    // 優先標準化箭頭與分隔符 (避免 -> 被拆解成 X >)
    text = text.replace(/⇒|->|>/g, ' → ')
               .replace(/[、，,]/g, ' & ')
               .replace(/['"’‘“”`\t/]/g, ' ')
               .replace(/\*\d+/g, '') // 移除腳註如 *1
               .replace(/　/g, ' ');

    text = text.replace(/全[sS][eE][tT]/g, 'OOOOO')
               .replace(/[sS][eE][tT]/g, 'on');
    
    // 保護 auto 關鍵字，防止其中的小寫 o 被誤殺為大寫 O
    text = text.replace(/auto/gi, '___AUTO___');

    // 特殊符號對應 (僅處理全形/特殊符號，保護半形減號以免破壞時間範圍)
    // 擴充：將 ─、━、― 等製圖符號與水平線，以及 ❌ 轉換為標準 X，將 ⭕ 轉換為標準 O
    text = text.replace(/[ー—－─━―x✕❌]/g, 'X')
               .replace(/[〇◯◯◯o○◎●⭕]/g, 'O');

    // 還原 auto 關鍵字
    text = text.replace(/___AUTO___/g, 'auto');

    let lines = text.split('\n').map(l => l.trim()).filter(l => l);
    let processedLines = [];
    let currentAutoState = ""; 

    for (let i = 0; i < lines.length; i++) {
        let l = lines[i];
        l = l.replace(/^([56])[星s\*]/i, '$1★');
        // 時間解析：1:30 -> 130
        l = l.replace(/^(\d{1,2})[:：](\d{2})/, (m, p1, p2) => `${p1.padStart(1, '0')}${p2}`);
        // 智慧補零：51 -> 051 (針對行首為 1-2 位數字的情況)
        l = l.replace(/^(\d{1,2})\x20/, (m, p1) => p1.padStart(3, '0') + ' ');
        
        let autoToggle = "";
        let statusStr = "";
        
        if (l.match(/(自动|自動|auto)\s*(ON|on)/i) || l.match(/(開|开)\s*auto/i)) autoToggle = "開auto";
        if (l.match(/(自动|自動|auto)\s*(OFF|off)/i) || l.match(/(關|关)\s*auto/i)) autoToggle = "關auto";
        l = l.replace(/(自动|自動|auto)\s*(ON|OFF|on|off)/gi, '')
             .replace(/(開|开|關|关)\s*auto/gi, '')
             .trim();
        // 針對連寫在中括號內的 [auto on] 進行清理
        l = l.replace(/[\[\]]/g, ' ').trim();

        const patternRegex = /[(\[【]?([OX]{5})[)\]】]?/i;
        // 關鍵：如果行內已經有箭頭了，則不要進行狀態碼的提取與重排列，直接按原樣保留 (僅進行符號標準變形)
        const statusMatch = l.includes('→') ? null : l.match(patternRegex);
        
        if (statusMatch) {
            statusStr = statusMatch[1].toUpperCase();
            if (!autoToggle) {
                const afterText = l.substring(statusMatch.index + statusMatch[0].length);
                if (afterText.match(/^\s*(ON|on)\b/i)) autoToggle = "開auto";
                if (afterText.match(/^\s*(OFF|off)\b/i)) autoToggle = "關auto";
            }
            l = l.replace(statusMatch[0], '').trim();
            if (autoToggle) {
                l = l.replace(/\s*(ON|OFF|on|off)\b/i, '').trim();
            }
        }

        l = l.replace(/\s*\b(ON|SET)\b/gi, 'on').replace(/\s*\bOFF\b/gi, 'off');
        
        let showAutoSuffix = false;
        if (autoToggle && autoToggle !== currentAutoState) {
            showAutoSuffix = true;
            currentAutoState = autoToggle;
        }

        if (statusStr) {
            const isOpenTime = l.match(/^(130)/);
            const isOpenKeyword = l.match(/^(初始|開始|开始|正式|初期|戰鬥開始|战斗开始|預設|開場)/);
            const isFirstLineWithStatus = (i === 0);

            if (isOpenTime || isOpenKeyword || isFirstLineWithStatus) {
                currentAutoState = autoToggle || currentAutoState || "開auto";
                processedLines.push(`開場：${currentAutoState} + set ${statusStr}`);
                continue;
            }
            
            const timeOnlyMatch = l.match(/^(\d{3})$/);
            if (timeOnlyMatch) l = `${timeOnlyMatch[1]} 準備`;
            
            let lineResult = l ? `${l} → ${statusStr}` : `→ ${statusStr}`;
            if (showAutoSuffix) lineResult += ` + ${currentAutoState}`;
            processedLines.push(lineResult);
        } else {
            // 包含箭頭的行、或無狀態碼的行，直接加上 Auto 狀態更新即可
            let lineResult = l;
            if (showAutoSuffix) lineResult += ` + ${currentAutoState}`;
            processedLines.push(lineResult);
        }
    }

    // 跨行合併邏輯
    let mergedLines = [];
    for (let i = 0; i < processedLines.length; i++) {
        let curr = processedLines[i];
        if ((curr.startsWith('→') || curr.startsWith('⇒')) && mergedLines.length > 0) {
            let prev = mergedLines.pop();
            mergedLines.push(`${prev} ${curr}`);
        } else {
            mergedLines.push(curr);
        }
    }

    // 美化輸出
    const beautifulLines = mergedLines.map(l => {
        let res = l.replace(/\s+/g, ' ');
        res = res.replace(/^(\d{3})(\S)/, '$1 $2');
        res = res.replace(/\s*→\s*/g, ' → ');
        res = res.replace(/\s*\+\s*/g, ' + ');
        return res;
    });

    res.innerText = beautifulLines.join('\n');
};

window.copyPreToMain = function() {
    const txt = document.getElementById('preResult').innerText;
    document.getElementById('sourceText').value = txt;
    processConversion();
    openTab('converter');
};

window.copyDiscordAnsi = function() {
    const text = document.getElementById('preResult').innerText.trim();
    if (!text) { alert("沒有可整理的結果，請先點擊一鍵整理！"); return; }

    const lines = text.split('\n');
    let prevStatus = "XXXXX"; // 初始狀態預設為全關
    let coloredLines = [];

    // ANSI 顏色控制碼 (預設使用黃底白字：極致純亮白字體 + 亮黃背景，確保在所有 Discord 客戶端及色彩主題下均有最極致的清晰度與對比度)
    const ANSI_RESET = "\u001b[0m";
    const ANSI_HIGHLIGHT = "\u001b[1;97;43m"; // 1;97;43m 為極致亮白字體 + 亮黃背景

    lines.forEach((line, index) => {
        let l = line;

        // 1. 如果是第一行 (通常是開場行)，不要進行任何著色，但需提取其狀態碼作為 prevStatus 的起點
        const isFirstLine = (index === 0 || l.includes("開場"));
        if (isFirstLine) {
            const match = l.match(/\b([OX]{5})\b/);
            if (match) {
                prevStatus = match[1];
            }
            coloredLines.push(l); // 直接推送原行，保持純白色
            return;
        }

        // 2. 智慧比對 5 位元狀態碼，將有改變的位元高亮標記
        // 開關 auto 保持原樣不上色，以維持極簡與高可讀性
        l = l.replace(/\b([OX]{5})\b/g, (statusStr) => {
            let coloredStr = "";
            for (let i = 0; i < 5; i++) {
                const char = statusStr[i];
                // 如果這個位置的狀態與前一次不同，則加上指定顏色高亮
                if (char !== prevStatus[i]) {
                    coloredStr += `${ANSI_HIGHLIGHT}${char}${ANSI_RESET}`;
                } else {
                    coloredStr += char;
                }
            }
            prevStatus = statusStr; // 更新前一次的狀態為當前狀態
            return coloredStr;
        });

        coloredLines.push(l);
    });

    const discordPayload = "```ansi\n" + coloredLines.join('\n') + "\n```";

    navigator.clipboard.writeText(discordPayload).then(() => {
        alert("已複製 Discord 彩色版作業！\n直接在 Discord 貼上即可呈現超讚的變色效果！");
    }).catch(err => {
        console.error("複製失敗：", err);
        alert("複製失敗，請手動複製結果。");
    });
};

window.clearPre = function() {
    document.getElementById('preSource').value = "";
    document.getElementById('preResult').innerText = "";
};

document.addEventListener('DOMContentLoaded', () => {
    const st = document.getElementById('sourceText');
    if(st) st.addEventListener('input', processConversion);
    const ss = document.getElementById('smartSort');
    if(ss) ss.addEventListener('change', processConversion);
    for(let i=1; i<=5; i++) {
        const ci = document.getElementById('char' + i);
        if(ci) ci.addEventListener('input', processConversion);
    }
});