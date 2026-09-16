import unittest
import json
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, '.')

class TestAvatarServiceShortIdContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js_path = Path('dashboard/avatar-service.js')
        cls.manifest_path = Path('dashboard/data/avatar_assets.json')
        assert cls.js_path.exists(), 'dashboard/avatar-service.js missing'
        assert cls.manifest_path.exists(), 'dashboard/data/avatar_assets.json missing'

    def test_frontend_contract_via_node(self):
        """透過 Node.js 執行實際 avatar-service.js，覆蓋 6112、1411、1234、100011"""
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
        const manifestData = JSON.parse(fs.readFileSync('dashboard/data/avatar_assets.json', 'utf8'));
        AvatarService.loadManifest(manifestData);

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

        // 2. unregistered legacy short ID 1411 (不 exact resolve，維持 fallback)
        const res1411 = AvatarService.resolveExactDialoguePortrait(1411);
        if (res1411 !== null) {
            console.error('FAIL_1411_SHOULD_BE_NULL', res1411);
            process.exit(3);
        }

        // 3. arbitrary unknown short ID 1234 (fail-closed / fallback)
        const res1234 = AvatarService.resolveExactDialoguePortrait(1234);
        if (res1234 !== null) {
            console.error('FAIL_1234_SHOULD_BE_NULL', res1234);
            process.exit(4);
        }

        // 5. existing >=100000 dialogue ID (100011) 行為保持不變
        const res100011 = AvatarService.resolveExactDialoguePortrait(100011);
        if (!res100011 || res100011.status !== 'active' || res100011.filename !== '100011.png') {
            console.error('FAIL_100011', res100011);
            process.exit(5);
        }

        console.log('NODE_CONTRACT_PASS');
        """
        p = subprocess.run(['node', '-e', test_script], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, f'Node contract failed: {p.stderr}')
        self.assertIn('NODE_CONTRACT_PASS', p.stdout)


class TestValidatorShortIdContract(unittest.TestCase):
    def test_validator_contract_rules(self):
        from pipeline.validate import validate_avatar_manifest_and_assets, ValidationResult

        # A. 現有 dashboard (包含 6112 與 5218004) 必須 PASS
        res = ValidationResult()
        ok = validate_avatar_manifest_and_assets(Path('dashboard'), res)
        self.assertTrue(ok, f'Current validation failed: {res.errors}')
        self.assertEqual(len(res.errors), 0)

        # B. 測試案例 4: short-ID Registry contract mismatch (6112 + asset_key '006111') -> Validator FAIL
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            shutil.copytree('dashboard/data', tmppath / 'data')
            shutil.copytree('dashboard/icon', tmppath / 'icon')
            (tmppath / 'story').mkdir(parents=True)

            manifest_file = tmppath / 'data' / 'avatar_assets.json'
            mdata = json.loads(manifest_file.read_text(encoding='utf-8'))
            for a in mdata['assets']:
                if a.get('unit_id') == 6112:
                    a['asset_key'] = '006111'  # 格式或 ID 不一致

            manifest_file.write_text(json.dumps(mdata), encoding='utf-8')

            res_mismatch = ValidationResult()
            ok_mismatch = validate_avatar_manifest_and_assets(tmppath, res_mismatch)
            self.assertFalse(ok_mismatch, 'Expected validator FAIL on asset_key mismatch')
            self.assertTrue(any('asset_key' in err or '006111' in err for err in res_mismatch.errors))

        # C. 測試案例 2: legacy short ID (1411) 存在於 Story 但未在 registry -> 不得報錯
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            shutil.copytree('dashboard/data', tmppath / 'data')
            shutil.copytree('dashboard/icon', tmppath / 'icon')
            (tmppath / 'story').mkdir(parents=True)

            # Story 只有 1411 (魔物/路人)
            story_file = tmppath / 'story' / '1001001.json'
            story_file.write_text(json.dumps([{'name': '魔物', 'unit_id': 1411}]), encoding='utf-8')

            res_legacy = ValidationResult()
            ok_legacy = validate_avatar_manifest_and_assets(tmppath, res_legacy)
            self.assertTrue(ok_legacy, f'Legacy short ID 1411 should not cause validator error: {res_legacy.errors}')


if __name__ == '__main__':
    unittest.main()
