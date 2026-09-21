#!/usr/bin/env python3
"""Focused contracts for Pipeline Safety Hardening Phase 1 (no network or Git)."""

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from pipeline.bundle import ensure_destination_parent
from pipeline.coverage import CoverageAnalysisStatus, CoverageResult, FreshnessStatus, evaluate_freshness
from pipeline.deploy import _get_internal_deploy_authorization, run_deploy
from pipeline.fetch import TruthVersionProbeResult, get_truth_version
from pipeline.update import check_and_sync_upstream
import pcrd_fetch


def make_valid_db(path):
    conn = sqlite3.connect(path)
    try:
        for table in ("unit_data", "chara_story_status", "unit_skill_data"):
            conn.execute(f"CREATE TABLE {table} (id INTEGER)")
            conn.execute(f"INSERT INTO {table} VALUES (1)")
        conn.commit()
    finally:
        conn.close()
    return path.read_bytes()


class TestPipelineSafetyHardeningPhase1(unittest.TestCase):
    def test_offline_history_and_db_fallbacks_are_not_remote_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "redive_tw.db"
            make_valid_db(db_path)
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE app_version (key TEXT, string_value TEXT)")
            conn.execute("INSERT INTO app_version VALUES ('asset_version', '00610008')")
            conn.commit()
            conn.close()
            history = root / "versions" / "version_history.json"
            history.parent.mkdir()
            history.write_text(json.dumps({"last_version": "00610007"}), encoding="utf-8")

            with patch.object(pcrd_fetch, "DB_PATH", str(db_path)), \
                 patch("pcrd_fetch.urllib.request.urlopen", side_effect=OSError("offline")):
                probe = pcrd_fetch.probe_truth_version()
                self.assertFalse(probe.confirmed_remote)
                self.assertIsNone(probe.version)
                self.assertEqual(pcrd_fetch._get_sonet_ver(), "00610007")
                self.assertIsNone(get_truth_version())
                self.assertEqual(
                    evaluate_freshness(probe.version, "00610007", True).status,
                    FreshnessStatus.REMOTE_UNREACHABLE,
                )

            history.unlink()
            with patch.object(pcrd_fetch, "DB_PATH", str(db_path)), \
                 patch("pcrd_fetch.urllib.request.urlopen", side_effect=OSError("offline")):
                self.assertEqual(pcrd_fetch._get_sonet_ver(), "00610008")

    def test_confirmed_remote_equal_local_remains_confirmed_current(self):
        response = MagicMock()
        response.read.return_value = b'{"data":{"truthVersion":"00610007"}}'
        response.__enter__.return_value = response
        with patch("pcrd_fetch.urllib.request.urlopen", return_value=response):
            probe = pcrd_fetch.probe_truth_version()
        self.assertTrue(probe.confirmed_remote)
        self.assertEqual(
            evaluate_freshness(probe.version, "00610007", True).status,
            FreshnessStatus.CONFIRMED_CURRENT,
        )

    def test_remote_truth_version_requires_an_eight_digit_string(self):
        for value, expected_confirmed in [
            ("00600025", True),
            ("invalid", False),
            ("600025", False),
            ("", False),
            (None, False),
            (600025, False),
        ]:
            response = MagicMock()
            response.read.return_value = json.dumps({"data": {"truthVersion": value}}).encode("utf-8")
            response.__enter__.return_value = response
            with self.subTest(value=value), patch("pcrd_fetch.urllib.request.urlopen", return_value=response):
                probe = pcrd_fetch.probe_truth_version()
            self.assertEqual(probe.confirmed_remote, expected_confirmed)
            if expected_confirmed:
                self.assertEqual(probe.version, value)
            else:
                self.assertIsNone(probe.version)

    def test_offline_required_story_gap_stops_before_cdn_story_sync(self):
        coverage = CoverageResult(
            analysis_status=CoverageAnalysisStatus.VALID,
            analysis_errors=[], source_status={}, local_present_count=1,
            required_total_count=1, optional_total_count=0, unknown_expected_count=0,
            missing_required_count=1, missing_optional_count=0, missing_unknown_count=0,
            missing_required_ids=[9999999], missing_optional_ids=[], missing_unknown_ids=[],
        )
        with patch("pipeline.fetch.probe_truth_version", return_value=TruthVersionProbeResult(None, "test", False, "offline")), \
             patch("pipeline.update.analyze_coverage", return_value=coverage), \
             patch("tools.pcrd_fetch.load_story_manifest_bundle_refs") as load_manifest:
            ok, freshness, _ = check_and_sync_upstream(dry_run=True)
        self.assertFalse(ok)
        self.assertFalse(freshness.confirmed)
        self.assertEqual(freshness.status, FreshnessStatus.REMOTE_UNREACHABLE)
        load_manifest.assert_not_called()

    def test_invalid_download_preserves_existing_db_and_reports_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "redive_tw.db"
            original = make_valid_db(db_path)
            with patch.object(pcrd_fetch, "DB_PATH", str(db_path)), \
                 patch.object(pcrd_fetch, "_http_get", return_value=b"not sqlite"), \
                 patch.object(pcrd_fetch, "_write_output"):
                result = pcrd_fetch.cmd_update_db(SimpleNamespace(output="ignored"))
            self.assertEqual(result["status"], "error")
            self.assertEqual(db_path.read_bytes(), original)
            self.assertFalse((root / "redive_tw.db.download.tmp").exists())

    def test_valid_download_replaces_existing_db_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "redive_tw.db"
            db_path.write_bytes(b"old database")
            expected = make_valid_db(root / "downloaded.db")
            with patch.object(pcrd_fetch, "DB_PATH", str(db_path)), \
                 patch.object(pcrd_fetch, "_http_get", return_value=expected), \
                 patch.object(pcrd_fetch, "_write_output"):
                result = pcrd_fetch.cmd_update_db(SimpleNamespace(output="ignored"))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(db_path.read_bytes(), expected)
            self.assertFalse((root / "redive_tw.db.download.tmp").exists())

    def test_unauthorized_deploy_never_reaches_validation_or_git(self):
        with patch("pipeline.deploy.validate_story_map") as validate, \
             patch("pipeline.deploy._run_git_in_dist") as git:
            self.assertFalse(run_deploy())
        validate.assert_not_called()
        git.assert_not_called()

    def test_direct_deploy_cli_is_rejected_before_any_git_action(self):
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "pipeline.deploy", "--dry-run"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Direct deployment is disabled", completed.stderr)

    def test_authorized_internal_deploy_primitive_remains_usable(self):
        with patch("pipeline.deploy.validate_story_map", return_value=True):
            self.assertTrue(run_deploy(dry_run=True, authorization=_get_internal_deploy_authorization()))

    def test_dry_run_does_not_create_dialogue_override_parent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "dist" / "icon" / "story_unit" / "1.webp"
            ensure_destination_parent(destination, dry_run=True)
            self.assertFalse(destination.parent.exists())
            ensure_destination_parent(destination, dry_run=False)
            self.assertTrue(destination.parent.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
