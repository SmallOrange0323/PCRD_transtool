'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const mapSource = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');
const cssSource = fs.readFileSync(path.join(__dirname, '../dashboard/style.css'), 'utf8');

const helperStart = mapSource.indexOf('getCharaCardHtml(chName, stories)');
const helperEnd = mapSource.indexOf('escapeHtml(str)', helperStart);
assert.ok(helperStart >= 0 && helperEnd > helperStart, 'character card helper must exist');

const helper = mapSource.slice(helperStart, helperEnd);

assert.match(helper, /<img[\s\S]*class="chara-card-image"/,
    'character cards must render a real image element');
assert.match(helper, /loading="lazy"/,
    'character card images must stay lazy-loaded');
assert.match(helper, /decoding="async"/,
    'character card images should decode asynchronously');
assert.match(helper, /src="\$\{localCardUrl\}"/,
    'local card asset must be the initial source');
assert.match(helper, /data-fallback-src="\$\{remoteCardUrl\}"/,
    'remote CDN must be retained only as fallback');
assert.match(helper, /handleCharaCardImageError\(this\)/,
    'image error must trigger fallback handling');

assert.match(mapSource, /dataset\.fallbackUsed === '1'/,
    'fallback handler must guard against retry loops');
assert.match(mapSource, /img\.src = fallbackSrc/,
    'fallback handler must switch source only after local failure');

assert.ok(!mapSource.includes("background-image: url('${localCardUrl}'), url('${remoteCardUrl}')"),
    'local and remote character cards must never be simultaneous CSS background layers');

const helperUses = (mapSource.match(/gridHtml \+= this\.getCharaCardHtml\(chName, stories\)/g) || []).length;
assert.equal(helperUses, 2,
    'both initial render and filtered grid refresh must use the same character-card helper');

assert.match(cssSource, /\.chara-card-image\s*\{[\s\S]*object-fit:\s*cover;/,
    'character card image styling must preserve cover layout');

console.log('✅ Character-card image loading contract passed');
