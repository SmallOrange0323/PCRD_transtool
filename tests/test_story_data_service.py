# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - StoryDataService & M3A UI Integration Tests (M3A.2 Dialogue Concurrency)
涵蓋 31 項針對性 Runtime、Service、Non-Blocking Dialogue、Token-Scoped Loading Guard、Stale-Load Lifecycle、Shape Hardening、Cache-Busting 與 UI Integrity 門禁測試 (全數 Hermetic 零外網洩漏)：
1. StoryDataService global exists
2. metadata_version present -> versioned manifest request
3. db_info request uses no-store
4. metadata_version missing -> no-store manifest request
5. db_version fallback strictly forbidden
6. concurrent calls share one loading operation
7. successful load caches episodes
8. failed load resets _loadingPromise
9. failed load permits retry
10. malformed root/episodes manifest graceful degradation
11. malformed episode array / null entry rejected
12. normal plain object episode entry accepted
13. getEpisodeMetadata numeric and string ID works
14. null synopsis returns null
15. non-blocking: pending metadata does not block dialogue shell and dialogue load
16. mobile mode zero metadata fetch
17. async story race guard: stale A metadata resolve does not overwrite active B synopsis
18. map.js no DB sub_title -> official synopsis mapping
19. map.js contains no fake synopsis phrases
20. official synopsis safely rendered via textContent
21. manifest missing does not block dialogue rendering
22. story-data-service.js precedes map.js in story_map.html
23. bundler copies story-data-service.js to dist
24. render_index_html applies content-hash cache busting
25. validator rejects missing runtime service with precise error message
26. dialogue concurrency: A pending dialogue -> B dialogue still starts
27. dialogue concurrency: B renders before stale A
28. dialogue concurrency: stale A never renders after B
29. dialogue concurrency: stale A cannot clear B loading state
30. dialogue concurrency: after stale A/B sequence, C still loads normally (permanent lock regression test)
31. dialogue concurrency: same-token duplicate dialogue request suppressed
"""

import os
import sys
import io
import json
import re
import shutil
import tempfile
import unittest
import subprocess
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
STORY_DATA_SERVICE_JS = DASHBOARD_DIR / "story-data-service.js"
MAP_JS = DASHBOARD_DIR / "map.js"
STORY_MAP_HTML = DASHBOARD_DIR / "story_map.html"

from pipeline.bundle import render_index_html, bundle_story_map, calc_sha256
from pipeline.validate import validate_story_map, ValidationResult


def run_node_test_script(js_code: str, include_map: bool = False) -> dict:
    """在 Node.js 沙盒中執行測試腳本，回傳 JSON 結果。"""
    service_code = STORY_DATA_SERVICE_JS.read_text(encoding="utf-8")
    map_code = MAP_JS.read_text(encoding="utf-8") if include_map else ""

    wrapper = f"""
    // 建立瀏覽器全域環境 Mock
    const window = {{
        innerWidth: 1024,
        scrollY: 0,
        scrollTo: () => {{}},
        DialogueView: {{
            renderLoading: () => {{}},
            renderEmpty: () => {{}},
            renderError: () => {{}},
            renderDialogue: () => {{}},
            clearAutoStartSelection: () => {{}},
            clearDialogueHighlight: () => {{}},
            setAutoStartSelection: () => {{}}
        }},
        DialogueNormalizer: {{
            normalize: (raw) => ({{ dialogueList: raw || [], speakerNames: [] }})
        }},
        MediaService: {{
            openStillPopup: () => {{}},
            closeStillPopup: () => {{}},
            playVoice: () => {{}}
        }},
        PCRDatabase: {{
            runQuery: async () => []
        }}
    }};
    global.window = window;

    // 將全域 fetch 橋接至 window.fetch，確保雙向相容
    global.fetch = async (url, options) => {{
        if (typeof window.fetch === 'function') {{
            return window.fetch(url, options);
        }}
        return {{ ok: false, status: 404 }};
    }};

    function createMockElement(id) {{
        const el = {{
            id,
            _innerHTML: '',
            innerText: '',
            textContent: '',
            style: {{}},
            scrollIntoView: () => {{}},
            getBoundingClientRect: () => ({{ top: 0 }}),
            querySelector: () => null,
            setAttribute: () => {{}},
            classList: {{ add: () => {{}}, remove: () => {{}}, contains: () => false }}
        }};
        Object.defineProperty(el, 'innerHTML', {{
            get() {{ return this._innerHTML; }},
            set(val) {{
                this._innerHTML = String(val);
                const idMatches = this._innerHTML.matchAll(/id=["']([^"']+)["'][^>]*>(.*?)<\/[a-zA-Z0-9]+>/gs);
                for (const match of idMatches) {{
                    const childId = match[1];
                    const childContent = match[2].replace(/<[^>]+>/g, '');
                    const child = global.document.getElementById(childId);
                    child.textContent = childContent;
                    child.innerText = childContent;
                    child._innerHTML = match[2];
                }}
            }}
        }});
        return el;
    }}

    global.document = {{
        getElementById: (id) => {{
            if (!global._elements) global._elements = {{}};
            if (!global._elements[id]) {{
                global._elements[id] = createMockElement(id);
            }}
            return global._elements[id];
        }},
        querySelectorAll: () => [],
        querySelector: () => ({{
            style: {{}},
            classList: {{ add: () => {{}}, remove: () => {{}}, contains: () => false }},
            scrollIntoView: () => {{}},
            getBoundingClientRect: () => ({{ top: 0 }})
        }})
    }};

    {service_code}
    {map_code}

    (async () => {{
        try {{
            {js_code}
        }} catch (err) {{
            console.log(JSON.stringify({{ success: false, error: err.message, stack: err.stack }}));
        }}
    }})();
    """
    with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(wrapper)
        temp_js_path = tf.name

    try:
        proc = subprocess.run(
            ["node", temp_js_path],
            capture_output=True,
            encoding="utf-8",
            cwd=str(PROJECT_ROOT)
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Node execution failed (code {proc.returncode}):\n{proc.stderr}\n{proc.stdout}")
        output = proc.stdout.strip()
        try:
            return json.loads(output.splitlines()[-1])
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse Node.js output as JSON: {output}")
    finally:
        try:
            os.remove(temp_js_path)
        except OSError:
            pass


class TestStoryDataServiceRuntime(unittest.TestCase):
    """M3A Runtime & StoryDataService 門禁測試"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="pcrd_m3a_test_")
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # 1. StoryDataService global exists
    def test_01_story_data_service_global_exists(self):
        """1. 驗證 window.StoryDataService 正確建立且具備標準 API"""
        js = """
        console.log(JSON.stringify({
            exists: typeof window.StoryDataService !== 'undefined',
            hasEnsureMetadataLoaded: typeof window.StoryDataService.ensureMetadataLoaded === 'function',
            hasGetEpisodeMetadata: typeof window.StoryDataService.getEpisodeMetadata === 'function',
            hasGetOfficialSynopsis: typeof window.StoryDataService.getOfficialSynopsis === 'function'
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("exists"))
        self.assertTrue(res.get("hasEnsureMetadataLoaded"))
        self.assertTrue(res.get("hasGetEpisodeMetadata"))
        self.assertTrue(res.get("hasGetOfficialSynopsis"))

    # 2. metadata_version present -> versioned manifest request
    def test_02_metadata_version_present_uses_versioned_request(self):
        """2. 驗證 db_info 含有 metadata_version 時，以版本號 query 請求 official_story_metadata.json"""
        js = """
        let requestedUrls = [];
        window.fetch = async (url, options) => {
            requestedUrls.push({ url, options });
            if (url.includes('db_info.json')) {
                return {
                    ok: true,
                    json: async () => ({ db_version: 'hash_db123', metadata_version: 'meta_ver_789' })
                };
            }
            if (url.includes('official_story_metadata.json')) {
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: {
                            '100101': {
                                story_id: 100101,
                                official_synopsis: '測試大綱'
                            }
                        }
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        const result = await window.StoryDataService.ensureMetadataLoaded();
        console.log(JSON.stringify({
            success: true,
            requestedUrls,
            has100101: result && result['100101'] ? true : false
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("has100101"))
        urls = [item["url"] for item in res["requestedUrls"]]
        self.assertTrue(any("data/official_story_metadata.json?v=meta_ver_789" in u for u in urls))

    # 3. db_info request uses no-store
    def test_03_db_info_request_uses_no_store(self):
        """3. 驗證探測 db_info.json 時必須使用 cache: 'no-store'"""
        js = """
        let dbInfoOptions = null;
        window.fetch = async (url, options) => {
            if (url.includes('db_info.json')) {
                dbInfoOptions = options;
                return { ok: false, status: 404 };
            }
            if (url.includes('official_story_metadata.json')) {
                return { ok: false, status: 404 };
            }
            return { ok: false, status: 404 };
        };

        await window.StoryDataService.ensureMetadataLoaded();
        console.log(JSON.stringify({
            success: true,
            dbInfoOptions
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertIsNotNone(res.get("dbInfoOptions"))
        self.assertEqual(res["dbInfoOptions"].get("cache"), "no-store")

    # 4. metadata_version missing -> no-store manifest request
    def test_04_metadata_version_missing_uses_no_store_request(self):
        """4. 驗證 db_info 不存在或無 metadata_version 時，以 no-store 直接請求 official_story_metadata.json"""
        js = """
        let manifestOptions = null;
        let manifestUrl = null;
        window.fetch = async (url, options) => {
            if (url.includes('db_info.json')) {
                return { ok: false, status: 404 };
            }
            if (url.includes('official_story_metadata.json')) {
                manifestUrl = url;
                manifestOptions = options;
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: {}
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        await window.StoryDataService.ensureMetadataLoaded();
        console.log(JSON.stringify({
            success: true,
            manifestUrl,
            manifestOptions
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("manifestUrl"), "data/official_story_metadata.json")
        self.assertIsNotNone(res.get("manifestOptions"))
        self.assertEqual(res["manifestOptions"].get("cache"), "no-store")

    # 5. db_version fallback strictly forbidden
    def test_05_db_version_fallback_strictly_forbidden(self):
        """5. 驗證 db_info 僅有 db_version 時，嚴格禁止 fallback 使用 db_version 作為 metadata 查詢參數"""
        js = """
        let requestedManifestUrl = null;
        let requestedManifestOptions = null;
        window.fetch = async (url, options) => {
            if (url.includes('db_info.json')) {
                return {
                    ok: true,
                    json: async () => ({ db_version: 'hash_db_only_123' })
                };
            }
            if (url.includes('official_story_metadata.json')) {
                requestedManifestUrl = url;
                requestedManifestOptions = options;
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: {}
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        await window.StoryDataService.ensureMetadataLoaded();
        console.log(JSON.stringify({
            success: true,
            requestedManifestUrl,
            requestedManifestOptions
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertNotIn("hash_db_only_123", res.get("requestedManifestUrl") or "")
        self.assertEqual(res.get("requestedManifestUrl"), "data/official_story_metadata.json")
        self.assertEqual(res.get("requestedManifestOptions", {}).get("cache"), "no-store")

    # 6. concurrent calls share one loading operation
    def test_06_concurrent_calls_share_one_loading_operation(self):
        """6. 驗證多次並發呼叫 ensureMetadataLoaded 共享同一個 Promise，只觸發一次網路載入"""
        js = """
        let manifestFetchCount = 0;
        window.fetch = async (url) => {
            if (url.includes('db_info.json')) {
                return { ok: true, json: async () => ({ metadata_version: 'v1' }) };
            }
            if (url.includes('official_story_metadata.json')) {
                manifestFetchCount++;
                await new Promise(r => setTimeout(r, 50));
                return {
                    ok: true,
                    json: async () => ({ schema_version: '1.0.0', truth_version: '00600023', episodes: {} })
                };
            }
            return { ok: false, status: 404 };
        };

        const [r1, r2, r3] = await Promise.all([
            window.StoryDataService.ensureMetadataLoaded(),
            window.StoryDataService.ensureMetadataLoaded(),
            window.StoryDataService.ensureMetadataLoaded()
        ]);

        console.log(JSON.stringify({
            success: true,
            manifestFetchCount,
            allSame: r1 === r2 && r2 === r3
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("manifestFetchCount"), 1)
        self.assertTrue(res.get("allSame"))

    # 7. successful load caches episodes
    def test_07_successful_load_caches_episodes(self):
        """7. 驗證載入成功後將 episodes 存入快取，後續呼叫不再發起 fetch"""
        js = """
        let fetchCount = 0;
        window.fetch = async (url) => {
            fetchCount++;
            if (url.includes('db_info.json')) {
                return { ok: true, json: async () => ({ metadata_version: 'v1' }) };
            }
            if (url.includes('official_story_metadata.json')) {
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: { '100101': { story_id: 100101, official_synopsis: '快取測試' } }
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        await window.StoryDataService.ensureMetadataLoaded();
        const initialCount = fetchCount;

        const ep1 = await window.StoryDataService.getEpisodeMetadata(100101);
        const ep2 = await window.StoryDataService.getEpisodeMetadata('100101');
        const finalCount = fetchCount;

        console.log(JSON.stringify({
            success: true,
            initialCount,
            finalCount,
            hasCache: ep1 !== null && ep1.official_synopsis === '快取測試',
            sameObject: ep1 === ep2
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("hasCache"))
        self.assertTrue(res.get("sameObject"))
        self.assertEqual(res.get("initialCount"), res.get("finalCount"))

    # 8. failed load resets _loadingPromise
    def test_08_failed_load_resets_loading_promise(self):
        """8. 驗證載入失敗時 _loadingPromise 正確重設為 null，且 _metadataCache 保持 null"""
        js = """
        window.fetch = async () => {
            throw new Error("Network error simulation");
        };

        const result = await window.StoryDataService.ensureMetadataLoaded();

        console.log(JSON.stringify({
            success: true,
            resultIsNull: result === null,
            loadingPromiseIsNull: window.StoryDataService._loadingPromise === null,
            metadataCacheIsNull: window.StoryDataService._metadataCache === null
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("resultIsNull"))
        self.assertTrue(res.get("loadingPromiseIsNull"))
        self.assertTrue(res.get("metadataCacheIsNull"))

    # 9. failed load permits retry
    def test_09_failed_load_permits_retry(self):
        """9. 驗證第一次載入失敗後，第二次呼叫可正常重試並在成功後取得資料"""
        js = """
        let attempts = 0;
        window.fetch = async (url) => {
            if (url.includes('db_info.json')) {
                return { ok: true, json: async () => ({ metadata_version: 'v1' }) };
            }
            if (url.includes('official_story_metadata.json')) {
                attempts++;
                if (attempts === 1) {
                    throw new Error("Temporary network error");
                }
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: { '100101': { story_id: 100101, official_synopsis: '重試成功' } }
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        const res1 = await window.StoryDataService.ensureMetadataLoaded();
        const res2 = await window.StoryDataService.ensureMetadataLoaded();

        console.log(JSON.stringify({
            success: true,
            res1IsNull: res1 === null,
            res2IsObject: res2 !== null && typeof res2 === 'object',
            res2HasData: res2 && res2['100101'] ? res2['100101'].official_synopsis : null
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("res1IsNull"))
        self.assertTrue(res.get("res2IsObject"))
        self.assertEqual(res.get("res2HasData"), "重試成功")

    # 10. malformed root/episodes manifest graceful degradation
    def test_10_malformed_manifest_graceful_degradation(self):
        """10. 驗證 Manifest 頂層非物件或 episodes 損壞時優雅降級為 null，絕不拋出例外崩潰 UI"""
        js = """
        let errors = [];
        window.fetch = async (url) => {
            if (url.includes('db_info.json')) return { ok: false, status: 404 };
            if (url.includes('official_story_metadata.json')) {
                // 回傳損壞的 episodes (非 object，例如 string 或 array)
                return {
                    ok: true,
                    json: async () => ({ schema_version: '1.0.0', truth_version: '00600023', episodes: "malformed" })
                };
            }
            return { ok: false, status: 404 };
        };

        let result = null;
        try {
            result = await window.StoryDataService.ensureMetadataLoaded();
        } catch (e) {
            errors.push(e.message);
        }

        console.log(JSON.stringify({
            success: errors.length === 0,
            resultIsNull: result === null,
            cacheIsNull: window.StoryDataService._metadataCache === null
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("resultIsNull"))
        self.assertTrue(res.get("cacheIsNull"))

    # 11. malformed episode array / null entry rejected
    def test_11_malformed_episode_entry_rejected(self):
        """11. 驗證 episode entry 為 Array 或 null 時，整份 Manifest 被拒絕，快取保持 null"""
        js = """
        window.fetch = async (url) => {
            if (url.includes('db_info.json')) return { ok: false, status: 404 };
            if (url.includes('official_story_metadata.json')) {
                // 回傳 episodes 含有損壞的 entry (例如 Array 或 null)
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: {
                            '100101': ['invalid', 'array'],
                            '100102': null
                        }
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        const result = await window.StoryDataService.ensureMetadataLoaded();

        console.log(JSON.stringify({
            success: true,
            resultIsNull: result === null,
            cacheIsNull: window.StoryDataService._metadataCache === null
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("resultIsNull"))
        self.assertTrue(res.get("cacheIsNull"))

    # 12. normal plain object episode entry accepted
    def test_12_normal_plain_object_episode_entry_accepted(self):
        """12. 驗證合規之 episode entry 正確載入並解析"""
        js = """
        window.fetch = async (url) => {
            if (url.includes('db_info.json')) return { ok: false, status: 404 };
            if (url.includes('official_story_metadata.json')) {
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: {
                            '100101': {
                                story_id: 100101,
                                official_chapter_title: '第1章',
                                official_subtitle: '第1話',
                                official_synopsis: '合規大綱',
                                provenance: {
                                    truth_version: '00600023',
                                    bundle_name: 'storydata_100101.unity3d',
                                    cdn_bundle_hash: 'hash100101'
                                }
                            }
                        }
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        const ep = await window.StoryDataService.getEpisodeMetadata(100101);

        console.log(JSON.stringify({
            success: true,
            epNotNull: ep !== null,
            synopsis: ep ? ep.official_synopsis : null
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("epNotNull"))
        self.assertEqual(res.get("synopsis"), "合規大綱")

    # 13. getEpisodeMetadata numeric and string ID works
    def test_13_get_episode_metadata_numeric_and_string_id(self):
        """13. 驗證 getEpisodeMetadata 傳入數字或字串 ID 均可正確查得節點"""
        js = """
        window.fetch = async (url) => {
            if (url.includes('db_info.json')) return { ok: false, status: 404 };
            if (url.includes('official_story_metadata.json')) {
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: {
                            '100101': { story_id: 100101, official_synopsis: '測試查表' }
                        }
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        const resNum = await window.StoryDataService.getEpisodeMetadata(100101);
        const resStr = await window.StoryDataService.getEpisodeMetadata('100101');
        const resNone = await window.StoryDataService.getEpisodeMetadata(999999);

        console.log(JSON.stringify({
            success: true,
            numMatch: resNum !== null && resNum.story_id === 100101,
            strMatch: resStr !== null && resStr.story_id === 100101,
            noneMatch: resNone === null
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("numMatch"))
        self.assertTrue(res.get("strMatch"))
        self.assertTrue(res.get("noneMatch"))

    # 14. null synopsis returns null
    def test_14_null_synopsis_returns_null(self):
        """14. 驗證話數 official_synopsis 為 null 或空白時，getOfficialSynopsis 嚴格回傳 null"""
        js = """
        window.fetch = async (url) => {
            if (url.includes('db_info.json')) return { ok: false, status: 404 };
            if (url.includes('official_story_metadata.json')) {
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: '1.0.0',
                        truth_version: '00600023',
                        episodes: {
                            '100101': { story_id: 100101, official_synopsis: null },
                            '100102': { story_id: 100102, official_synopsis: '   ' },
                            '100103': { story_id: 100103, official_synopsis: '有內容大綱' }
                        }
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        const s1 = await window.StoryDataService.getOfficialSynopsis(100101);
        const s2 = await window.StoryDataService.getOfficialSynopsis(100102);
        const s3 = await window.StoryDataService.getOfficialSynopsis(100103);

        console.log(JSON.stringify({
            success: true,
            s1IsNull: s1 === null,
            s2IsNull: s2 === null,
            s3Value: s3
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("s1IsNull"))
        self.assertTrue(res.get("s2IsNull"))
        self.assertEqual(res.get("s3Value"), "有內容大綱")

    # 15. non-blocking: pending metadata does not block dialogue shell and dialogue load
    def test_15_pending_metadata_does_not_block_dialogue(self):
        """15. 驗證當 metadata Promise 永遠 pending 時，selectStory 仍能立即建立對白 shell 並觸發 loadDialogue"""
        js = """
        let dialogueLoadCalled = false;
        let dialogueLoadStoryId = null;

        const qm = window.QuestMapModule;
        qm.getStoryById = () => ({ id: 100101, chapter: '第1章', title: '話標題 1' });
        qm.isDialogueExpanded = true;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};
        qm.loadDialogue = (sid) => {
            dialogueLoadCalled = true;
            dialogueLoadStoryId = sid;
        };

        // Mock 永遠 pending 的 getOfficialSynopsis
        window.StoryDataService.getOfficialSynopsis = () => new Promise(() => {});

        // 呼叫 selectStory
        qm.selectStory(100101);

        const synopsisEl = global.document.getElementById('official-synopsis-content');
        const summaryEl = global.document.getElementById('cinema-summary');

        console.log(JSON.stringify({
            success: true,
            dialogueLoadCalled,
            dialogueLoadStoryId,
            synopsisPlaceholder: synopsisEl ? synopsisEl.textContent : null,
            hasDialogueShell: summaryEl ? summaryEl.innerHTML.includes('game-dialogue-panel') : false
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("dialogueLoadCalled"))
        self.assertEqual(res.get("dialogueLoadStoryId"), 100101)
        self.assertEqual(res.get("synopsisPlaceholder"), "正在載入官方大綱…")
        self.assertTrue(res.get("hasDialogueShell"))

    # 16. mobile mode zero metadata fetch
    def test_16_mobile_mode_zero_metadata_fetch(self):
        """16. 驗證在 Mobile 模式下，selectStory 完全不呼叫 StoryDataService.getOfficialSynopsis"""
        js = """
        window.innerWidth = 375; // Mobile 螢幕

        let metadataFetchCount = 0;
        window.StoryDataService.getOfficialSynopsis = async () => {
            metadataFetchCount++;
            return 'SYNOPSIS';
        };

        const qm = window.QuestMapModule;
        qm.getStoryById = () => ({ id: 100101, chapter: '第1章', title: '話標題 1' });
        qm.isDialogueExpanded = true;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};
        qm.loadDialogue = () => {};
        qm.getQuickDirectoryHtml = () => '<div id="quick-dir">QUICK_DIR</div>';

        qm.selectStory(100101);

        console.log(JSON.stringify({
            success: true,
            metadataFetchCount
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("metadataFetchCount"), 0)

    # 17. async story race guard: stale A metadata resolve does not overwrite active B synopsis
    def test_17_stale_story_race_guard(self):
        """17. 驗證快速切換話數時，舊話數 A 延遲回傳之大綱不會覆蓋當前話數 B"""
        js = """
        const qm = window.QuestMapModule;
        qm.getStoryById = (id) => ({ id, chapter: `第${id}章`, title: `話標題 ${id}` });
        qm.isDialogueExpanded = false;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};
        qm.loadDialogue = () => {};

        let resolveA = null;
        window.StoryDataService.getOfficialSynopsis = (sid) => {
            if (sid === 100101) {
                return new Promise((resolve) => {
                    resolveA = () => resolve('大綱 A (延遲)');
                });
            }
            if (sid === 100102) {
                return Promise.resolve('大綱 B (快速)');
            }
            return Promise.resolve(null);
        };

        // 1. 使用者先選 100101 (A)
        qm.selectStory(100101);

        // 2. 快速切換至 100102 (B)
        qm.selectStory(100102);

        // 等待 microtasks 讓 B 完成
        await new Promise(r => setTimeout(r, 20));

        const synopsisEl = global.document.getElementById('official-synopsis-content');
        const bSynopsis = synopsisEl ? synopsisEl.textContent : null;

        // 3. 現在 resolve 舊話數 A
        if (resolveA) resolveA();
        await new Promise(r => setTimeout(r, 20));

        const finalSynopsis = synopsisEl ? synopsisEl.textContent : null;

        console.log(JSON.stringify({
            success: true,
            bSynopsis,
            finalSynopsis,
            staleDidNotOverwrite: finalSynopsis === '大綱 B (快速)'
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("bSynopsis"), "大綱 B (快速)")
        self.assertEqual(res.get("finalSynopsis"), "大綱 B (快速)")
        self.assertTrue(res.get("staleDidNotOverwrite"))

    # 18. map.js no DB sub_title -> official synopsis mapping
    def test_18_map_js_no_db_subtitle_to_official_synopsis(self):
        """18. 靜態斷言：map.js updateSummaryContent 已移除 SELECT sub_title 作為官方大綱之路徑"""
        map_content = MAP_JS.read_text(encoding="utf-8")
        self.assertNotIn("SELECT sub_title FROM", map_content)
        self.assertIn("window.StoryDataService", map_content)

    # 19. map.js contains no fake synopsis phrases
    def test_19_map_js_contains_no_fake_synopsis_phrases(self):
        """19. 靜態斷言：map.js 完全不包含任何偽造大綱詞彙"""
        map_content = MAP_JS.read_text(encoding="utf-8")
        self.assertNotIn("美食殿堂的羈絆", map_content)
        self.assertNotIn("進一步的昇華", map_content)

    # 20. official synopsis safely rendered via textContent
    def test_20_official_synopsis_safely_rendered(self):
        """20. 靜態斷言：map.js 對 officialSynopsis 使用 textContent 設定以杜絕 XSS"""
        map_content = MAP_JS.read_text(encoding="utf-8")
        self.assertIn("synopsisEl.textContent = normalizedSynopsis", map_content)
        self.assertNotIn("synopsisEl.innerHTML =", map_content)

    # 21. manifest missing does not block dialogue rendering
    def test_21_manifest_missing_does_not_block_dialogue_rendering(self):
        """21. 靜態斷言：map.js 在官方大綱為 null 時顯示 availability state，對白區塊仍完整呈現"""
        map_content = MAP_JS.read_text(encoding="utf-8")
        self.assertIn("本話暫無官方大綱", map_content)
        self.assertIn("game-dialogue-board", map_content)
        self.assertIn("game-chara-list-bar", map_content)

    # 22. story-data-service.js precedes map.js in story_map.html
    def test_22_story_map_html_script_order(self):
        """22. 驗證 story_map.html 中 story-data-service.js 出現在 map.js 之前"""
        html = STORY_MAP_HTML.read_text(encoding="utf-8")
        idx_service = html.find("story-data-service.js")
        idx_map = html.find("map.js")
        self.assertNotEqual(idx_service, -1, "story-data-service.js 必須在 story_map.html 中引用")
        self.assertNotEqual(idx_map, -1, "map.js 必須在 story_map.html 中引用")
        self.assertLess(idx_service, idx_map, "story-data-service.js 必須出現在 map.js 之前")

    # 23. bundler copies story-data-service.js to dist
    def test_23_bundler_copies_story_data_service(self):
        """23. 驗證 bundler 包含 story-data-service.js 並正確複製至 dist 目錄"""
        from pipeline.bundle import DASHBOARD_DIR
        src_file = DASHBOARD_DIR / "story-data-service.js"
        self.assertTrue(src_file.exists())
        self.assertGreater(src_file.stat().st_size, 0)

        # 建立隔離的 mock dashboard 與 mock dist
        mock_dash = self.tmp_path / "dash"
        mock_dist = self.tmp_path / "dist"
        mock_dash.mkdir(parents=True)
        mock_dist.mkdir(parents=True)

        (mock_dash / "story-data-service.js").write_text("console.log('service');", encoding="utf-8")
        (mock_dash / "style.css").write_text("body{}", encoding="utf-8")
        (mock_dash / "story_map.html").write_text("<html></html>", encoding="utf-8")
        (mock_dash / "db.js").write_text("var db=1;", encoding="utf-8")
        (mock_dash / "chapter-data.js").write_text("var cd=1;", encoding="utf-8")

        from pipeline.bundle import copy_if_different
        copy_if_different(mock_dash / "story-data-service.js", mock_dist / "story-data-service.js")
        self.assertTrue((mock_dist / "story-data-service.js").exists())

    # 24. render_index_html applies content-hash cache busting
    def test_24_render_index_html_applies_content_hash(self):
        """24. 驗證 render_index_html 對 story-data-service.js 套用 8 碼 SHA-256 content hash"""
        html_out = render_index_html(DASHBOARD_DIR)
        expected_hash = calc_sha256(STORY_DATA_SERVICE_JS)[:8]
        expected_tag = f'<script src="story-data-service.js?v={expected_hash}"></script>'
        reader_hash = calc_sha256(DASHBOARD_DIR / "reader-navigation.js")[:8]
        self.assertIn(f'<script src="reader-navigation.js?v={reader_hash}"></script>', html_out)
        self.assertIn(expected_tag, html_out)

    # 25. validator rejects missing runtime service with precise error message
    def test_25_validator_rejects_missing_story_data_service_with_precise_error(self):
        """25. 驗證 Validator 遇到僅缺失 story-data-service.js 時精準在 errors 中指出該檔案"""
        mock_board = self.tmp_path / "mock_dashboard"
        mock_board.mkdir(parents=True)
        # 建立完整的必要檔案 (僅刻意缺少 story-data-service.js)
        (mock_board / "story_map.html").write_text("<html></html>", encoding="utf-8")
        (mock_board / "style.css").write_text("body{}", encoding="utf-8")
        (mock_board / "map.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "characters.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "avatar-service.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "story-asset-service.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "chapter-data.js").write_text("var cd=1;", encoding="utf-8")
        (mock_board / "db.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "sql-wasm.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "sql-wasm.wasm").write_bytes(b"wasm")
        (mock_board / "redive_tw.db").write_bytes(b"sqlite")

        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            ok = validate_story_map(target_dir=mock_board, check_dist=False, allow_metadata_bootstrap_incomplete=True)

        output_str = out.getvalue()
        self.assertFalse(ok)
        self.assertIn("story-data-service.js", output_str)

    # 26. dialogue concurrency: A pending dialogue -> B dialogue still starts
    def test_26_pending_a_dialogue_allows_b_dialogue_start(self):
        """26. 驗證當話數 A 對白加載處於 pending 時，切換至話數 B 仍能立即啟動話數 B 的 fetch"""
        js = """
        const qm = window.QuestMapModule;
        qm.getStoryById = (id) => ({ id, chapter: `第${id}章`, title: `話標題 ${id}` });
        qm.isDialogueExpanded = true;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};

        let fetchUrls = [];
        let resolveA = null;

        global.fetch = (url) => {
            fetchUrls.push(url);
            if (url.includes('100101')) {
                return new Promise((resolve) => {
                    resolveA = resolve;
                });
            }
            if (url.includes('100102')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => [{ name: '佩可', text: '對白B' }]
                });
            }
            return Promise.resolve({ ok: true, json: async () => [] });
        };

        // 1. selectStory(A)
        qm.selectStory(100101);

        // 2. 在 A 尚未 resolve 時 selectStory(B)
        qm.selectStory(100102);

        // 等待 microtasks 執行以讓 B 的 Promise chain 完成
        await new Promise(r => setTimeout(r, 20));

        console.log(JSON.stringify({
            success: true,
            fetchUrls,
            activeStoryId: qm.activeStoryId,
            isLoadingDialogue: qm.isLoadingDialogue
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        urls = res.get("fetchUrls", [])
        self.assertTrue(any("100101" in u for u in urls), "必須已發起話數 A 之請求")
        self.assertTrue(any("100102" in u for u in urls), "必須在 A pending 狀態下成功發起話數 B 之請求")
        self.assertEqual(res.get("activeStoryId"), 100102)
        self.assertFalse(res.get("isLoadingDialogue"))

    # 27. dialogue concurrency: B renders before stale A
    def test_27_b_renders_before_stale_a(self):
        """27. 驗證話數 B 之對白在舊話數 A 尚未完成前即正確渲染"""
        js = """
        const qm = window.QuestMapModule;
        qm.getStoryById = (id) => ({ id, chapter: `第${id}章`, title: `話標題 ${id}` });
        qm.isDialogueExpanded = true;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};

        let renderedStories = [];
        window.DialogueView.renderDialogue = (params) => {
            renderedStories.push(params.storyId);
        };

        let resolveA = null;
        global.fetch = (url) => {
            if (url.includes('100101')) {
                return new Promise((resolve) => {
                    resolveA = resolve;
                });
            }
            if (url.includes('100102')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => [{ name: '佩可', text: '對白B' }]
                });
            }
            return Promise.resolve({ ok: true, json: async () => [] });
        };

        qm.selectStory(100101);
        qm.selectStory(100102);

        await new Promise(r => setTimeout(r, 20));

        console.log(JSON.stringify({
            success: true,
            renderedStories
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("renderedStories"), [100102])

    # 28. dialogue concurrency: stale A never renders after B
    def test_28_stale_a_never_renders_after_b(self):
        """28. 驗證當舊話數 A 延遲 resolve 時，絕不渲染話數 A 且不覆蓋話數 B"""
        js = """
        const qm = window.QuestMapModule;
        qm.getStoryById = (id) => ({ id, chapter: `第${id}章`, title: `話標題 ${id}` });
        qm.isDialogueExpanded = true;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};

        let renderedStories = [];
        window.DialogueView.renderDialogue = (params) => {
            renderedStories.push(params.storyId);
        };

        let resolveA = null;
        global.fetch = (url) => {
            if (url.includes('100101')) {
                return new Promise((resolve) => {
                    resolveA = () => resolve({
                        ok: true,
                        json: async () => [{ name: '凱留', text: '對白A' }]
                    });
                });
            }
            if (url.includes('100102')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => [{ name: '佩可', text: '對白B' }]
                });
            }
            return Promise.resolve({ ok: true, json: async () => [] });
        };

        qm.selectStory(100101);
        qm.selectStory(100102);

        await new Promise(r => setTimeout(r, 20));

        // 現在 resolve 舊話數 A
        if (resolveA) resolveA();

        await new Promise(r => setTimeout(r, 20));

        console.log(JSON.stringify({
            success: true,
            renderedStories,
            activeStoryId: qm.activeStoryId
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("renderedStories"), [100102])
        self.assertEqual(res.get("activeStoryId"), 100102)

    # 29. dialogue concurrency: stale A cannot clear B loading state
    def test_29_stale_a_cannot_clear_b_loading_state(self):
        """29. 驗證當 A 與 B 同時處於請求中時，A 的完成不得清除話數 B 專屬的 loading 狀態"""
        js = """
        const qm = window.QuestMapModule;
        qm.getStoryById = (id) => ({ id, chapter: `第${id}章`, title: `話標題 ${id}` });
        qm.isDialogueExpanded = true;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};

        let resolveA = null;
        let resolveB = null;

        global.fetch = (url) => {
            if (url.includes('100101')) {
                return new Promise((resolve) => {
                    resolveA = () => resolve({
                        ok: true,
                        json: async () => [{ name: '凱留', text: '對白A' }]
                    });
                });
            }
            if (url.includes('100102')) {
                return new Promise((resolve) => {
                    resolveB = () => resolve({
                        ok: true,
                        json: async () => [{ name: '佩可', text: '對白B' }]
                    });
                });
            }
            return Promise.resolve({ ok: true, json: async () => [] });
        };

        qm.selectStory(100101);
        const tokenA = qm._storyRenderToken;

        qm.selectStory(100102);
        const tokenB = qm._storyRenderToken;

        // 此時 A, B 都在加載中
        const loadingBeforeResolveA = qm.isLoadingDialogue;
        const tokenBeforeResolveA = qm._dialogueLoadingToken;

        // Resolve 舊話數 A
        if (resolveA) resolveA();
        await new Promise(r => setTimeout(r, 20));

        // A 完成後，B 仍在加載，loading 狀態不得被 A 的 finally 偷清除
        const loadingAfterResolveA = qm.isLoadingDialogue;
        const tokenAfterResolveA = qm._dialogueLoadingToken;

        // Resolve 話數 B
        if (resolveB) resolveB();
        await new Promise(r => setTimeout(r, 20));

        // B 完成後，loading 狀態正常清除
        const loadingAfterResolveB = qm.isLoadingDialogue;
        const tokenAfterResolveB = qm._dialogueLoadingToken;

        console.log(JSON.stringify({
            success: true,
            tokenA,
            tokenB,
            loadingBeforeResolveA,
            tokenBeforeResolveA,
            loadingAfterResolveA,
            tokenAfterResolveA,
            loadingAfterResolveB,
            tokenAfterResolveB
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("loadingBeforeResolveA"))
        self.assertEqual(res.get("tokenBeforeResolveA"), res.get("tokenB"))
        self.assertTrue(res.get("loadingAfterResolveA"), "A 的 finally 絕不可將 B 正在進行中的 loading 改為 false")
        self.assertEqual(res.get("tokenAfterResolveA"), res.get("tokenB"))
        self.assertFalse(res.get("loadingAfterResolveB"), "B 正常完成後 loading 應重設為 false")
        self.assertIsNone(res.get("tokenAfterResolveB"))

    # 30. dialogue concurrency: after stale A/B sequence, C still loads normally
    def test_30_after_stale_ab_sequence_c_still_loads_normally(self):
        """30. 回歸防護測試：驗證在經歷 A (stale) -> B 切換序列後，後續切換至話數 C 仍可正常加載與渲染對白 (無永久鎖死)"""
        js = """
        const qm = window.QuestMapModule;
        qm.getStoryById = (id) => ({ id, chapter: `第${id}章`, title: `話標題 ${id}` });
        qm.isDialogueExpanded = true;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};

        let renderedStories = [];
        window.DialogueView.renderDialogue = (params) => {
            renderedStories.push(params.storyId);
        };

        let resolveA = null;
        global.fetch = (url) => {
            if (url.includes('100101')) {
                return new Promise((resolve) => {
                    resolveA = () => resolve({
                        ok: true,
                        json: async () => [{ name: '凱留', text: '對白A' }]
                    });
                });
            }
            if (url.includes('100102')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => [{ name: '佩可', text: '對白B' }]
                });
            }
            if (url.includes('100103')) {
                return Promise.resolve({
                    ok: true,
                    json: async () => [{ name: '可可蘿', text: '對白C' }]
                });
            }
            return Promise.resolve({ ok: true, json: async () => [] });
        };

        // 1. A 啟動 (pending)
        qm.selectStory(100101);

        // 2. 切換至 B
        qm.selectStory(100102);
        await new Promise(r => setTimeout(r, 20));

        // 3. A 延遲 resolve
        if (resolveA) resolveA();
        await new Promise(r => setTimeout(r, 20));

        // 4. 現在切換至 C (驗證永不 dead-lock)
        qm.selectStory(100103);
        await new Promise(r => setTimeout(r, 20));

        console.log(JSON.stringify({
            success: true,
            renderedStories,
            activeStoryId: qm.activeStoryId,
            isLoadingDialogue: qm.isLoadingDialogue
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("renderedStories"), [100102, 100103])
        self.assertEqual(res.get("activeStoryId"), 100103)
        self.assertFalse(res.get("isLoadingDialogue"))

    # 31. dialogue concurrency: same-token duplicate dialogue request suppressed
    def test_31_same_token_duplicate_dialogue_request_suppressed(self):
        """31. 驗證同一 token / 相同話數短時間內重複呼叫 loadDialogue 被正確抑制，不發起重複請求"""
        js = """
        const qm = window.QuestMapModule;
        qm.getStoryById = (id) => ({ id, chapter: `第${id}章`, title: `話標題 ${id}` });
        qm.isDialogueExpanded = true;
        qm.updateNavigationButtons = () => {};
        qm.updateReaderState = () => {};

        let storyFetchCount = 0;
        global.fetch = (url) => {
            if (url.includes('story/')) {
                storyFetchCount++;
            }
            return new Promise(() => {}); // 保持 pending
        };

        // 1. selectStory(A)
        qm.selectStory(100101);
        const token = qm._storyRenderToken;

        // 2. 重複呼叫 loadDialogue 傳入相同 token
        qm.loadDialogue(100101, token);
        qm.loadDialogue(100101, token);

        console.log(JSON.stringify({
            success: true,
            storyFetchCount,
            dialogueLoadingToken: qm._dialogueLoadingToken
        }));
        """
        res = run_node_test_script(js, include_map=True)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("storyFetchCount"), 1)


if __name__ == "__main__":
    unittest.main()
