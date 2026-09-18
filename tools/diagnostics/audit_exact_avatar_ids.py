#!/usr/bin/env python3
"""Audit every positive explicit dialogue unit_id against avatar_assets.json.

Audit-only diagnostic. It intentionally does not use speaker-name inference or
numeric-range eligibility. Every positive integer explicit unit_id is required.
"""

from __future__ import annotations

import json
import argparse
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORY_DIR = ROOT / "dashboard" / "story"
MANIFEST_PATH = ROOT / "dashboard" / "data" / "avatar_assets.json"
ICON_DIR = ROOT / "dashboard" / "icon" / "unit"


def main(output_path: Path) -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assets = manifest.get("assets", [])
    registry = {
        int(a["unit_id"]): a
        for a in assets
        if a.get("usage") == "dialogue" and a.get("unit_id") is not None
    }

    occurrences: Counter[int] = Counter()
    story_ids: dict[int, set[int]] = defaultdict(set)
    speakers: dict[int, Counter[str]] = defaultdict(Counter)
    samples: dict[int, list[dict]] = defaultdict(list)

    story_files = sorted(
        (p for p in STORY_DIR.glob("*.json") if p.stem.isdigit()),
        key=lambda p: int(p.stem),
    )

    parse_errors = []
    invalid_positive_candidates = []

    for path in story_files:
        sid = int(path.stem)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            parse_errors.append({"story_id": sid, "error": repr(exc)})
            continue

        rows = data if isinstance(data, list) else data.get("dialogue", [])
        if not isinstance(rows, list):
            continue

        for index, row in enumerate(rows):
            if not isinstance(row, dict) or row.get("type") != "dialogue":
                continue
            raw_uid = row.get("unit_id")
            if raw_uid is None:
                continue
            try:
                uid = int(raw_uid)
            except (TypeError, ValueError):
                invalid_positive_candidates.append(
                    {"story_id": sid, "index": index, "unit_id": raw_uid}
                )
                continue
            if uid <= 0:
                continue

            occurrences[uid] += 1
            story_ids[uid].add(sid)
            speaker = str(row.get("name") or "")
            speakers[uid][speaker] += 1
            if len(samples[uid]) < 3:
                samples[uid].append(
                    {
                        "story_id": sid,
                        "index": index,
                        "speaker": speaker,
                        "words": str(row.get("words") or "")[:80],
                    }
                )

    required_ids = set(occurrences)
    registry_ids = set(registry)
    missing = sorted(required_ids - registry_ids)
    registered_required = sorted(required_ids & registry_ids)

    active_missing_local = []
    placeholder_required = []
    for uid in registered_required:
        asset = registry[uid]
        status = asset.get("status")
        if status == "placeholder_only":
            placeholder_required.append(uid)
            continue
        if status == "active":
            filename = asset.get("filename")
            if not filename or not (ICON_DIR / filename).exists():
                active_missing_local.append(
                    {"unit_id": uid, "filename": filename}
                )

    missing_details = []
    for uid in missing:
        candidate = f"{uid:06d}.png"
        candidate_path = ICON_DIR / candidate
        missing_details.append(
            {
                "unit_id": uid,
                "occurrences": occurrences[uid],
                "story_count": len(story_ids[uid]),
                "story_ids_sample": sorted(story_ids[uid])[:10],
                "speaker_sample": [
                    {"speaker": name, "count": count}
                    for name, count in speakers[uid].most_common(5)
                ],
                "dialogue_samples": samples[uid],
                "local_candidate_filename": candidate,
                "local_candidate_exists": candidate_path.exists(),
                "local_candidate_size": candidate_path.stat().st_size
                if candidate_path.exists()
                else None,
            }
        )

    short_required = sorted(uid for uid in required_ids if uid < 100000)
    short_missing = sorted(uid for uid in missing if uid < 100000)
    ge100k_missing = sorted(uid for uid in missing if uid >= 100000)

    report = {
        "story_files_scanned": len(story_files),
        "parse_errors": parse_errors,
        "distinct_required_exact_ids": len(required_ids),
        "total_positive_unit_id_occurrences": sum(occurrences.values()),
        "dialogue_registry_ids": len(registry_ids),
        "required_registered": len(required_ids & registry_ids),
        "missing_registry_count": len(missing),
        "missing_registry_ids": missing,
        "short_required_count": len(short_required),
        "short_required_ids": short_required,
        "short_missing_registry_count": len(short_missing),
        "short_missing_registry_ids": short_missing,
        "ge100000_missing_registry_count": len(ge100k_missing),
        "ge100000_missing_registry_ids": ge100k_missing,
        "placeholder_required_count": len(placeholder_required),
        "placeholder_required_ids": placeholder_required,
        "active_registered_missing_local_count": len(active_missing_local),
        "active_registered_missing_local": active_missing_local,
        "invalid_unit_id_rows": invalid_positive_candidates,
        "missing_details": missing_details,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== EXACT_AVATAR_ID_AUDIT_BEGIN ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("=== EXACT_AVATAR_ID_AUDIT_END ===")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "data" / "avatar_exact_id_audit_20260918.json",
        help="machine-readable audit report path",
    )
    args = parser.parse_args()
    raise SystemExit(main(args.output))
