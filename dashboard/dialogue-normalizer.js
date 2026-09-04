console.log("dialogue-normalizer.js loaded");
/**
 * PCRD Data Hub - 對白資料正規化模組 (DialogueNormalizer)
 * 負責將原始對白劇本 JSON 資料進行純邏輯清洗、空行過濾、連續同發言人/同語音氣泡合併，
 * 以及萃取唯一發言人名單。
 * 
 * 本模組為純運算模組（Pure Function Module）：
 * 1. 嚴格不修改輸入的 rawDialogueList 陣列與物件（No Input Mutation 保證）。
 * 2. 零外部依賴：不操作 DOM、不存取全域狀態、不發起非同步請求、不依賴資料庫。
 */

(function() {
    /**
     * 驗證並解析有效之具體 unit_id (大於 0 的正整數)
     * @param {*} value
     * @returns {number|null}
     */
    function getConcreteUnitId(value) {
        if (value === null || value === undefined) return null;
        if (typeof value === 'number') {
            return Number.isInteger(value) && value > 0 ? value : null;
        }
        if (typeof value === 'string') {
            const trimmed = value.trim();
            if (!/^\d+$/.test(trimmed)) return null;
            const parsed = Number(trimmed);
            return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
        }
        return null;
    }

    const DialogueNormalizer = {
        /**
         * 正規化對白劇本資料並萃取發言人清單
         * @param {Array<Object>} rawDialogueList - 原始對白劇本陣列
         * @returns {{ dialogueList: Array<Object>, speakerNames: Array<string> }}
         */
        normalize(rawDialogueList) {
            if (!rawDialogueList || !Array.isArray(rawDialogueList) || rawDialogueList.length === 0) {
                return {
                    dialogueList: [],
                    speakerNames: []
                };
            }

            const dialogueList = [];

            rawDialogueList.forEach(item => {
                if (!item || typeof item !== 'object') return;

                // 特殊類型項目 (插畫 / 背景切換 / 動畫標記) 直接 shallow clone 保留
                if (item.type === 'still' || item.type === 'background' || item.type === 'movie') {
                    dialogueList.push({ ...item });
                    return;
                }

                // 檢查去除換行後的文字是否為純空白
                const cleanedWords = (item.words || "").replace(/\\n/g, "").replace(/\n/g, "").trim();
                if (!cleanedWords) {
                    return; // 忽略純空行或純 \n 的氣泡，消除大行距
                }

                const last = dialogueList[dialogueList.length - 1];

                const lastUnitId = last ? getConcreteUnitId(last.unit_id) : null;
                const currentUnitId = getConcreteUnitId(item.unit_id);
                const hasConcreteUnitConflict = (
                    lastUnitId !== null &&
                    currentUnitId !== null &&
                    lastUnitId !== currentUnitId
                );

                // 合併條件：前一筆存在、非特殊項目、相同發言人姓名、語音相容且無具體 unit_id 衝突
                if (last &&
                    last.type !== 'still' &&
                    last.type !== 'background' &&
                    last.type !== 'movie' &&
                    last.name === item.name &&
                    (!item.voice || last.voice === item.voice) &&
                    !hasConcreteUnitConflict) {

                    const rawCurrentWords = item.words || "";
                    // 判定官方劇本換行標記（以 \n 開頭或前句以 \n 結尾）
                    const hasLeadingNewline = rawCurrentWords.startsWith("\n") || rawCurrentWords.startsWith("\r\n");
                    const hasTrailingNewline = (last.words || "").endsWith("\n") || (last.words || "").endsWith("\r\n");

                    const cleanCurrent = rawCurrentWords.replace(/^[\r\n]+/, "").trimEnd();
                    if (!cleanCurrent) {
                        return; // 若純為換行/空白，直接忽略
                    }

                    if (!last.words) {
                        last.words = cleanCurrent;
                    } else if (hasLeadingNewline || hasTrailingNewline) {
                        // 官方劇本明確帶有換行意圖，保留換行
                        last.words = last.words.trimEnd() + "\n" + cleanCurrent;
                    } else {
                        // 官方劇本無換行標記，屬於同一行內的連續斷句，同行接續（對齊遊戲實機全文模式）
                        last.words = last.words.trimEnd() + cleanCurrent;
                    }

                    // 若前一筆無 voice 但當前筆有 voice，繼承 voice 標籤
                    if (!last.voice && item.voice) {
                        last.voice = item.voice;
                    }
                } else {
                    const cloned = { ...item };
                    if (cloned.words) {
                        cloned.words = cloned.words.replace(/^[\r\n]+/, "").trimEnd();
                    }
                    dialogueList.push(cloned);
                }
            });

            // 萃取登場發言人名單 (支援合稱拆分與順序去重)
            const speakerNames = [];
            dialogueList.forEach(item => {
                if (item.name) {
                    const names = item.name.split(/[、＆&]|和|與/).map(n => n.trim()).filter(Boolean);
                    names.forEach(name => {
                        if (!speakerNames.includes(name)) {
                            speakerNames.push(name);
                        }
                    });
                }
            });

            return {
                dialogueList,
                speakerNames
            };
        }
    };

    // 掛載至全域環境 (支援 Browser window 或 Node.js global)
    if (typeof window !== 'undefined') {
        window.DialogueNormalizer = DialogueNormalizer;
    } else if (typeof global !== 'undefined') {
        global.DialogueNormalizer = DialogueNormalizer;
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = DialogueNormalizer;
    }
})();
