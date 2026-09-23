'use strict';

const assert = require('assert');
const path = require('path');

global.window = global;
global.document = {
    getElementById: () => ({ querySelector: () => null, querySelectorAll: () => [] })
};

require(path.resolve(__dirname, '../dashboard/media-service.js'));
require(path.resolve(__dirname, '../dashboard/auto-voice-controller.js'));

const MediaService = global.MediaService;
const AutoVoiceController = global.AutoVoiceController;

const originalAudio = global.Audio;
const originalTimeout = MediaService.VOICE_CANDIDATE_TIMEOUT_MS;
const audios = [];
let plans = [];

class ControlledAudio {
    constructor(src) {
        this.src = src;
        this.paused = true;
        this.ended = false;
        this.currentTime = 1;
        this.onended = null;
        this.onerror = null;
        this.playCalls = 0;
        this._plan = plans.shift() || 'resolve';
        this._deferred = null;
        audios.push(this);
    }

    play() {
        this.playCalls++;
        this.paused = false;
        if (this._plan === 'not-allowed') {
            const error = new Error('autoplay blocked');
            error.name = 'NotAllowedError';
            return Promise.reject(error);
        }
        if (this._plan === 'pending') {
            return new Promise((resolve, reject) => { this._deferred = { resolve, reject }; });
        }
        if (this._plan === 'resolve-then-pending') {
            if (this.playCalls === 1) return Promise.resolve();
            return new Promise((resolve, reject) => { this._deferred = { resolve, reject }; });
        }
        return Promise.resolve();
    }

    pause() {
        this.paused = true;
    }

    emitError() {
        if (typeof this.onerror === 'function') this.onerror();
    }

    rejectPending(error) {
        if (this._deferred) this._deferred.reject(error);
    }
}

global.Audio = ControlledAudio;

const flush = () => new Promise(resolve => setImmediate(resolve));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const reset = () => {
    MediaService.stopVoice();
    AutoVoiceController.stop();
    audios.length = 0;
    plans = [];
};

(async () => {
    try {
        // 1 + 2: pause 後 error 只記住 retry；resume 才且只會啟動下一候選一次。
        reset();
        let starts = 0;
        MediaService.playVoiceWithOptions('vo_adv_1001001_001', { onStart: () => { starts++; } });
        await flush();
        const cloudflare = audios[0];
        assert.strictEqual(starts, 1, 'Cloudflare should start before pause');
        assert.strictEqual(MediaService.pauseVoice(), true);
        cloudflare.emitError();
        await flush();
        assert.strictEqual(audios.length, 1, 'paused failure must not create PRCN Audio');
        assert.strictEqual(starts, 1, 'paused retry must not call onStart');
        const resumePromise = MediaService.resumeVoice();
        await resumePromise;
        assert.strictEqual(audios.length, 2, 'resume should create exactly one PRCN candidate');
        assert.ok(audios[1].src.includes('prcn-sound.estertion.win'), 'resume must continue at PRCN');
        assert.strictEqual(starts, 2, 'PRCN should start only after resume');

        // 3: stale resume rejection cannot stop a newer AUTO session.
        reset();
        plans = ['resolve-then-pending', 'resolve'];
        const dialogue = [{ voice: 'vo_adv_1001001_001' }];
        AutoVoiceController.start(dialogue, 1001001);
        await flush();
        const oldAudio = audios[0];
        AutoVoiceController.pause();
        AutoVoiceController.resume();
        AutoVoiceController.start([{ voice: 'vo_adv_1001002_001' }], 1001002);
        const notAllowed = new Error('stale autoplay rejection');
        notAllowed.name = 'NotAllowedError';
        oldAudio.rejectPending(notAllowed);
        await flush();
        assert.strictEqual(AutoVoiceController.state, 'PLAYING', 'stale resume rejection must not stop new AUTO session');
        assert.strictEqual(AutoVoiceController.storyId, 1001002, 'new AUTO session must remain active');

        // 4: a candidate that never resolves/errors must advance after its lifecycle timeout.
        reset();
        MediaService.VOICE_CANDIDATE_TIMEOUT_MS = 20;
        plans = ['pending', 'resolve'];
        MediaService.playVoiceWithOptions('vo_adv_1001003_001');
        await wait(40);
        assert.strictEqual(audios.length, 2, 'timeout must create the next candidate');
        assert.ok(audios[1].src.includes('prcn-sound.estertion.win'), 'timeout fallback must use PRCN');

        // 5: a timeout from the old session cannot affect the new one.
        reset();
        plans = ['pending', 'resolve'];
        MediaService.playVoiceWithOptions('vo_adv_old_000000');
        MediaService.playVoiceWithOptions('vo_adv_new_000000');
        await wait(40);
        assert.strictEqual(audios.length, 2, 'old timeout must not create a retry in the new session');
        assert.ok(audios[1].src.includes('vo_adv_new_000000'), 'new session audio must remain current');

        // 6: stop clears timeout and makes pending retry work inert.
        reset();
        plans = ['pending'];
        MediaService.playVoiceWithOptions('vo_adv_stop_000000');
        MediaService.stopVoice();
        await wait(40);
        assert.strictEqual(audios.length, 1, 'stop must prevent timeout retry');
        assert.strictEqual(MediaService.getCurrentAudio(), null, 'stop must clear current Audio');
        assert.strictEqual(MediaService._candidateTimeoutId, null, 'stop must clear candidate timeout');

        // 7: autoplay policy rejection is terminal and never falls back to another CDN.
        reset();
        plans = ['not-allowed'];
        let notAllowedErrors = 0;
        MediaService.playVoiceWithOptions('vo_adv_policy_000000', {
            onError: error => {
                if (error.name === 'NotAllowedError' && error.voiceFailureType === 'autoplay-blocked') notAllowedErrors++;
            }
        });
        await flush();
        assert.strictEqual(audios.length, 1, 'NotAllowedError must not fall back to PRCN/REDIVE');
        assert.strictEqual(notAllowedErrors, 1, 'NotAllowedError should retain structured failure type');

        console.log('Voice lifecycle hardening tests passed.');
    } finally {
        MediaService.VOICE_CANDIDATE_TIMEOUT_MS = originalTimeout;
        reset();
        global.Audio = originalAudio;
    }
})().catch(error => {
    console.error(error);
    process.exit(1);
});
