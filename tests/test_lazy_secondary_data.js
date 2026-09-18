'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../dashboard/map.js'), 'utf8');

function between(start, end) {
    const s = source.indexOf(start);
    const e = source.indexOf(end, s + start.length);
    assert.ok(s >= 0 && e > s, `missing source range: ${start}`);
    return source.slice(s, e);
}

const coreLoad = between('async _loadDataInternal() {', 'async ensureAppearanceMap() {');

// Large/secondary payloads must not block the general Story Map data preload.
assert.ok(!coreLoad.includes('ensureMetadataLoaded'),
    'official_story_metadata must stay lazy until a story synopsis is requested');
assert.ok(!coreLoad.includes("story/speaker_appearance.json"),
    'speaker appearance data must stay out of core preload');
assert.ok(!coreLoad.includes("data/movie_links.json"),
    'movie links must stay out of core preload');

// Independent core services should start together.
assert.match(coreLoad, /await Promise\.all\(\[/,
    'ChapterDataService and AvatarService should initialize in parallel');

// Feature entry points own their secondary data.
const appearanceLoader = between('async ensureAppearanceMap() {', 'async ensureMovieLinks() {');
assert.match(appearanceLoader, /story\/speaker_appearance\.json/);

const movieLoader = between('async ensureMovieLinks() {', 'groupStories() {');
assert.match(movieLoader, /data\/movie_links\.json/);

const movieOpen = between('async openMoviePopup(movieId) {', 'closeMoviePopup() {');
assert.match(movieOpen, /await this\.ensureMovieLinks\(\)/);

const modalOpen = between('async showCharaModal(charaName, unitId = null) {', 'jumpToStory(storyId');
assert.match(modalOpen, /await this\.ensureAppearanceMap\(\)/);

const speakerBranch = source.slice(
    source.indexOf("if (this.activeTabType === 'speaker')"),
    source.indexOf("if (this.activeTabType === 'event')")
);
assert.match(speakerBranch, /await this\.ensureAppearanceMap\(\)/);

console.log('✅ Lazy secondary-data source contract passed');
