# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.story_sync import ensure_required_story_coverage


class TestRequiredStoryAutoSync(unittest.TestCase):
    def _coverage(self, missing):
        return SimpleNamespace(
            missing_required_ids=list(missing),
            missing_required_count=len(missing),
            analysis_status="VALID",
        )

    @patch("tools.pcrd_fetch.sync_story_batch_with_metadata")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    def test_dry_run_checks_manifest_without_fetching_bundles(self, mock_refs, mock_sync):
        coverage = self._coverage([1001, 1002])
        mock_refs.return_value = {1001: object(), 1002: object()}

        result, effective = ensure_required_story_coverage(
            coverage,
            truth_version="00610007",
            dry_run=True,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.fetchable_ids, [1001, 1002])
        self.assertEqual(result.synced_ids, [])
        self.assertIs(effective, coverage)
        mock_sync.assert_not_called()

    @patch("tools.pcrd_fetch.sync_story_batch_with_metadata")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    def test_missing_manifest_entry_fails_closed(self, mock_refs, mock_sync):
        coverage = self._coverage([1001, 1002])
        mock_refs.return_value = {1001: object()}

        result, effective = ensure_required_story_coverage(
            coverage,
            truth_version="00610007",
            dry_run=False,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.unavailable_ids, [1002])
        self.assertIs(effective, coverage)
        mock_sync.assert_not_called()

    @patch("pipeline.coverage.analyze_coverage")
    @patch("tools.pcrd_fetch.sync_story_batch_with_metadata")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    def test_normal_sync_rechecks_coverage(self, mock_refs, mock_sync, mock_analyze):
        coverage = self._coverage([1001, 1002])
        mock_refs.return_value = {1001: object(), 1002: object()}
        mock_sync.return_value = (True, "abc123", [1001, 1002], [])

        refreshed = self._coverage([])
        mock_analyze.return_value = refreshed

        result, effective = ensure_required_story_coverage(
            coverage,
            truth_version="00610007",
            dry_run=False,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.synced_ids, [1001, 1002])
        self.assertIs(effective, refreshed)
        mock_sync.assert_called_once()
        args, kwargs = mock_sync.call_args
        self.assertEqual(args[0], [1001, 1002])
        self.assertEqual(kwargs["truth_version"], "00610007")
        self.assertTrue(kwargs["write_story_json"])
        self.assertFalse(kwargs["replace_existing"])

    @patch("tools.pcrd_fetch.sync_story_batch_with_metadata")
    @patch("tools.pcrd_fetch.load_story_manifest_bundle_refs")
    def test_failed_batch_stops_without_claiming_success(self, mock_refs, mock_sync):
        coverage = self._coverage([1001, 1002])
        mock_refs.return_value = {1001: object(), 1002: object()}
        mock_sync.return_value = (False, None, [1001], [1002])

        result, effective = ensure_required_story_coverage(
            coverage,
            truth_version="00610007",
            dry_run=False,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.synced_ids, [1001])
        self.assertEqual(result.failed_ids, [1002])
        self.assertIs(effective, coverage)

    def test_missing_truth_version_fails_closed(self):
        coverage = self._coverage([1001])
        result, effective = ensure_required_story_coverage(
            coverage,
            truth_version=None,
            dry_run=False,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.failed_ids, [1001])
        self.assertIs(effective, coverage)


if __name__ == "__main__":
    unittest.main()
