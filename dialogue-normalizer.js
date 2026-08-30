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
                // 合併條件：前一筆存在、非特殊項目、相同發言人姓名、且語音相容 (當前無語音標籤或語音標籤完全相同)
                if (last &&
                    last.type !== 'still' &&
                    last.type !== 'background' &&
                    last.type !== 'movie' &&
                    last.name === item.name &&
                    (!item.voice || last.voice === item.voice)) {

                    let lastWords = (last.words || "").trim();
                    let currentWords = (item.words || "").trim();

                    if (!currentWords) {
                        return; // 如果當前行去除前後空白後為空，直接忽略
                    }

                    if (!lastWords) {
                        last.words = currentWords;
                    } else {
                        last.words = lastWords + "\n" + currentWords;
                    }

                    // 若前一筆無 voice 但當前筆有 voice，繼承 voice 標籤
                    if (!last.voice && item.voice) {
                        last.voice = item.voice;
                    }
                } else {
                    const cloned = { ...item };
                    if (cloned.words) {
                        cloned.words = cloned.words.trim();
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
