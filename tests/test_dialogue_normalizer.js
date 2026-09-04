/**
 * 單元測試：DialogueNormalizer
 * 驗證對白資料正規化、連續同發言人/語音合併、特殊項目保留、發言人拆分去重與 No Input Mutation 契約。
 */

const assert = require('assert');
const path = require('path');

// 載入待測模組
global.window = global;
const normalizerPath = path.resolve(__dirname, '../dashboard/dialogue-normalizer.js');
require(normalizerPath);

const DialogueNormalizer = global.DialogueNormalizer || window.DialogueNormalizer;

assert(DialogueNormalizer, 'DialogueNormalizer 必須正確載入並暴露於全域');

console.log('開始執行 DialogueNormalizer 測試案例...');

// Case 1: Empty input
{
    const resEmpty = DialogueNormalizer.normalize([]);
    assert.deepStrictEqual(resEmpty.dialogueList, [], '空陣列輸入應得到空 dialogueList');
    assert.deepStrictEqual(resEmpty.speakerNames, [], '空陣列輸入應得到空 speakerNames');

    const resNull = DialogueNormalizer.normalize(null);
    assert.deepStrictEqual(resNull.dialogueList, []);
    assert.deepStrictEqual(resNull.speakerNames, []);

    const resUndef = DialogueNormalizer.normalize(undefined);
    assert.deepStrictEqual(resUndef.dialogueList, []);
    assert.deepStrictEqual(resUndef.speakerNames, []);
}

// Case 2: Blank dialogue removed ("", "   ", "\n", "\\n")
{
    const input = [
        { name: '佩可', words: '第一句' },
        { name: '佩可', words: '' },
        { name: '佩可', words: '   ' },
        { name: '佩可', words: '\n' },
        { name: '佩可', words: '\\n' },
        { name: '佩可', words: '  \n  \\n  ' },
        { name: '凱留', words: '第二句' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 2, '空白與純換行對白應全數被過濾');
    assert.strictEqual(res.dialogueList[0].words, '第一句');
    assert.strictEqual(res.dialogueList[1].words, '第二句');
}

// Case 3: Same speaker + same voice merges (with \n)
{
    const input = [
        { name: '佑樹', voice: 'vo_001', words: 'hello' },
        { name: '佑樹', voice: 'vo_001', words: '\nworld' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 1, '同發言人同語音應合併為一筆');
    assert.strictEqual(res.dialogueList[0].words, 'hello\nworld', '帶有換行意圖時應以 \\n 相連');
    assert.strictEqual(res.dialogueList[0].voice, 'vo_001');

    // 子案例：無 \n 時同行接續（對齊遊戲實機全文模式）
    const inputInline = [
        { name: '真軌', voice: 'vo_000', words: '我的、' },
        { name: '真軌', voice: 'vo_000', words: '主……' }
    ];
    const resInline = DialogueNormalizer.normalize(inputInline);
    assert.strictEqual(resInline.dialogueList.length, 1);
    assert.strictEqual(resInline.dialogueList[0].words, '我的、主……', '無換行標記時應同行相接');
}

// Case 4: Same speaker + different voice does NOT merge
{
    const input = [
        { name: '可可蘿', voice: 'vo_101', words: '主人' },
        { name: '可可蘿', voice: 'vo_102', words: '早安' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 2, '同發言人但不同語音不應合併');
    assert.strictEqual(res.dialogueList[0].words, '主人');
    assert.strictEqual(res.dialogueList[1].words, '早安');
}

// Case 5: Current no-item-voice compatibility (A / voice_1 / hello + A / no voice / \nworld -> merge)
{
    const input = [
        { name: '凱留', voice: 'vo_201', words: '等一下！' },
        { name: '凱留', words: '\n你在做什麼？' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 1, '後者無語音標籤時應相容合併');
    assert.strictEqual(res.dialogueList[0].words, '等一下！\n你在做什麼？');
    assert.strictEqual(res.dialogueList[0].voice, 'vo_201', '合併後應保留前者的語音標籤');

    // 反向：前者無語音標籤，後者有語音標籤（依既有條件 !item.voice 為 false 且 last.voice !== item.voice，故不合併）
    const input2 = [
        { name: '凱留', words: '第一句' },
        { name: '凱留', voice: 'vo_202', words: '第二句' }
    ];
    const res2 = DialogueNormalizer.normalize(input2);
    assert.strictEqual(res2.dialogueList.length, 2, '前者無語音但後者有新語音時依既有邏輯不合併');
    assert.strictEqual(res2.dialogueList[0].words, '第一句');
    assert.strictEqual(res2.dialogueList[1].words, '第二句');
}

// Case 6: Special items preserved (still, background, movie)
{
    const input = [
        { type: 'background', id: 'bg_01' },
        { name: '佩可', words: '肚子餓了' },
        { type: 'still', id: 'still_01' },
        { type: 'movie', id: 'mov_01' },
        { name: '佩可', words: '吃飯了' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 5, '特殊項目應完整保留');
    assert.strictEqual(res.dialogueList[0].type, 'background');
    assert.strictEqual(res.dialogueList[2].type, 'still');
    assert.strictEqual(res.dialogueList[3].type, 'movie');
}

// Case 7: Speaker splitting (、, ＆, &, 和, 與)
{
    const input = [
        { name: '佩可＆可可蘿', words: '一起出發！' },
        { name: '凱留、雪菲', words: '等等我們' },
        { name: '優衣與怜', words: '破曉之星集合' },
        { name: '步未&莫妮卡', words: '巡邏' },
        { name: '真步和克莉絲提娜', words: '童話王國' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.deepStrictEqual(res.speakerNames, [
        '佩可', '可可蘿', '凱留', '雪菲', '優衣', '怜', '步未', '莫妮卡', '真步', '克莉絲提娜'
    ], '合稱名稱應依 first-seen 順序正確拆分');
}

// Case 8: Duplicate speaker dedup
{
    const input = [
        { name: '佩可', words: '好吃！' },
        { name: '可可蘿', words: '主人請用' },
        { name: '佩可', words: '再來一碗！' },
        { name: '可可蘿', words: '好的' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.deepStrictEqual(res.speakerNames, ['佩可', '可可蘿'], '發言人清單應唯一去重');
}

// Case 9: No input mutation (deepEqual snapshot & object references)
{
    const input = [
        { name: '佩可', voice: 'vo_1', words: ' 原始對白一 ' },
        { name: '佩可', voice: 'vo_1', words: ' 原始對白二 ' },
        { type: 'still', id: 'still_101', extra: { note: 'test' } },
        { name: '凱留', words: ' 原始對白三 ' }
    ];
    const inputSnapshot = JSON.stringify(input);

    const res = DialogueNormalizer.normalize(input);

    // 驗證輸入陣列與原始物件完全未被更動
    assert.strictEqual(JSON.stringify(input), inputSnapshot, 'normalize 執行後輸入陣列與物件不得被修改');

    // 驗證輸出物件與輸入物件非同一個 reference (shallow clone 保證)
    assert.notStrictEqual(res.dialogueList[0], input[0], '輸出對話物件不應與輸入物件共享相同 reference');
    assert.notStrictEqual(res.dialogueList[1], input[2], '輸出特殊物件不應與輸入特殊物件共享相同 reference');
}

// Case 10: Same speaker + same concrete unit_id -> merge
{
    const input = [
        { name: '可可蘿', words: '主人早安。', unit_id: 105911, voice: 'vo_1' },
        { name: '可可蘿', words: '\n今天也要加油喔。', unit_id: 105911, voice: 'vo_1' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 1, '同發言人且相同具體 unit_id 應正常合併');
    assert.strictEqual(res.dialogueList[0].words, '主人早安。\n今天也要加油喔。');
    assert.strictEqual(res.dialogueList[0].unit_id, 105911);
}

// Case 11: Same speaker + different concrete unit_id -> DO NOT merge
{
    const input = [
        { name: '可可蘿', words: '主人早安。', unit_id: 105911, voice: 'vo_1' },
        { name: '可可蘿', words: '衣服換好了。', unit_id: 105931, voice: 'vo_1' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 2, '同發言人但不同具體 unit_id 必須阻止合併以防資訊遺失');
    assert.strictEqual(res.dialogueList[0].unit_id, 105911);
    assert.strictEqual(res.dialogueList[1].unit_id, 105931);
}

// Case 12: Previous concrete + current missing -> legacy merge
{
    const input = [
        { name: '可可蘿', words: '主人早安。', unit_id: 105911 },
        { name: '可可蘿', words: '今天天氣很好。' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 1, '一端缺少 unit_id 時應維持 Legacy 合併行為');
    assert.strictEqual(res.dialogueList[0].unit_id, 105911, '應保留前一筆的 unit_id');
}

// Case 13: Previous missing + current concrete -> legacy merge
{
    const input = [
        { name: '可可蘿', words: '主人早安。' },
        { name: '可可蘿', words: '今天天氣很好。', unit_id: 105911 }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 1, '前一筆缺少 unit_id 但相容時應維持 Legacy 合併行為');
}

// Case 14: Both missing unit_id -> legacy merge
{
    const input = [
        { name: '可可蘿', words: '主人早安。' },
        { name: '可可蘿', words: '今天天氣很好。' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 1, '兩端均無 unit_id 時應維持 Legacy 合併行為');
}

// Case 15: Numeric string concrete IDs
{
    const input = [
        { name: '可可蘿', words: '主人早安。', unit_id: '105911' },
        { name: '可可蘿', words: '衣服換好了。', unit_id: '105931' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 2, '數字字串 unit_id 亦應正確判定為具體衝突並阻止合併');
    assert.strictEqual(res.dialogueList[0].unit_id, '105911', '原始資料格式應完整保留');
    assert.strictEqual(res.dialogueList[1].unit_id, '105931', '原始資料格式應完整保留');
}

// Case 16: Invalid / zero IDs treated as non-concrete (no conflict)
{
    const input = [
        { name: '可可蘿', words: '第一句', unit_id: 0 },
        { name: '可可蘿', words: '第二句', unit_id: 'invalid_id' },
        { name: '可可蘿', words: '第三句', unit_id: '' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 1, '非正整數 ID 視為 non-concrete，維持 Legacy 合併');
}

// Case 17: Chain merge 1001 -> 1002 -> 1002
{
    const input = [
        { name: '可可蘿', words: '台詞 1', unit_id: 105911 },
        { name: '可可蘿', words: '台詞 2', unit_id: 105931 },
        { name: '可可蘿', words: '\n台詞 3', unit_id: 105931 }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 2, '鏈式切換應精確切成 2 筆');
    assert.strictEqual(res.dialogueList[0].unit_id, 105911);
    assert.strictEqual(res.dialogueList[0].words, '台詞 1');
    assert.strictEqual(res.dialogueList[1].unit_id, 105931);
    assert.strictEqual(res.dialogueList[1].words, '台詞 2\n台詞 3');
}

console.log('DialogueNormalizer tests passed.');
