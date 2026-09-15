const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const { webcrypto, createHash } = require('node:crypto');
const source = fs.readFileSync(path.join(__dirname, '../dashboard/db.js'), 'utf8');
const bytes = n => Uint8Array.of(n, 2, 3, 4).buffer;
const versionOf = buffer => 'hash_' + createHash('sha256').update(Buffer.from(buffer)).digest('hex').slice(0, 12);

function setup({ old, downloaded = bytes(1), failDownload = false, failSave = false, corrupt = false } = {}) {
    const expected = bytes(1);
    const version = versionOf(expected);
    const calls = { saved: [], downloads: [], closed: 0 };
    class Database {
        constructor(data) { if (data[0] === 255) throw new Error('corrupt'); }
        close() { calls.closed++; }
    }
    const context = vm.createContext({
        window: {}, console: { log() {}, warn() {}, error() {} },
        localStorage: { setItem() { throw new Error('storage blocked'); } },
        initSqlJs: async () => ({ Database }), crypto: webcrypto,
        setTimeout, clearTimeout, AbortSignal, Uint8Array,
        fetch: async () => ({ ok: true, json: async () => ({ tw_size: 4, db_version: version }) })
    });
    vm.runInContext(source, context);
    const db = context.window.PCRDatabase;
    db.verifyDatabase = () => !corrupt;
    db.loadFromIDB = async () => old;
    db.removeFromIDB = async () => assert.fail('must not erase old release');
    db.downloadDB = async url => {
        calls.downloads.push(url);
        if (failDownload) throw new Error('offline');
        return downloaded;
    };
    db.saveToIDB = async (key, record) => {
        if (failSave) throw new Error('quota exceeded');
        calls.saved.push({ key, record });
    };
    return { db, calls, version };
}

test('matching atomic cache loads without download despite blocked localStorage', async () => {
    const old = { format: 2, version: versionOf(bytes(1)), buffer: bytes(1) };
    const { db, calls } = setup({ old });
    assert.ok(await db.initDatabase());
    assert.equal(calls.downloads.length, 0);
});

test('failed replacement preserves old release and never fetches a mirror', async () => {
    const { db, calls } = setup({ old: { format: 2, version: 'old', buffer: bytes(2) }, failDownload: true });
    await assert.rejects(db.initDatabase(), /offline/);
    assert.equal(calls.saved.length, 0);
    assert.equal(calls.downloads.length, 1);
    assert.match(calls.downloads[0], /^\.\/redive_tw.db\?v=hash_/);
});

test('same-size wrong release is rejected before opening or saving', async () => {
    const { db, calls } = setup({ downloaded: bytes(2) });
    await assert.rejects(db.initDatabase(), /版本不一致/);
    assert.equal(db.db, null);
    assert.equal(calls.saved.length, 0);
});

test('storage quota failure leaves verified database usable', async () => {
    const { db } = setup({ failSave: true });
    const result = await db.initDatabase();
    assert.ok(result);
    assert.match(db.cacheWarning, /本次仍可閱讀/);
    assert.equal(await db.initDatabase(), result);
});

test('legacy bytes are reused only after release hash validation', async () => {
    const { db, calls } = setup({ old: bytes(2) });
    await db.initDatabase();
    assert.equal(calls.downloads.length, 1);
    assert.equal(calls.saved[0].record.format, 2);
    assert.equal(calls.saved[0].record.version, versionOf(bytes(1)));
});

test('invalid schema closes database and is not cached', async () => {
    const { db, calls } = setup({ corrupt: true });
    await assert.rejects(db.initDatabase(), /格式有誤/);
    assert.equal(db.db, null);
    assert.equal(calls.closed, 1);
    assert.equal(calls.saved.length, 0);
});
