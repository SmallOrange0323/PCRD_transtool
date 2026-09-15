'use strict';

const assert = require('assert');
const path = require('path');

global.window = global;
require(path.resolve(__dirname, '../dashboard/media-service.js'));

const MediaService = global.MediaService;
assert(MediaService, 'MediaService must be available');

function makeDeferredAudio(src) {
    let resolvePlay;
    const audio = {
        src,
        paused: true,
        ended: false,
        currentTime: 0,
        onended: null,
        onerror: null,
        play() {
            this.paused = false;
            return new Promise(resolve => { resolvePlay = resolve; });
        },
        pause() {
            this.paused = true;
        },
        resolvePlay() {
            if (resolvePlay) resolvePlay();
        }
    };
    return audio;
}

async function flush() {
    await new Promise(resolve => setImmediate(resolve));
}

(async () => {
    const originalAudio = global.Audio;
    try {
        // Case 1: a stale onerror callback captured before stop must not retry.
        let created = 0;
        let firstAudio;
        global.Audio = function(src) {
            created++;
            firstAudio = makeDeferredAudio(src);
            return firstAudio;
        };

        MediaService.stopVoice();
        MediaService.playVoiceWithOptions('vo_adv_stale_error_000');
        assert.strictEqual(created, 1, 'initial playback should create one Audio');
        const staleOnError = firstAudio.onerror;
        assert.strictEqual(typeof staleOnError, 'function', 'onerror should be installed before stop');

        MediaService.stopVoice();
        staleOnError();
        await flush();

        assert.strictEqual(created, 1, 'stale onerror must not create a CDN retry Audio');
        assert.strictEqual(MediaService._currentAudio, null, 'stale onerror must not restore current audio');

        // Case 2: an old onended callback captured before a new session must not fire.
        let oldEndedCalls = 0;
        let newStartCalls = 0;
        let oldAudio;
        let newAudio;
        created = 0;
        global.Audio = function(src) {
            created++;
            const audio = makeDeferredAudio(src);
            if (created === 1) oldAudio = audio;
            else newAudio = audio;
            return audio;
        };

        MediaService.stopVoice();
        MediaService.playVoiceWithOptions('vo_adv_stale_ended_old', {
            onEnded: () => { oldEndedCalls++; }
        });
        const staleOnEnded = oldAudio.onended;
        assert.strictEqual(typeof staleOnEnded, 'function', 'onended should be installed before new session');

        MediaService.playVoiceWithOptions('vo_adv_stale_ended_new', {
            onStart: () => { newStartCalls++; }
        });
        newAudio.resolvePlay();
        await flush();
        assert.strictEqual(newStartCalls, 1, 'new session should start normally');

        staleOnEnded();
        await flush();

        assert.strictEqual(oldEndedCalls, 0, 'stale onended callback must be ignored');
        assert.strictEqual(MediaService._currentAudio, newAudio, 'stale onended must not disturb the new session');

        console.log('MediaService stale callback regression tests passed.');
    } finally {
        MediaService.stopVoice();
        global.Audio = originalAudio;
    }
})().catch(error => {
    console.error(error);
    process.exit(1);
});
