import unittest
import json
import subprocess
import sys
import tempfile
import hashlib
from pathlib import Path

sys.path.insert(0, '.')

class TestAvatarServiceShortIdContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js_path = Path('dashboard/avatar-service.js')
        assert cls.js_path.exists(), 'dashboard/avatar-service.js missing'

    def test_frontend_contract_hermetic_via_node(self):
        """透過 Node.js 執行實際 avatar-service.js，使用合成最小 Manifest 驗證 exact resolution 契約"""
        test_script = """
        const fs = require('fs');
        const vm = require('vm');

        const jsCode = fs.readFileSync('dashboard/avatar-service.js', 'utf8');
        const sandbox = {
            console: { log: () => {}, warn: () => {}, error: () => {} },
            window: {},
            document: {},
            fetch: null
        };
        sandbox.window = sandbox;
        vm.createContext(sandbox);
        vm.runInContext(jsCode, sandbox);

        const AvatarService = sandbox.AvatarService;
        
        // 最小合成 Manifest (完全不依賴 production avatar_assets.json 與圖檔)
        const syntheticManifest = {
            version: 1,
            assets: [
                {
                    unit_id: 6112,
                    asset_key: "006112",
                    filename: "006112.png",
                    usage: "dialogue",
                    status: "active"
                },
                {
                    unit_id: 100011,
                    filename: "100011.png",
                    usage: "dialogue",
                    status: "active"
                }
            ]
        };
        AvatarService.loadManifest(syntheticManifest);

        // 1. registered canonical short ID 6112
        const res6112 = AvatarService.resolveExactDialoguePortrait(6112);
        if (!res6112 || res6112.status !== 'active' || res6112.filename !== '006112.png') {
            console.error('FAIL_6112_EXACT', res6112);
            process.exit(1);
        }
        const html6112 = AvatarService.getAvatarHtmlByUnitId(6112, '秘書');
        if (!html6112.includes('006112.png')) {
            console.error('FAIL_6112_HTML', html6112);
            process.exit(2);
        }

        // 2. Unregistered short IDs are explicit unknown identities, never a
        // name-inference candidate.
        const res1411 = AvatarService.resolveExactDialoguePortrait(1411);
        if (!res1411 || res1411.status !== 'unknown_placeholder') {
            console.error('FAIL_1411_MUST_FAIL_CLOSED', res1411);
            process.exit(3);
        }

        // 3. arbitrary unknown short ID also fails closed.
        const res1234 = AvatarService.resolveExactDialoguePortrait(1234);
        if (!res1234 || res1234.status !== 'unknown_placeholder') {
            console.error('FAIL_1234_MUST_FAIL_CLOSED', res1234);
            process.exit(4);
        }

        const unknownShortHtml = AvatarService.getAvatarHtmlByUnitId(1411, '路人', { '路人': 105801 });
        if (!unknownShortHtml.includes('npc-avatar-placeholder') || unknownShortHtml.includes('105811.png')) {
            console.error('FAIL_1411_HTML_MUST_NOT_INFER', unknownShortHtml);
            process.exit(6);
        }

        // 5. existing >=100000 dialogue ID (100011) 行為保持不變
        const res100011 = AvatarService.resolveExactDialoguePortrait(100011);
        if (!res100011 || res100011.status !== 'active' || res100011.filename !== '100011.png') {
            console.error('FAIL_100011', res100011);
            process.exit(5);
        }

        console.log('NODE_HERMETIC_PASS');
        """
        p = subprocess.run(['node', '-e', test_script], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, f'Node contract failed: {p.stderr}')
        self.assertIn('NODE_HERMETIC_PASS', p.stdout)


class TestValidatorShortIdContract(unittest.TestCase):
    def _create_fixture(self, tmpdir_path, asset_key_6112="006112", include_legacy_1411=False, include_six_digit=True, omit_six_digit_registry=False):
        """建立完全隔離的最小測試 dashboard 環境，不複製 production 資料"""
        data_dir = tmpdir_path / "data"
        icon_dir = tmpdir_path / "icon" / "unit"
        story_dir = tmpdir_path / "story"
        data_dir.mkdir(parents=True)
        icon_dir.mkdir(parents=True)
        story_dir.mkdir(parents=True)

        # 建立 dummy binary 檔案並計算雜湊大小
        dummy_6112_bytes = b"DUMMY_IMAGE_BINARY_FOR_006112"
        p_6112 = icon_dir / "006112.png"
        p_6112.write_bytes(dummy_6112_bytes)
        size_6112 = len(dummy_6112_bytes)
        sha_6112 = hashlib.sha256(dummy_6112_bytes).hexdigest()

        assets = [
            {
                "unit_id": 6112,
                "asset_key": asset_key_6112,
                "filename": "006112.png",
                "format": "png",
                "usage": "dialogue",
                "status": "active",
                "size_bytes": size_6112,
                "sha256": sha_6112
            }
        ]

        if include_six_digit and not omit_six_digit_registry:
            dummy_100011_bytes = b"DUMMY_IMAGE_BINARY_FOR_100011"
            p_100011 = icon_dir / "100011.png"
            p_100011.write_bytes(dummy_100011_bytes)
            size_100011 = len(dummy_100011_bytes)
            sha_100011 = hashlib.sha256(dummy_100011_bytes).hexdigest()
            assets.append({
                "unit_id": 100011,
                "filename": "100011.png",
                "format": "png",
                "usage": "dialogue",
                "status": "active",
                "size_bytes": size_100011,
                "sha256": sha_100011
            })

        manifest = {
            "version": 1,
            "metadata": {"total_assets": len(assets)},
            "assets": assets
        }
        (data_dir / "avatar_assets.json").write_text(json.dumps(manifest), encoding="utf-8")

        # 建立 Story fixture
        story_rows = [
            {"type": "dialogue", "name": "秘書", "unit_id": 6112, "words": "test 6112"}
        ]
        if include_legacy_1411:
            story_rows.append({"type": "dialogue", "name": "路人", "unit_id": 1411, "words": "test legacy 1411"})
        if include_six_digit:
            story_rows.append({"type": "dialogue", "name": "可可蘿", "unit_id": 100011, "words": "test 100011"})

        (story_dir / "5218004.json").write_text(json.dumps(story_rows), encoding="utf-8")

    def test_case_a_valid_pilot_fixture_passes(self):
        """Case A: 合法 6112 registry + dummy binary + story -> PASS"""
        from pipeline.validate import validate_avatar_manifest_and_assets, ValidationResult
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            self._create_fixture(tmppath, asset_key_6112="006112")
            res = ValidationResult()
            ok = validate_avatar_manifest_and_assets(tmppath, res)
            self.assertTrue(ok, f"Case A should pass: {res.errors}")
            self.assertEqual(len(res.errors), 0)

    def test_case_b_asset_key_mismatch_fails(self):
        """Case B: 將 asset_key 設為 '006111' 錯配 -> FAIL"""
        from pipeline.validate import validate_avatar_manifest_and_assets, ValidationResult
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            self._create_fixture(tmppath, asset_key_6112="006111")
            res = ValidationResult()
            ok = validate_avatar_manifest_and_assets(tmppath, res)
            self.assertFalse(ok, "Case B should fail on asset_key mismatch")
            self.assertTrue(any("asset_key" in err or "006111" in err for err in res.errors))

    def test_case_c_unregistered_short_id_fails(self):
        """Any positive explicit short ID missing from the registry must fail."""
        from pipeline.validate import validate_avatar_manifest_and_assets, ValidationResult
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            self._create_fixture(tmppath, include_legacy_1411=True)
            res = ValidationResult()
            ok = validate_avatar_manifest_and_assets(tmppath, res)
            self.assertFalse(ok, f"Case C must fail for unregistered short ID: {res.errors}")
            self.assertTrue(any("登錄" in error for error in res.errors))

    def test_case_d_existing_six_digit_strict_coverage_maintained(self):
        """Case D: existing six-digit ID fixture -> 維持原本 strict coverage 行為 (若 registry 缺失 100011 則報錯 FAIL)"""
        from pipeline.validate import validate_avatar_manifest_and_assets, ValidationResult
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            self._create_fixture(tmppath, include_six_digit=True, omit_six_digit_registry=True)
            res = ValidationResult()
            ok = validate_avatar_manifest_and_assets(tmppath, res)
            self.assertFalse(ok, "Case D should fail when six-digit ID in story is missing from registry")
            self.assertTrue(any("100011" in err for err in res.errors))

    def test_case_e_unreadable_or_invalid_story_fails_closed(self):
        """A partial Story scan must not be accepted as a complete registry check."""
        from pipeline.validate import validate_avatar_manifest_and_assets, ValidationResult
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            self._create_fixture(tmppath)
            (tmppath / "story" / "9999.json").write_text("{invalid-json", encoding="utf-8")
            res = ValidationResult()
            ok = validate_avatar_manifest_and_assets(tmppath, res)
            self.assertFalse(ok, "Invalid canonical Story JSON must fail validation")
            self.assertTrue(any("無法讀取或解析" in error for error in res.errors))


if __name__ == '__main__':
    unittest.main()
