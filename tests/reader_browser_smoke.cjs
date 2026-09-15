// Run against a local server: NODE_PATH=<Playwright installation> node tests/reader_browser_smoke.cjs
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const fs = require('node:fs');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.READER_BROWSER || 'msedge' });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        // External artwork is irrelevant to navigation; keep this test local.
        await context.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => { errors.push(error.message); console.error('PAGE ERROR:', error.message); });
        const base = process.env.READER_TEST_URL || 'http://127.0.0.1:8765/story_map.html';
        await page.goto(base + '#story=1001001&line=10');
        await page.waitForFunction(() => window.ReaderNavigation?.readyStoryId === 1001001, null, { timeout: 30000 });
        assert.equal(await page.locator('#dialogue-board [data-dialogue-index]').count() > 10, true);
        assert.equal(await page.evaluate(() => QuestMapModule.currentView), 'list');
        await page.locator('[data-dialogue-index="10"]').scrollIntoViewIfNeeded();
        await page.evaluate(() => ReaderNavigation.savePosition());
        const saved = await page.evaluate(() => ReaderNavigation.readSaved());
        assert.equal(saved.storyId, 1001001);
        assert.equal(await page.locator('#reader-resume').isEnabled(), true);
        const nextId = await page.evaluate(() => QuestMapModule.getNextStoryId());
        assert.ok(nextId);
        await page.evaluate(() => QuestMapModule.toNextStory());
        await page.waitForFunction(id => ReaderNavigation.readyStoryId === id, nextId);
        await page.goBack();
        await page.waitForFunction(() => ReaderNavigation.readyStoryId === 1001001);
        await page.reload();
        await page.waitForFunction(() => ReaderNavigation.readyStoryId === 1001001);
        await page.locator('#loading-overlay').waitFor({ state: 'hidden' });
        assert.equal(await page.evaluate(() => QuestMapModule.directoryLevel), 'level2');
        await page.screenshot({ path: path.join(os.tmpdir(), 'pcrd-reader-desktop.png') });

        // Persist progress through exit, reload the menu, then resume explicitly.
        await page.evaluate(() => { ReaderNavigation.savePosition(); QuestMapModule.exitReader(); });
        await page.reload();
        await page.waitForFunction(() => !!ReaderNavigation.map);
        await page.locator('#loading-overlay').waitFor({ state: 'hidden' });
        assert.equal(await page.evaluate(() => QuestMapModule.activeStoryId), null);
        await page.locator('#reader-resume').click();
        await page.waitForFunction(() => ReaderNavigation.readyStoryId === 1001001);

        // Exercise routing across categories using locally available episodes.
        const stories = await page.evaluate(() => [...QuestMapModule.stories, ...QuestMapModule.eventStories].map(s => ({ id: s.id, type: s.isEvent ? 'event' : s.type })));
        const routed = [];
        for (const type of ['main', 'event', 'guild', 'tower']) {
            const story = stories.find(s => s.type === type && fs.existsSync(path.join(__dirname, `../dashboard/story/${s.id}.json`)));
            assert.ok(story, `Missing local fixture for ${type}`);
            console.log('Routing', story);
            await page.evaluate(id => ReaderNavigation.open({ storyId: id, line: 0 }), story.id);
            try { await page.waitForFunction(id => ReaderNavigation.readyStoryId === id, story.id); }
            catch (error) {
                console.log(await page.evaluate(() => ({ active: QuestMapModule.activeStoryId, ready: ReaderNavigation.readyStoryId, loading: QuestMapModule.isLoadingDialogue, board: document.getElementById('dialogue-board')?.textContent.slice(0, 200), status: document.getElementById('reader-navigation-status')?.textContent })));
                throw error;
            }
            assert.equal(await page.evaluate(() => QuestMapModule.activeTabType), type);
            routed.push(story);
        }
        await page.evaluate(() => ReaderNavigation.open({ storyId: 1001001, line: 10 }));
        await page.waitForFunction(() => ReaderNavigation.readyStoryId === 1001001);

        await page.setViewportSize({ width: 390, height: 844 });
        await page.reload();
        await page.waitForFunction(() => ReaderNavigation.readyStoryId === 1001001);
        const details = page.locator('.mobile-official-synopsis');
        assert.equal(await details.getAttribute('open'), null);
        await details.locator('summary').click();
        await page.waitForFunction(() => document.getElementById('official-synopsis-content').textContent !== '正在載入官方大綱…');
        assert.equal(await page.locator('#btn-next-story').evaluate(el => el.tagName), 'BUTTON');
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        await page.screenshot({ path: path.join(os.tmpdir(), 'pcrd-reader-mobile.png') });
        if (overflow) console.log(await page.evaluate(() => [...document.querySelectorAll('body *')].filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(0, 12).map(el => ({ tag: el.tagName, class: el.className, right: el.getBoundingClientRect().right }))));
        assert.equal(overflow, false, 'Mobile page must not overflow horizontally');
        assert.deepEqual(errors, [], 'No uncaught browser errors');
        console.log(JSON.stringify({ passed: true, nextId, saved, routed, screenshots: [path.join(os.tmpdir(), 'pcrd-reader-desktop.png'), path.join(os.tmpdir(), 'pcrd-reader-mobile.png')] }));
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
