#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Official Story Metadata Manifest (Layer 1 Foundation)
負責管理 dashboard/data/official_story_metadata.json 專屬側車索引清單之：
1. 100% 決定性 Canonical 序列化 (Byte-for-Byte Deterministic JSON)
2. Schema 契約驗證 (頂層 4 欄位，嚴格排除 generated_at 與 metadata_version)
3. 單向 metadata_version 計算原語 (sha256[:12]，供 post-bundle 注入 db_info.json)
4. 原子增量寫入與安全更新流程
"""

import os
import sys
import json
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
MANIFEST_PATH = DASHBOARD_DIR / "data" / "official_story_metadata.json"

SCHEMA_VERSION = "1.0.0"
CANONICAL_TOP_LEVEL_KEYS = ["schema_version", "truth_version", "episode_count", "episodes"]
PROVENANCE_REQUIRED_KEYS = {
    "truth_version",
    "cdn_bundle_hash",
    "bundle_name",
    "cmd1_present",
    "cmd1_nonempty",
    "cmd32_present",
    "cmd32_nonempty",
}
PROVENANCE_ALLOWED_OPTIONAL_KEYS = {"bundle_sha256"}
PROVENANCE_ALL_ALLOWED_KEYS = PROVENANCE_REQUIRED_KEYS | PROVENANCE_ALLOWED_OPTIONAL_KEYS


@dataclass
class EpisodeProvenance:
    truth_version: str
    cdn_bundle_hash: str
    bundle_name: str
    bundle_sha256: Optional[str] = None
    cmd1_present: bool = False
    cmd1_nonempty: bool = False
    cmd32_present: bool = False
    cmd32_nonempty: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "truth_version": self.truth_version,
            "cdn_bundle_hash": self.cdn_bundle_hash,
            "bundle_name": self.bundle_name,
            "cmd1_present": self.cmd1_present,
            "cmd1_nonempty": self.cmd1_nonempty,
            "cmd32_present": self.cmd32_present,
            "cmd32_nonempty": self.cmd32_nonempty
        }
        if self.bundle_sha256 is not None:
            d["bundle_sha256"] = self.bundle_sha256
        return d


@dataclass
class OfficialEpisodeMetadata:
    story_id: int
    chapter_title: Optional[str]
    official_synopsis: Optional[str]
    subtitle: Optional[str]
    provenance: Union[EpisodeProvenance, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        prov_dict = self.provenance.to_dict() if isinstance(self.provenance, EpisodeProvenance) else dict(self.provenance)
        return {
            "chapter_title": self.chapter_title,
            "official_synopsis": self.official_synopsis,
            "subtitle": self.subtitle,
            "provenance": prov_dict
        }


@dataclass
class OfficialStoryMetadataManifest:
    truth_version: str
    episodes: Dict[Union[int, str], Union[OfficialEpisodeMetadata, Dict[str, Any]]] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if not isinstance(self.truth_version, str) or not re.match(r"^[0-9]{8}$", self.truth_version):
            raise ValueError(f"[ContractError] 無效的 truth_version: {self.truth_version}，必須為 8 位數字字串")

    @property
    def episode_count(self) -> int:
        return len(self.episodes)

    def to_dict(self) -> Dict[str, Any]:
        ep_dicts = {}
        for sid, ep in self.episodes.items():
            sid_str = str(sid)
            if isinstance(ep, OfficialEpisodeMetadata):
                ep_dicts[sid_str] = ep.to_dict()
            else:
                ep_dicts[sid_str] = dict(ep)
        return {
            "schema_version": self.schema_version,
            "truth_version": str(self.truth_version),
            "episode_count": len(ep_dicts),
            "episodes": ep_dicts
        }

    def to_canonical_json(self) -> str:
        return serialize_canonical_manifest(self.to_dict())


def create_empty_manifest(truth_version: str) -> Dict[str, Any]:
    """建立符合 D2.2 契約之空白 Manifest 字典物件（嚴禁預設值，強制顯式傳入合規 8 碼 TruthVersion）"""
    if not isinstance(truth_version, str) or not re.match(r"^[0-9]{8}$", truth_version):
        raise ValueError(f"[ContractError] 無效的 truth_version: {truth_version}，必須為 8 位數字字串")
    return {
        "schema_version": SCHEMA_VERSION,
        "truth_version": str(truth_version),
        "episode_count": 0,
        "episodes": {}
    }


def validate_manifest_dict_contract(manifest: Dict[str, Any]) -> None:
    """
    對 Manifest 字典物件進行嚴格契約斷言：
    1. 頂層僅允許 Canonical 4 欄位，禁止 generated_at 與 metadata_version (避免 self-hash circularity)
    2. episode_count 必須嚴格等於 len(episodes)
    3. episodes 鍵名必須全為數字字串
    4. 每個 episode 必須包含合法 4 欄位，嚴禁額外欄位 (additionalProperties: false)
    5. provenance 必須符合必填 7 欄位 + 可選 1 欄位 (bundle_sha256 格式驗證)
    6. 標記蘊含規則：nonempty -> present
    7. synopsis / subtitle 嚴格 null contract
    """
    if not isinstance(manifest, dict):
        raise ValueError("[ContractError] Manifest 頂層必須為字典物件")

    top_keys = set(manifest.keys())
    expected_top_keys = set(CANONICAL_TOP_LEVEL_KEYS)
    if top_keys != expected_top_keys:
        missing = expected_top_keys - top_keys
        extra = top_keys - expected_top_keys
        raise ValueError(
            f"[ContractError] Manifest 頂層欄位不符合規範: 缺少 {missing}, 多出 {extra}。"
            f" 注意：禁止包含 generated_at 與 metadata_version。"
        )

    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"[ContractError] 不支援的 schema_version: {manifest.get('schema_version')}")

    tv = manifest.get("truth_version")
    if not isinstance(tv, str) or not re.match(r"^[0-9]{8}$", tv):
        raise ValueError(f"[ContractError] Manifest 頂層 truth_version 必須為 8 位數字字串: {tv}")

    episodes = manifest.get("episodes", {})
    if not isinstance(episodes, dict):
        raise ValueError("[ContractError] episodes 必須為字典物件")

    count = manifest.get("episode_count")
    if count != len(episodes):
        raise ValueError(f"[ContractError] episode_count ({count}) 與 len(episodes) ({len(episodes)}) 不一致！")

    num_pattern = re.compile(r"^[0-9]+$")
    allowed_ep_keys = {"chapter_title", "official_synopsis", "subtitle", "provenance"}

    for sid, ep in episodes.items():
        if not num_pattern.match(str(sid)):
            raise ValueError(f"[ContractError] 話數 ID 鍵名必須為純數字字串: {sid}")

        if not isinstance(ep, dict):
            raise ValueError(f"[ContractError] 話數 {sid} 之節點必須為字典物件")

        ep_keys = set(ep.keys())
        if ep_keys != allowed_ep_keys:
            missing = allowed_ep_keys - ep_keys
            extra = ep_keys - allowed_ep_keys
            raise ValueError(
                f"[ContractError] 話數 {sid} 欄位不符 (additionalProperties: false): 缺少 {missing}, 多出 {extra}"
            )

        c_title = ep["chapter_title"]
        if c_title is not None:
            if not isinstance(c_title, str):
                raise ValueError(f"[ContractError] 話數 {sid} chapter_title 必須為 string 或 null")
            if not c_title.strip():
                raise ValueError(f"[ContractError] 話數 {sid} chapter_title 為空字串或純空白字串，必須規整為 null")

        if ep["official_synopsis"] is not None and not isinstance(ep["official_synopsis"], str):
            raise ValueError(f"[ContractError] 話數 {sid} official_synopsis 必須為 string 或 null")
        if ep["subtitle"] is not None and not isinstance(ep["subtitle"], str):
            raise ValueError(f"[ContractError] 話數 {sid} subtitle 必須為 string 或 null")

        prov = ep.get("provenance")
        if not isinstance(prov, dict):
            raise ValueError(f"[ContractError] 話數 {sid} provenance 必須為字典物件")

        prov_keys = set(prov.keys())
        missing_prov = PROVENANCE_REQUIRED_KEYS - prov_keys
        if missing_prov:
            raise ValueError(f"[ContractError] 話數 {sid} provenance 缺少必要欄位: {missing_prov}")
        extra_prov = prov_keys - PROVENANCE_ALL_ALLOWED_KEYS
        if extra_prov:
            raise ValueError(
                f"[ContractError] 話數 {sid} provenance 包含未允許之欄位 (additionalProperties: false): {extra_prov}"
            )

        # 欄位值規格驗證
        p_tv = prov["truth_version"]
        if not isinstance(p_tv, str) or not re.match(r"^[0-9]{8}$", p_tv):
            raise ValueError(f"[ContractError] 話數 {sid} provenance.truth_version 必須為 8 位數字字串: {p_tv}")

        p_cbh = prov["cdn_bundle_hash"]
        if not isinstance(p_cbh, str) or not p_cbh.strip():
            raise ValueError(f"[ContractError] 話數 {sid} provenance.cdn_bundle_hash 必須為非空字串")

        p_bn = prov["bundle_name"]
        if not isinstance(p_bn, str) or not p_bn.strip():
            raise ValueError(f"[ContractError] 話數 {sid} provenance.bundle_name 必須為非空字串")

        if "bundle_sha256" in prov:
            p_sha = prov["bundle_sha256"]
            if not isinstance(p_sha, str) or not re.match(r"^[0-9a-fA-F]{64}$", p_sha):
                raise ValueError(
                    f"[ContractError] 話數 {sid} provenance.bundle_sha256 存在時必須為 64 位十六進位字串，"
                    f"不接受 null、空字串或無效格式: {p_sha!r}"
                )

        for flag_k in ["cmd1_present", "cmd1_nonempty", "cmd32_present", "cmd32_nonempty"]:
            if not isinstance(prov[flag_k], bool):
                raise ValueError(f"[ContractError] 話數 {sid} provenance.{flag_k} 必須為布林值")

        # 蘊含關係檢查 (Invariants)
        if prov["cmd1_nonempty"] and not prov["cmd1_present"]:
            raise ValueError(f"[ContractError] 話數 {sid} cmd1_nonempty 為 True 但 cmd1_present 為 False，違反蘊含關係！")
        if prov["cmd32_nonempty"] and not prov["cmd32_present"]:
            raise ValueError(f"[ContractError] 話數 {sid} cmd32_nonempty 為 True 但 cmd32_present 為 False，違反蘊含關係！")

        # Synopsis Null Contract
        if prov["cmd1_present"] and prov["cmd1_nonempty"]:
            if not isinstance(ep["official_synopsis"], str) or not ep["official_synopsis"].strip():
                raise ValueError(f"[ContractError] 話數 {sid} 標記 cmd1 為 nonempty，但 official_synopsis 為空或非字串！")
        else:
            if ep["official_synopsis"] is not None:
                raise ValueError(f"[ContractError] 話數 {sid} cmd1 非 nonempty，official_synopsis 必須嚴格為 null (None)！")

        # Subtitle Null Contract
        if prov["cmd32_present"] and prov["cmd32_nonempty"]:
            if not isinstance(ep["subtitle"], str) or not ep["subtitle"].strip():
                raise ValueError(f"[ContractError] 話數 {sid} 標記 cmd32 為 nonempty，但 subtitle 為空或非字串！")
        else:
            if ep["subtitle"] is not None:
                raise ValueError(f"[ContractError] 話數 {sid} cmd32 非 nonempty，subtitle 必須嚴格為 null (None)！")


def serialize_canonical_manifest(manifest: Dict[str, Any]) -> str:
    """
    執行 100% 決定性 (Deterministic) 序列化：
    1. 驗證契約
    2. 按數字順序排序 episodes 鍵名
    3. 每個 episode 內部物件按固定鍵序構造
    4. 頂層固定鍵序: schema_version, truth_version, episode_count, episodes
    5. UTF-8、ensure_ascii=False、indent=2、結尾單一換行 \\n
    """
    validate_manifest_dict_contract(manifest)

    sorted_episodes = {}
    for sid in sorted(manifest["episodes"].keys(), key=lambda x: int(x)):
        ep = manifest["episodes"][sid]
        prov = ep["provenance"]
        sorted_prov = {
            "truth_version": prov["truth_version"],
            "cdn_bundle_hash": prov["cdn_bundle_hash"],
            "bundle_name": prov["bundle_name"],
            "cmd1_present": prov["cmd1_present"],
            "cmd1_nonempty": prov["cmd1_nonempty"],
            "cmd32_present": prov["cmd32_present"],
            "cmd32_nonempty": prov["cmd32_nonempty"]
        }
        if "bundle_sha256" in prov:
            sorted_prov["bundle_sha256"] = prov["bundle_sha256"]

        sorted_episodes[sid] = {
            "chapter_title": ep["chapter_title"],
            "official_synopsis": ep["official_synopsis"],
            "subtitle": ep["subtitle"],
            "provenance": sorted_prov
        }

    canonical_obj = {
        "schema_version": manifest["schema_version"],
        "truth_version": manifest["truth_version"],
        "episode_count": len(sorted_episodes),
        "episodes": sorted_episodes
    }

    serialized = json.dumps(canonical_obj, ensure_ascii=False, indent=2)
    return serialized + "\n"


serialize_canonical_json = serialize_canonical_manifest


def compute_manifest_version(manifest_bytes: bytes) -> str:
    """
    計算 Canonical Manifest 之專屬版本號：
    metadata_version = sha256(source_manifest_bytes)[:12]
    """
    return hashlib.sha256(manifest_bytes).hexdigest()[:12]


def load_metadata_manifest(filepath: Path = MANIFEST_PATH, default_truth_version: Optional[str] = None) -> Dict[str, Any]:
    """讀取 Manifest 檔案，若不存在且提供 default_truth_version 則回傳空白骨架，否則拋出 FileNotFoundError"""
    if not filepath.exists():
        if default_truth_version is not None:
            return create_empty_manifest(default_truth_version)
        raise FileNotFoundError(f"[ContractError] Manifest 檔案不存在: {filepath}，且未提供 default_truth_version")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    validate_manifest_dict_contract(data)
    return data


def save_canonical_manifest(manifest: Dict[str, Any], filepath: Path = MANIFEST_PATH) -> str:
    """
    將 Manifest 決定性序列化並原子寫入目標檔案路徑。
    :return: 序列化後內容之 metadata_version (SHA-256 前12碼)
    """
    content_str = serialize_canonical_manifest(manifest)
    content_bytes = content_str.encode("utf-8")
    m_version = compute_manifest_version(content_bytes)

    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")

    with open(tmp_path, "wb") as f:
        f.write(content_bytes)
    tmp_path.replace(filepath)

    return m_version


def batch_update_manifest_entries(
    entries: Dict[Union[int, str], Dict[str, Any]],
    truth_version: Optional[str] = None,
    filepath: Path = MANIFEST_PATH
) -> str:
    """
    批次原子插入或更新多話元數據至 Manifest：
    1. 在記憶體中載入現有 manifest（若不存在且有 truth_version 則建立空 manifest）
    2. 批次更新所有 entries，更新 episode_count
    3. 若提供 truth_version 則更新頂層 truth_version
    4. 驗證契約合規性（契約失敗則直接拋出例外，完全不寫入檔案）
    5. 透過 save_canonical_manifest 原子寫入檔案
    6. 回傳更新後之 metadata_version
    """
    manifest = load_metadata_manifest(filepath, default_truth_version=truth_version)
    if truth_version:
        manifest["truth_version"] = str(truth_version)

    for sid, entry in entries.items():
        sid_str = str(sid)
        manifest["episodes"][sid_str] = entry

    manifest["episode_count"] = len(manifest["episodes"])
    validate_manifest_dict_contract(manifest)
    return save_canonical_manifest(manifest, filepath)


def update_manifest_entry(
    story_id: int | str,
    entry: Dict[str, Any],
    truth_version: Optional[str] = None,
    filepath: Path = MANIFEST_PATH
) -> str:
    """
    增量插入或更新單一話數元數據至 Manifest。
    :return: 更新後之 metadata_version
    """
    return batch_update_manifest_entries({story_id: entry}, truth_version=truth_version, filepath=filepath)


def run_cli():
    """CLI 入口，支援官方元數據側車清單之查詢與回補程序"""
    import argparse
    parser = argparse.ArgumentParser(
        description="PCRD Official Story Metadata Manifest 管理與回補工具"
    )
    parser.add_argument("--rebuild", action="store_true", help="重建/回補官方元數據側車清單 (需連線 CDN)")
    parser.add_argument("--sample", type=int, default=None, help="僅針對前 N 話樣本進行回補測試")
    parser.add_argument("--truth-version", type=str, default=None, help="指定 8 位數字 TruthVersion (選填)")
    parser.add_argument("--output", type=str, default=None, help="輸出檔案路徑 (預設為 dashboard/data/official_story_metadata.json)")

    args = parser.parse_args()

    if args.rebuild:
        print("=" * 60)
        print("⚡ [Bootstrap / Backfill] 官方元數據側車清單回補程序")
        print("=" * 60)
        out_path = Path(args.output) if args.output else MANIFEST_PATH
        print(f"  目標檔案: {out_path}")
        print("  網路需求: 需要連線 So-net CDN (storydata2_assetmanifest 與 pool/AssetBundles)")

        tv = args.truth_version
        if not tv:
            try:
                from pipeline.fetch import get_truth_version
                tv = get_truth_version()
            except Exception as e:
                print(f"❌ 無法探測 TruthVersion: {e}", file=sys.stderr)
                sys.exit(1)

        print(f"  確定 TruthVersion 快照: {tv}")

        try:
            from tools.pcrd_fetch import load_story_manifest_bundle_refs, fetch_story_json_by_id
            bundle_refs = load_story_manifest_bundle_refs(truth_version=tv)
        except Exception as e:
            print(f"❌ 載入 Story Manifest 失敗: {e}", file=sys.stderr)
            sys.exit(1)

        all_story_ids = sorted(bundle_refs.keys())
        total_available = len(all_story_ids)
        print(f"  CDN 上共有 {total_available} 話故事 AssetBundle 索引")

        if args.sample:
            target_story_ids = all_story_ids[:args.sample]
            print(f"  [樣本模式] 僅處理前 {len(target_story_ids)} 話")
        else:
            print(f"⚠️  警告: 即將處理全量 {total_available} 話！")
            confirm = input("確定要執行全量 CDN 回補嗎？(輸入 YES 繼續): ")
            if confirm.strip() != "YES":
                print("操作已取消。")
                sys.exit(0)
            target_story_ids = all_story_ids

        collected_entries = {}
        failed_count = 0
        print(f"  開始抓取並萃取元數據...")
        for i, sid in enumerate(target_story_ids, 1):
            ref = bundle_refs[sid]
            res = fetch_story_json_by_id(sid, bundle_ref=ref, extract_metadata=True, timeout=15)
            if res.status == "OK" and res.metadata:
                collected_entries[sid] = res.metadata.to_dict()
                print(f"  [{i}/{len(target_story_ids)}] story_id={sid} OK")
            else:
                failed_count += 1
                print(f"  [{i}/{len(target_story_ids)}] story_id={sid} FAILED: {res.error_message}", file=sys.stderr)

        if failed_count > 0:
            print(f"❌ 回補過程中有 {failed_count} 話失敗，基於全有全無原子原則，不寫入 Manifest！", file=sys.stderr)
            sys.exit(1)

        print(f"  所有 {len(collected_entries)} 話萃取完成，正在原子寫入 Manifest...")
        m_ver = batch_update_manifest_entries(collected_entries, truth_version=tv, filepath=out_path)
        print(f"✅ 回補完成！已原子寫入: {out_path} (metadata_version: {m_ver})")
    else:
        parser.print_help()


if __name__ == '__main__':
    run_cli()
