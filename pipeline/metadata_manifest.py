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
PROVENANCE_REQUIRED_KEYS = [
    "truth_version",
    "cdn_bundle_hash",
    "bundle_name",
    "cmd1_present",
    "cmd1_nonempty",
    "cmd32_present",
    "cmd32_nonempty"
]


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


def create_empty_manifest(truth_version: str = "00600025") -> Dict[str, Any]:
    """建立符合 D2.2 契約之空白 Manifest 字典物件"""
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
    4. 每個 episode 必須包含必要欄位與合規 provenance
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

    episodes = manifest.get("episodes", {})
    if not isinstance(episodes, dict):
        raise ValueError("[ContractError] episodes 必須為字典物件")

    count = manifest.get("episode_count")
    if count != len(episodes):
        raise ValueError(f"[ContractError] episode_count ({count}) 與 len(episodes) ({len(episodes)}) 不一致！")

    num_pattern = re.compile(r"^[0-9]+$")
    for sid, ep in episodes.items():
        if not num_pattern.match(str(sid)):
            raise ValueError(f"[ContractError] 話數 ID 鍵名必須為純數字字串: {sid}")

        if not isinstance(ep, dict):
            raise ValueError(f"[ContractError] 話數 {sid} 之節點必須為字典物件")

        required_ep_keys = {"chapter_title", "official_synopsis", "subtitle", "provenance"}
        ep_keys = set(ep.keys())
        if not required_ep_keys.issubset(ep_keys):
            raise ValueError(f"[ContractError] 話數 {sid} 欄位不符: 缺少 {required_ep_keys - ep_keys}")

        if ep["chapter_title"] is not None and not isinstance(ep["chapter_title"], str):
            raise ValueError(f"[ContractError] 話數 {sid} chapter_title 必須為 string 或 null")
        if ep["official_synopsis"] is not None and not isinstance(ep["official_synopsis"], str):
            raise ValueError(f"[ContractError] 話數 {sid} official_synopsis 必須為 string 或 null")
        if ep["subtitle"] is not None and not isinstance(ep["subtitle"], str):
            raise ValueError(f"[ContractError] 話數 {sid} subtitle 必須為 string 或 null")

        prov = ep.get("provenance")
        if not isinstance(prov, dict):
            raise ValueError(f"[ContractError] 話數 {sid} provenance 必須為字典物件")

        prov_keys = set(prov.keys())
        for req_k in PROVENANCE_REQUIRED_KEYS:
            if req_k not in prov_keys:
                raise ValueError(f"[ContractError] 話數 {sid} provenance 缺少必要欄位: {req_k}")

        for flag_k in ["cmd1_present", "cmd1_nonempty", "cmd32_present", "cmd32_nonempty"]:
            if not isinstance(prov[flag_k], bool):
                raise ValueError(f"[ContractError] 話數 {sid} provenance.{flag_k} 必須為布林值")

        if prov["cmd1_present"] and prov["cmd1_nonempty"]:
            if not ep["official_synopsis"]:
                raise ValueError(f"[ContractError] 話數 {sid} 標記 cmd1_nonempty 為 True 但 official_synopsis 為空！")
        else:
            if ep["official_synopsis"] is not None:
                raise ValueError(f"[ContractError] 話數 {sid} cmd1 為空或缺失，official_synopsis 必須嚴格規整為 null！")


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
        if "bundle_sha256" in prov and prov["bundle_sha256"] is not None:
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


def load_metadata_manifest(filepath: Path = MANIFEST_PATH) -> Dict[str, Any]:
    """讀取 Manifest 檔案，若不存在則回傳空白骨架"""
    if not filepath.exists():
        return create_empty_manifest()
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
    manifest = load_metadata_manifest(filepath)
    if truth_version:
        manifest["truth_version"] = str(truth_version)

    sid_str = str(story_id)
    manifest["episodes"][sid_str] = entry
    manifest["episode_count"] = len(manifest["episodes"])

    return save_canonical_manifest(manifest, filepath)


if __name__ == '__main__':
    print('metadata_manifest module loaded.')
