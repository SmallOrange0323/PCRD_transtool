// --- 1. 基礎數據與配置已遷移至 data.js ---

// --- 2. 繁簡轉換與工具函式已遷移至 utils.js ---


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
               .replace(/["\t/]/g, ' ')
               .replace(/\*\d+/g, '') // 移除腳註如 *1
               .replace(/　/g, ' ');

    text = text.replace(/全[sS][eE][tT]/g, 'OOOOO')
               .replace(/[sS][eE][tT]/g, 'on');
    
    // 特殊符號對應 (僅處理全形/特殊符號，保護半形減號以免破壞時間範圍)
    text = text.replace(/[ー—－x✕]/g, 'X')
               .replace(/[〇◯◯◯o○◎●]/g, 'O');

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
        
        if (l.match(/(自动|自動|auto)\s*(ON|on)/i)) autoToggle = "開auto";
        if (l.match(/(自动|自動|auto)\s*(OFF|off)/i)) autoToggle = "關auto";
        l = l.replace(/(自动|自動|auto)\s*(ON|OFF|on|off)/gi, '').trim();
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