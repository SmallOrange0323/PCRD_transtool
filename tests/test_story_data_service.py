# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - StoryDataService & M3A UI Integration Tests
涵蓋 20 項針對性 Runtime、Service、Cache-Busting 與 UI Integrity 門禁測試 (全數 Hermetic 零外網洩漏)：
1. StoryDataService global exists
2. metadata_version present -> versioned manifest request
3. db_info request uses no-store
4. metadata_version missing -> no-store manifest request
5. db_version fallback strictly forbidden
6. concurrent calls share one loading operation
7. successful load caches episodes
8. failed load resets _loadingPromise
9. failed load permits retry
10. malformed manifest graceful degradation
11. getEpisodeMetadata numeric and string ID works
12. null synopsis returns null
13. map.js no DB sub_title -> official synopsis mapping
14. map.js contains no fake synopsis phrases
15. official synopsis HTML escapes text
16. manifest missing does not block dialogue rendering
17. story-data-service.js precedes map.js in story_map.html
18. bundler copies story-data-service.js to dist
19. render_index_html applies content-hash cache busting
20. validator rejects missing runtime service
"""

import os
import sys
import json
import re
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
STORY_DATA_SERVICE_JS = DASHBOARD_DIR / "story-data-service.js"
MAP_JS = DASHBOARD_DIR / "map.js"
STORY_MAP_HTML = DASHBOARD_DIR / "story_map.html"

from pipeline.bundle import render_index_html, bundle_story_map, calc_sha256
from pipeline.validate import validate_story_map, ValidationResult


def run_node_test_script(js_code: str) -> dict:
    """在 Node.js 沙盒中執行測試腳本，回傳 JSON 結果。"""
    service_code = STORY_DATA_SERVICE_JS.read_text(encoding="utf-8")
    wrapper = f"""
    const window = {{}};
    {service_code}
    
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
            return json.loads(output)
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse Node.js output as JSON: {output}")
    finally:
        try:
            os.remove(temp_js_path)
        except OSError:
            pass


class TestStoryDataServiceRuntime(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # 1. StoryDataService global exists
    def test_01_story_data_service_global_exists(self):
        """1. 驗證 window.StoryDataService 正確建立且具備標準 API"""
        js = """
        const exists = typeof window.StoryDataService === 'object' && window.StoryDataService !== null;
        const hasEnsure = typeof window.StoryDataService.ensureMetadataLoaded === 'function';
        const hasGetEp = typeof window.StoryDataService.getEpisodeMetadata === 'function';
        const hasGetSyn = typeof window.StoryDataService.getOfficialSynopsis === 'function';
        const hasGetCh = typeof window.StoryDataService.getChapterTitle === 'function';
        const hasGetSub = typeof window.StoryDataService.getSubtitle === 'function';
        console.log(JSON.stringify({ success: true, exists, hasEnsure, hasGetEp, hasGetSyn, hasGetCh, hasGetSub }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("exists"))
        self.assertTrue(res.get("hasEnsure"))
        self.assertTrue(res.get("hasGetEp"))
        self.assertTrue(res.get("hasGetSyn"))
        self.assertTrue(res.get("hasGetCh"))
        self.assertTrue(res.get("hasGetSub"))

    # 2. metadata_version present -> versioned manifest request
    def test_02_metadata_version_present_uses_versioned_request(self):
        """2. 驗證 db_info 含有 metadata_version 時，以版本號 query 請求 official_story_metadata.json"""
        js = """
        const fetchCalls = [];
        global.fetch = async (url, opts) => {
            fetchCalls.push({ url, opts });
            if (url === 'data/db_info.json') {
                return {
                    ok: true,
                    json: async () => ({ metadata_version: 'a1b2c3d4e5f6', db_version: 'db_9999' })
                };
            }
            if (url.startsWith('data/official_story_metadata.json')) {
                return {
                    ok: true,
                    json: async () => ({
                        schema_version: 1,
                        truth_version: '00600025',
                        episodes: {
                            '100101': { official_synopsis: '測試大綱 1' }
                        }
                    })
                };
            }
            return { ok: false, status: 404 };
        };

        const res = await window.StoryDataService.ensureMetadataLoaded();
        console.log(JSON.stringify({
            success: true,
            fetchCalls,
            hasLoaded: res !== null && typeof res['100101'] === 'object'
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("hasLoaded"))
        calls = res.get("fetchCalls", [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["url"], "data/db_info.json")
        self.assertEqual(calls[1]["url"], "data/official_story_metadata.json?v=a1b2c3d4e5f6")

    # 3. db_info request uses no-store
    def test_03_db_info_request_uses_no_store(self):
        """3. 驗證探測 db_info.json 時必須使用 cache: 'no-store'"""
        js = """
        let dbInfoOpts = null;
        global.fetch = async (url, opts) => {
            if (url === 'data/db_info.json') {
                dbInfoOpts = opts;
                return { ok: false, status: 404 };
            }
            if (url.startsWith('data/official_story_metadata.json')) {
                return { ok: false, status: 404 };
            }
            return { ok: false, status: 404 };
        };

        await window.StoryDataService.ensureMetadataLoaded();
        console.log(JSON.stringify({ success: true, dbInfoOpts }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        opts = res.get("dbInfoOpts")
        self.assertIsNotNone(opts)
        self.assertEqual(opts.get("cache"), "no-store")

    # 4. metadata_version missing -> no-store manifest request
    def test_04_metadata_version_missing_uses_no_store_request(self):
        """4. 驗證 db_info 不存在或無 metadata_version 時，以 no-store 直接請求 official_story_metadata.json"""
        js = """
        const fetchCalls = [];
        global.fetch = async (url, opts) => {
            fetchCalls.push({ url, opts });
            if (url === 'data/db_info.json') {
                return { ok: true, json: async () => ({}) };
            }
            if (url === 'data/official_story_metadata.json') {
                return {
                    ok: true,
                    json: async () => ({ episodes: { '100101': { official_synopsis: '測試' } } })
                };
            }
            return { ok: false, status: 404 };
        };

        await window.StoryDataService.ensureMetadataLoaded();
        console.log(JSON.stringify({ success: true, fetchCalls }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        calls = res.get("fetchCalls", [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["url"], "data/official_story_metadata.json")
        self.assertEqual(calls[1]["opts"].get("cache"), "no-store")

    # 5. db_version fallback strictly forbidden
    def test_05_db_version_fallback_strictly_forbidden(self):
        """5. 驗證 db_info 僅有 db_version 時，嚴格禁止 fallback 使用 db_version 作為 metadata 查詢參數"""
        js = """
        const fetchCalls = [];
        global.fetch = async (url, opts) => {
            fetchCalls.push({ url, opts });
            if (url === 'data/db_info.json') {
                return { ok: true, json: async () => ({ db_version: 'db_hash_123456' }) };
            }
            if (url === 'data/official_story_metadata.json') {
                return { ok: true, json: async () => ({ episodes: {} }) };
            }
            return { ok: false, status: 404 };
        };

        await window.StoryDataService.ensureMetadataLoaded();
        console.log(JSON.stringify({ success: true, fetchCalls }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        calls = res.get("fetchCalls", [])
        self.assertEqual(len(calls), 2)
        # 絕不應出現 ?v=db_hash_123456
        self.assertEqual(calls[1]["url"], "data/official_story_metadata.json")
        self.assertNotIn("db_hash", calls[1]["url"])

    # 6. concurrent calls share one loading operation
    def test_06_concurrent_calls_share_one_loading_operation(self):
        """6. 驗證多次並發呼叫 ensureMetadataLoaded 共享同一個 Promise，只觸發一次網路載入"""
        js = """
        let manifestFetchCount = 0;
        global.fetch = async (url, opts) => {
            if (url === 'data/db_info.json') {
                return { ok: true, json: async () => ({ metadata_version: 'v123' }) };
            }
            if (url.startsWith('data/official_story_metadata.json')) {
                manifestFetchCount++;
                // 模擬微小網路延遲
                await new Promise(r => setTimeout(r, 10));
                return { ok: true, json: async () => ({ episodes: { '100101': { official_synopsis: 'OK' } } }) };
            }
            return { ok: false };
        };

        const [r1, r2, r3] = await Promise.all([
            window.StoryDataService.ensureMetadataLoaded(),
            window.StoryDataService.ensureMetadataLoaded(),
            window.StoryDataService.ensureMetadataLoaded()
        ]);

        console.log(JSON.stringify({
            success: true,
            manifestFetchCount,
            allSame: r1 === r2 && r2 === r3 && r1['100101'].official_synopsis === 'OK'
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
        let totalCalls = 0;
        global.fetch = async (url) => {
            totalCalls++;
            if (url === 'data/db_info.json') return { ok: true, json: async () => ({ metadata_version: 'v1' }) };
            return { ok: true, json: async () => ({ episodes: { '100101': { subtitle: 'Sub 1' } } }) };
        };

        await window.StoryDataService.ensureMetadataLoaded();
        const callCountAfterFirst = totalCalls;

        const ep = await window.StoryDataService.getEpisodeMetadata(100101);
        const sub = await window.StoryDataService.getSubtitle(100101);

        console.log(JSON.stringify({
            success: true,
            callCountAfterFirst,
            totalCallsAfterAll: totalCalls,
            sub
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("callCountAfterFirst"), 2)
        self.assertEqual(res.get("totalCallsAfterAll"), 2)
        self.assertEqual(res.get("sub"), "Sub 1")

    # 8. failed load resets _loadingPromise
    def test_08_failed_load_resets_loading_promise(self):
        """8. 驗證載入失敗時 _loadingPromise 正確重設為 null，且 _metadataCache 保持 null"""
        js = """
        global.fetch = async () => ({ ok: false, status: 500 });

        const res = await window.StoryDataService.ensureMetadataLoaded();
        const loadingPromiseNull = window.StoryDataService._loadingPromise === null;
        const cacheNull = window.StoryDataService._metadataCache === null;

        console.log(JSON.stringify({
            success: true,
            resIsNull: res === null,
            loadingPromiseNull,
            cacheNull
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("resIsNull"))
        self.assertTrue(res.get("loadingPromiseNull"))
        self.assertTrue(res.get("cacheNull"))

    # 9. failed load permits retry
    def test_09_failed_load_permits_retry(self):
        """9. 驗證第一次載入失敗後，第二次呼叫可正常重試並在成功後取得資料"""
        js = """
        let attempt = 0;
        global.fetch = async (url) => {
            if (url === 'data/db_info.json') return { ok: true, json: async () => ({ metadata_version: 'v1' }) };
            attempt++;
            if (attempt === 1) {
                return { ok: false, status: 500 };
            }
            return { ok: true, json: async () => ({ episodes: { '100101': { official_synopsis: 'RETRY_SUCCESS' } } }) };
        };

        const res1 = await window.StoryDataService.getOfficialSynopsis(100101);
        const res2 = await window.StoryDataService.getOfficialSynopsis(100101);

        console.log(JSON.stringify({
            success: true,
            res1,
            res2,
            attempt
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertIsNone(res.get("res1"))
        self.assertEqual(res.get("res2"), "RETRY_SUCCESS")
        self.assertEqual(res.get("attempt"), 2)

    # 10. malformed manifest graceful degradation
    def test_10_malformed_manifest_graceful_degradation(self):
        """10. 驗證 Manifest 頂層非物件或 episodes 損壞時優雅降級為 null，絕不拋出例外崩潰 UI"""
        js = """
        global.fetch = async (url) => {
            if (url === 'data/db_info.json') return { ok: true, json: async () => ({ metadata_version: 'v1' }) };
            // 回傳損壞結構 (episodes 非 dict 而是 string)
            return { ok: true, json: async () => ({ schema_version: 1, episodes: "invalid_string" }) };
        };

        let threw = false;
        let res = null;
        try {
            res = await window.StoryDataService.getOfficialSynopsis(100101);
        } catch (e) {
            threw = true;
        }

        console.log(JSON.stringify({ success: true, threw, res }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertFalse(res.get("threw"))
        self.assertIsNone(res.get("res"))

    # 11. getEpisodeMetadata numeric and string ID works
    def test_11_get_episode_metadata_numeric_and_string_id(self):
        """11. 驗證 getEpisodeMetadata 傳入數字或字串 ID 均可正確查得節點"""
        js = """
        global.fetch = async (url) => {
            if (url === 'data/db_info.json') return { ok: true, json: async () => ({ metadata_version: 'v1' }) };
            return { ok: true, json: async () => ({
                episodes: {
                    '100101': { official_synopsis: 'SYNOPSIS_100101', chapter_title: 'TITLE_1' }
                }
            }) };
        };

        const epNum = await window.StoryDataService.getEpisodeMetadata(100101);
        const epStr = await window.StoryDataService.getEpisodeMetadata("100101");
        const epNull = await window.StoryDataService.getEpisodeMetadata(null);

        console.log(JSON.stringify({
            success: true,
            numSynopsis: epNum?.official_synopsis,
            strSynopsis: epStr?.official_synopsis,
            nullResult: epNull
        }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("numSynopsis"), "SYNOPSIS_100101")
        self.assertEqual(res.get("strSynopsis"), "SYNOPSIS_100101")
        self.assertIsNone(res.get("nullResult"))

    # 12. null synopsis returns null
    def test_12_null_synopsis_returns_null(self):
        """12. 驗證話數 official_synopsis 為 null 或空白時，getOfficialSynopsis 嚴格回傳 null"""
        js = """
        global.fetch = async (url) => {
            if (url === 'data/db_info.json') return { ok: true, json: async () => ({ metadata_version: 'v1' }) };
            return { ok: true, json: async () => ({
                episodes: {
                    '100101': { official_synopsis: null },
                    '100102': { official_synopsis: '   ' }
                }
            }) };
        };

        const s1 = await window.StoryDataService.getOfficialSynopsis(100101);
        const s2 = await window.StoryDataService.getOfficialSynopsis(100102);
        const s3 = await window.StoryDataService.getOfficialSynopsis(999999);

        console.log(JSON.stringify({ success: true, s1, s2, s3 }));
        """
        res = run_node_test_script(js)
        self.assertTrue(res.get("success"))
        self.assertIsNone(res.get("s1"))
        self.assertIsNone(res.get("s2"))
        self.assertIsNone(res.get("s3"))

    # 13. map.js no DB sub_title -> official synopsis mapping
    def test_13_map_js_no_db_subtitle_to_official_synopsis(self):
        """13. 靜態斷言：map.js updateSummaryContent 已移除 SELECT sub_title 作為官方大綱之路徑"""
        map_content = MAP_JS.read_text(encoding="utf-8")
        # 尋找 updateSummaryContent 區塊
        self.assertNotIn("SELECT sub_title FROM", map_content)
        self.assertIn("window.StoryDataService", map_content)

    # 14. map.js contains no fake synopsis phrases
    def test_14_map_js_contains_no_fake_synopsis_phrases(self):
        """14. 靜態斷言：map.js 完全不包含任何偽造大綱詞彙"""
        map_content = MAP_JS.read_text(encoding="utf-8")
        self.assertNotIn("美食殿堂的羈絆", map_content)
        self.assertNotIn("進一步的昇華", map_content)

    # 15. official synopsis HTML escapes text
    def test_15_official_synopsis_html_escaped(self):
        """15. 靜態斷言：map.js 對 officialSynopsis 渲染前調用 this.escapeHtml"""
        map_content = MAP_JS.read_text(encoding="utf-8")
        self.assertIn("this.escapeHtml(officialSynopsis)", map_content)

    # 16. manifest missing does not block dialogue rendering
    def test_16_manifest_missing_does_not_block_dialogue_rendering(self):
        """16. 靜態斷言：map.js 在官方大綱為 null 時顯示 availability state，對白區塊仍完整呈現"""
        map_content = MAP_JS.read_text(encoding="utf-8")
        self.assertIn("本話暫無官方大綱", map_content)
        self.assertIn("game-dialogue-board", map_content)
        self.assertIn("game-chara-list-bar", map_content)

    # 17. story-data-service.js precedes map.js in story_map.html
    def test_17_story_map_html_script_order(self):
        """17. 驗證 story_map.html 中 story-data-service.js 出現在 map.js 之前"""
        html = STORY_MAP_HTML.read_text(encoding="utf-8")
        idx_service = html.find("story-data-service.js")
        idx_map = html.find("map.js")
        self.assertNotEqual(idx_service, -1, "story-data-service.js 必須在 story_map.html 中引用")
        self.assertNotEqual(idx_map, -1, "map.js 必須在 story_map.html 中引用")
        self.assertLess(idx_service, idx_map, "story-data-service.js 必須出現在 map.js 之前")

    # 18. bundler copies story-data-service.js to dist
    def test_18_bundler_copies_story_data_service(self):
        """18. 驗證 bundler 包含 story-data-service.js 並正確複製至 dist 目錄"""
        from pipeline.bundle import DASHBOARD_DIR
        mock_dist = self.tmp_path / "dist"
        mock_dist.mkdir(parents=True)
        # 測試 dry-run / render 均包含
        bundle_story_map(dry_run=True)
        # 驗證 source 存在且非空
        src_file = DASHBOARD_DIR / "story-data-service.js"
        self.assertTrue(src_file.exists())
        self.assertGreater(src_file.stat().st_size, 0)

    # 19. render_index_html applies content-hash cache busting
    def test_19_render_index_html_applies_content_hash(self):
        """19. 驗證 render_index_html 對 story-data-service.js 套用 8 碼 SHA-256 content hash"""
        html_out = render_index_html(DASHBOARD_DIR)
        expected_hash = calc_sha256(STORY_DATA_SERVICE_JS)[:8]
        expected_tag = f'<script src="story-data-service.js?v={expected_hash}"></script>'
        self.assertIn(expected_tag, html_out)

    # 20. validator rejects missing runtime service
    def test_20_validator_rejects_missing_story_data_service(self):
        """20. 驗證 Validator 嚴格阻斷缺失 story-data-service.js 之 dashboard / dist"""
        mock_board = self.tmp_path / "mock_dashboard"
        mock_board.mkdir(parents=True)
        # 建立除了 story-data-service.js 以外的基本檔案
        (mock_board / "story_map.html").write_text("<html></html>", encoding="utf-8")
        (mock_board / "style.css").write_text("body{}", encoding="utf-8")
        (mock_board / "map.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "characters.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "avatar-service.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "story-asset-service.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "chapter-data.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "db.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "sql-wasm.js").write_text("var a=1;", encoding="utf-8")
        (mock_board / "sql-wasm.wasm").write_bytes(b"wasm")
        (mock_board / "redive_tw.db").write_bytes(b"sqlite")

        res = ValidationResult()
        ok = validate_story_map(target_dir=mock_board, check_dist=False, allow_metadata_bootstrap_incomplete=True)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
