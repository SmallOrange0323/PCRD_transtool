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

// Case 3: Same speaker + same voice merges
{
    const input = [
        { name: '佑樹', voice: 'vo_001', words: 'hello' },
        { name: '佑樹', voice: 'vo_001', words: 'world' }
    ];
    const res = DialogueNormalizer.normalize(input);
    assert.strictEqual(res.dialogueList.length, 1, '同發言人同語音應合併為一筆');
    assert.strictEqual(res.dialogueList[0].words, 'hello\nworld');
    assert.strictEqual(res.dialogueList[0].voice, 'vo_001');
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

// Case 5: Current no-item-voice compatibility (A / voice_1 / hello + A / no voice / world -> merge)
{
    const input = [
        { name: '凱留', voice: 'vo_201', words: '等一下！' },
        { name: '凱留', words: '你在做什麼？' }
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

console.log('DialogueNormalizer tests passed.');
