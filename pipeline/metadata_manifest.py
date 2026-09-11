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
from typing import Dict, Any, Optional, Union, List, Tuple, Set, Sequence, Iterable
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
    filepath: Path = MANIFEST_PATH,
    replace_existing: bool = False
) -> str:
    """
    批次原子插入或更新多話元數據至 Manifest：
    1. 若 replace_existing=True，建立乾淨的空 manifest (Replacement Semantics)；
       若為 False，則在記憶體中載入現有 manifest（若不存在且有 truth_version 則建立空 manifest）
    2. 驗證所有 entries 之 provenance.truth_version 是否與傳入之 snapshot truth_version 一致
    3. 批次更新所有 entries，更新 episode_count
    4. 若提供 truth_version 則更新頂層 truth_version
    5. 驗證契約合規性（契約失敗則直接拋出例外，完全不寫入檔案）
    6. 透過 save_canonical_manifest 原子寫入檔案
    7. 回傳更新後之 metadata_version
    """
    if replace_existing:
        if not truth_version:
            raise ValueError("replace_existing=True 時必須提供有效的 truth_version！")
        manifest = create_empty_manifest(truth_version=str(truth_version))
    else:
        manifest = load_metadata_manifest(filepath, default_truth_version=truth_version)

    if truth_version:
        str_tv = str(truth_version)
        manifest["truth_version"] = str_tv
        for sid, entry in entries.items():
            prov = entry.get("provenance", {}) if isinstance(entry, dict) else {}
            entry_tv = prov.get("truth_version")
            if entry_tv and entry_tv != str_tv:
                raise ValueError(
                    f"話數 {sid} provenance.truth_version ({entry_tv}) 與本次批次 snapshot truth_version ({str_tv}) 不一致！"
                )

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


CHECKPOINT_SCHEMA_VERSION = "1.0.0"
CHECKPOINT_STATE_FILENAME = "official_story_metadata_bootstrap_state.json"
CHECKPOINT_DATA_FILENAME = "official_story_metadata_bootstrap_checkpoint.json"


def compute_target_fingerprint(target_ids: Iterable[int]) -> str:
    """計算目標話數集合之決定性 SHA-256 指紋"""
    sorted_str = ",".join(str(x) for x in sorted(target_ids))
    return hashlib.sha256(sorted_str.encode("utf-8")).hexdigest()


def save_bootstrap_checkpoint(
    checkpoint_dir: Path,
    target_ids: List[int],
    truth_version: str,
    episodes: Dict[Any, Any],
    status: str = "IN_PROGRESS"
) -> Tuple[Path, Path]:
    """
    以原子寫入 (tmp -> replace) 儲存 Bootstrap Checkpoint 狀態與資料檔案。
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    state_file = checkpoint_dir / CHECKPOINT_STATE_FILENAME
    data_file = checkpoint_dir / CHECKPOINT_DATA_FILENAME

    target_fingerprint = compute_target_fingerprint(target_ids)
    episodes_dict = {str(k): v for k, v in episodes.items()}

    state_obj = {
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "status": status,
        "truth_version": str(truth_version),
        "target_count": len(target_ids),
        "target_ids_sha256": target_fingerprint,
        "completed_count": len(episodes_dict)
    }

    data_obj = {
        "schema_version": SCHEMA_VERSION,
        "truth_version": str(truth_version),
        "episode_count": len(episodes_dict),
        "episodes": episodes_dict
    }

    # 原子寫入 data
    tmp_data = checkpoint_dir / f"{CHECKPOINT_DATA_FILENAME}.tmp"
    with open(tmp_data, "w", encoding="utf-8") as f:
        json.dump(data_obj, f, ensure_ascii=False, indent=2)
    tmp_data.replace(data_file)

    # 原子寫入 state
    tmp_state = checkpoint_dir / f"{CHECKPOINT_STATE_FILENAME}.tmp"
    with open(tmp_state, "w", encoding="utf-8") as f:
        json.dump(state_obj, f, ensure_ascii=False, indent=2)
    tmp_state.replace(state_file)

    return state_file, data_file


def load_and_validate_bootstrap_checkpoint(
    checkpoint_dir: Path,
    target_ids: List[int],
    requested_truth_version: str
) -> Dict[int, Any]:
    """
    載入並以嚴格契約驗證 Bootstrap Checkpoint：
    1. state 與 data 檔案存在性
    2. state 結構與欄位規格
    3. truth_version 單一快照比對
    4. target_count 與 target_ids_sha256 指紋比對
    5. validate_manifest_dict_contract 契約檢驗
    6. episodes 節點話數 ID 必須為數字且為 target_ids 之子集
    7. 所有 entry provenance truth_version 比對
    若有任一不符，Fail Loudly 拋出 ValueError，絕不發起網路請求與 production 寫入。
    """
    state_file = checkpoint_dir / CHECKPOINT_STATE_FILENAME
    data_file = checkpoint_dir / CHECKPOINT_DATA_FILENAME

    if not state_file.exists():
        raise FileNotFoundError(f"[CheckpointError] Checkpoint 狀態檔案不存在: {state_file}")
    if not data_file.exists():
        raise FileNotFoundError(f"[CheckpointError] Checkpoint 資料檔案不存在: {data_file}")

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        raise ValueError(f"[CheckpointError] Checkpoint 狀態檔案損壞: {e}")

    try:
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"[CheckpointError] Checkpoint 資料檔案損壞: {e}")

    if not isinstance(state, dict) or not isinstance(data, dict):
        raise ValueError("[CheckpointError] Checkpoint state 與 data 頂層必須為字典物件")

    if state.get("checkpoint_schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError(f"[CheckpointError] 不支援之 Checkpoint schema version: {state.get('checkpoint_schema_version')}")

    if state.get("truth_version") != str(requested_truth_version):
        raise ValueError(
            f"[CheckpointError] Checkpoint TruthVersion ({state.get('truth_version')}) "
            f"與請求之版本 ({requested_truth_version}) 不一致！"
        )

    if state.get("target_count") != len(target_ids):
        raise ValueError(
            f"[CheckpointError] Checkpoint target_count ({state.get('target_count')}) "
            f"與當前目標數量 ({len(target_ids)}) 不一致！"
        )

    expected_fingerprint = compute_target_fingerprint(target_ids)
    if state.get("target_ids_sha256") != expected_fingerprint:
        raise ValueError(
            f"[CheckpointError] Checkpoint target_ids_sha256 ({state.get('target_ids_sha256')}) "
            f"與當前話數宇宙指紋 ({expected_fingerprint}) 不相符！"
        )

    # 驗證 Data 契約 (複用既有 validate_manifest_dict_contract)
    validate_manifest_dict_contract(data)

    episodes = data.get("episodes", {})
    if state.get("completed_count") != len(episodes):
        raise ValueError(
            f"[CheckpointError] state.completed_count ({state.get('completed_count')}) "
            f"與實際 episodes 數量 ({len(episodes)}) 不符！"
        )

    target_set = set(target_ids)
    validated_episodes: Dict[int, Any] = {}
    for sid_str, ep in episodes.items():
        if not sid_str.isdigit():
            raise ValueError(f"[CheckpointError] Checkpoint 話數 ID 必須為純數字: {sid_str}")
        sid = int(sid_str)
        if sid not in target_set:
            raise ValueError(f"[CheckpointError] Checkpoint 包含非當前預期目標之話數: {sid}")

        prov = ep.get("provenance", {})
        if prov.get("truth_version") != str(requested_truth_version):
            raise ValueError(
                f"[CheckpointError] 話數 {sid} 之 provenance.truth_version ({prov.get('truth_version')}) "
                f"與請求版本 ({requested_truth_version}) 不一致！"
            )

        validated_episodes[sid] = ep

    return validated_episodes


def rebuild_official_metadata(
    truth_version: Optional[str] = None,
    target_story_ids: Optional[List[int]] = None,
    output_path: Optional[Path] = None,
    sample_limit: Optional[int] = None,
    write_story_json: bool = False,
    timeout: int = 30,
    dashboard_dir: Optional[Union[str, Path]] = None,
    resume: bool = False,
    checkpoint_dir: Optional[Union[str, Path]] = None,
    story_retry_attempts: int = 3,
    story_retry_backoff: Optional[List[float]] = None,
    progress_interval: int = 100,
    overwrite_checkpoint: bool = True,
) -> Tuple[bool, Optional[str], int, List[int]]:
    """
    可測試之官方元數據側車重建/回補 Orchestrator (支援 Resumable Checkpoint 與 Network Retry Hardening)：
    1. 驗證 sample_limit (若有傳入必須 > 0)
    2. 安全防禦：若 sample_limit 存在且 output_path 為預設 production 路徑，自動轉向 scratch/ 防止污染
    3. 決定目標 universe：若未指定 target_story_ids，建構 CanonicalStoryUniverse，並嚴格檢查 analysis_status == VALID 且 local_present 非空
    4. 取得 TruthVersion snapshot 與 bundle_refs
    5. Checkpoint 與 Resume 決策：
       - 若 resume=True：嚴格校驗 Checkpoint Identity 與契約，提取已完成 entries
       - 若 resume=False：初始化 0 completed 快照
    6. 依序遍歷 pending_ids：
       - 故事層級重試 (僅限 NETWORK_ERROR，最多 story_retry_attempts 次)
       - 每 progress_interval 話原子更新快照
       - 遇到非網路錯誤或重試耗盡，立即原子保存快照並安全退出 (全有全無原子防護，生產清單零寫入)
    7. 全數成功後一次性原子寫入生產清單，並標記快照為 COMPLETE。
    :return: (success, metadata_version, processed_count, failed_ids)
    """
    import time
    if sample_limit is not None:
        if sample_limit <= 0:
            raise ValueError(f"sample_limit 必須大於 0: {sample_limit}")

    if output_path is not None:
        target_out = Path(output_path)
    elif dashboard_dir is not None:
        target_out = Path(dashboard_dir) / "data" / "official_story_metadata.json"
    else:
        target_out = MANIFEST_PATH

    if sample_limit is not None and target_out == MANIFEST_PATH:
        target_out = PROJECT_ROOT / "scratch" / "sample_official_metadata.json"

    # 1. 決定目標話數 (Metadata Eligible Universe 或顯式傳入)
    if target_story_ids is not None:
        target_ids = list(target_story_ids)
        if not target_ids:
            return False, None, 0, []
    else:
        from pipeline.coverage import build_metadata_eligible_story_universe, CoverageAnalysisStatus
        target_dash = Path(dashboard_dir) if dashboard_dir else DASHBOARD_DIR
        metadata_univ = build_metadata_eligible_story_universe(dashboard_dir=target_dash)
        if metadata_univ.canonical.analysis_status != CoverageAnalysisStatus.VALID:
            # 來源 DEGRADED 或 INVALID，Fail Loudly，禁止 destructive replacement
            return False, None, 0, []
        if len(metadata_univ.missing_required_local_ids) > 0:
            # Required story 缺少本地 story JSON，視為不完整狀態，禁止 replacement
            return False, None, 0, sorted(list(metadata_univ.missing_required_local_ids))
        if len(metadata_univ.eligible_ids) == 0:
            # 空宇宙禁止 replacement
            return False, None, 0, []
        target_ids = sorted(list(metadata_univ.eligible_ids))

    if sample_limit is not None:
        target_ids = target_ids[:sample_limit]
        if not target_ids:
            return False, None, 0, []

    # 2. 取得 TruthVersion
    tv = truth_version
    if not tv:
        try:
            from pipeline.fetch import get_truth_version
            tv = get_truth_version()
        except Exception:
            return False, None, 0, []

    # 3. 載入 bundle_refs
    try:
        from tools.pcrd_fetch import load_story_manifest_bundle_refs, fetch_story_json_by_id
        bundle_refs = load_story_manifest_bundle_refs(truth_version=tv)
    except Exception:
        return False, None, 0, []

    # 檢查是否有預期話數不在 bundle_refs 中
    missing_bundle_ids = [sid for sid in target_ids if sid not in bundle_refs]
    if missing_bundle_ids:
        return False, None, 0, missing_bundle_ids

    # 4. Checkpoint 目錄定位
    if checkpoint_dir is not None:
        chk_dir = Path(checkpoint_dir)
    elif dashboard_dir is not None:
        chk_dir = Path(dashboard_dir).parent / "scratch"
    elif target_out != MANIFEST_PATH:
        chk_dir = target_out.parent / "scratch"
    elif sample_limit is not None:
        chk_dir = PROJECT_ROOT / "scratch" / f"sample_chk_{sample_limit}"
    else:
        chk_dir = PROJECT_ROOT / "scratch"

    state_file = chk_dir / CHECKPOINT_STATE_FILENAME
    data_file = chk_dir / CHECKPOINT_DATA_FILENAME
    chk_exists = state_file.exists() and data_file.exists()

    if resume:
        if not chk_exists:
            return False, None, 0, []
        try:
            checkpoint_episodes = load_and_validate_bootstrap_checkpoint(chk_dir, target_ids, tv)
        except Exception:
            return False, None, 0, []
    else:
        if chk_exists and not overwrite_checkpoint:
            return False, None, 0, []
        checkpoint_episodes = {}
        save_bootstrap_checkpoint(chk_dir, target_ids, tv, {}, status="IN_PROGRESS")

    completed_ids = set(checkpoint_episodes.keys())
    pending_ids = [sid for sid in target_ids if sid not in completed_ids]

    collected_metadata: Dict[int, Any] = dict(checkpoint_episodes)
    failed_ids: List[int] = []

    backoff_delays = story_retry_backoff if story_retry_backoff is not None else [5.0, 15.0, 30.0]

    processed_since_chk = 0
    for sid in pending_ids:
        ref = bundle_refs.get(sid)
        if not ref:
            failed_ids.append(sid)
            break

        success_this_story = False
        for attempt in range(1, story_retry_attempts + 1):
            res = fetch_story_json_by_id(
                sid,
                bundle_ref=ref,
                extract_metadata=True,
                write_story_json=write_story_json,
                timeout=timeout,
            )
            if res.status == "OK" and res.metadata is not None:
                collected_metadata[sid] = res.metadata
                success_this_story = True
                break

            if res.status == "NETWORK_ERROR" and attempt < story_retry_attempts:
                wait_s = backoff_delays[attempt - 1] if attempt - 1 < len(backoff_delays) else 30.0
                print(
                    f"[Retry] Story ID: {sid}, attempt {attempt}/{story_retry_attempts}, "
                    f"reason: {res.error_message}, wait {wait_s}s",
                    file=sys.stderr,
                    flush=True
                )
                if wait_s > 0:
                    time.sleep(wait_s)
            else:
                break

        if not success_this_story:
            failed_ids.append(sid)
            break

        processed_since_chk += 1
        if processed_since_chk >= progress_interval:
            save_bootstrap_checkpoint(chk_dir, target_ids, tv, collected_metadata, status="IN_PROGRESS")
            processed_since_chk = 0
            pct = len(collected_metadata) / len(target_ids) * 100
            pending_count = len(target_ids) - len(collected_metadata)
            print(
                f"📊 [進度 {len(collected_metadata)}/{len(target_ids)}] ({pct:.1f}%) | "
                f"待處理: {pending_count} | 最近話數: {sid} | 快照已更新: {chk_dir}",
                flush=True
            )

    if failed_ids or len(collected_metadata) != len(target_ids):
        # 失敗安全防禦：原子保存當前已成功進度，確保生產清單零寫入
        save_bootstrap_checkpoint(chk_dir, target_ids, tv, collected_metadata, status="IN_PROGRESS")
        return False, None, len(collected_metadata), failed_ids

    # 全數成功：原子寫入生產清單
    try:
        m_ver = batch_update_manifest_entries(
            collected_metadata,
            truth_version=tv,
            filepath=target_out,
            replace_existing=True,
        )
        save_bootstrap_checkpoint(chk_dir, target_ids, tv, collected_metadata, status="COMPLETE")
        return True, m_ver, len(collected_metadata), []
    except Exception:
        save_bootstrap_checkpoint(chk_dir, target_ids, tv, collected_metadata, status="IN_PROGRESS")
        return False, None, len(collected_metadata), target_ids


def run_cli():
    """CLI 入口，支援官方元數據側車清單之查詢與回補程序"""
    import argparse
    parser = argparse.ArgumentParser(
        description="PCRD Official Story Metadata Manifest 管理與回補工具"
    )
    parser.add_argument("--rebuild", action="store_true", help="重建/回補官方元數據側車清單 (需連線 CDN)")
    parser.add_argument("--resume", action="store_true", help="從上次中斷之快照 (checkpoint) 繼續執行")
    parser.add_argument("--sample", type=int, default=None, help="僅針對前 N 話樣本進行回補測試 (N 必須 > 0)")
    parser.add_argument("--truth-version", type=str, default=None, help="指定 8 位數字 TruthVersion (選填)")
    parser.add_argument("--output", type=str, default=None, help="輸出檔案路徑")
    parser.add_argument("--timeout", type=int, default=30, help="單話請求逾時秒數 (預設: 30)")
    parser.add_argument("--progress-interval", type=int, default=100, help="進度回報與快照更新間隔話數 (預設: 100)")

    args = parser.parse_args()

    if args.rebuild:
        if args.sample is not None and args.sample <= 0:
            parser.error("--sample 參數必須為大於 0 的正整數")

        print("=" * 60)
        print("⚡ [Bootstrap / Backfill] 官方元數據側車清單回補程序")
        print("=" * 60)

        chk_dir = PROJECT_ROOT / "scratch"
        state_file = chk_dir / CHECKPOINT_STATE_FILENAME
        data_file = chk_dir / CHECKPOINT_DATA_FILENAME
        chk_exists = state_file.exists() and data_file.exists()

        if args.resume:
            if not chk_exists:
                print(f"❌ [ERROR] 指定了 --resume 但未找到中斷快照檔案: {state_file}", file=sys.stderr)
                sys.exit(1)
        else:
            if chk_exists and not args.sample:
                print(
                    f"❌ [ERROR] 偵測到既有中斷快照檔案: {state_file}。\n"
                    f"   若要從上次中斷處續跑，請加上 --resume 參數；\n"
                    f"   若要全新重新抓取，請先手動移除或封存該快照目錄。",
                    file=sys.stderr
                )
                sys.exit(1)

        out_path = Path(args.output) if args.output else None
        if args.sample and not out_path:
            out_path = PROJECT_ROOT / "scratch" / "sample_official_metadata.json"
            print(f"  [安全防禦] Sample 模式未指定 --output，自動輸出至樣本檔案: {out_path}")
        elif not out_path:
            out_path = MANIFEST_PATH
            print(f"  目標檔案: {out_path}")

        print("  網路需求: 需要連線 So-net CDN (storydata2_assetmanifest 與 pool/AssetBundles)")
        print("  模式: Metadata-Only (絕不修改 dashboard/story/*.json)")
        if args.resume:
            print("  模式: 斷點續傳 (Resume from scratch checkpoint)")

        if not args.sample:
            print(f"⚠️  警告: 即將處理全量故事話數！")
            confirm = input("確定要執行全量 CDN 回補嗎？(輸入 YES 繼續): ")
            if confirm.strip() != "YES":
                print("操作已取消。")
                sys.exit(0)

        ok, m_ver, count, failed_ids = rebuild_official_metadata(
            truth_version=args.truth_version,
            output_path=out_path,
            sample_limit=args.sample,
            write_story_json=False,
            timeout=args.timeout,
            resume=args.resume,
            progress_interval=args.progress_interval,
            overwrite_checkpoint=False if not args.resume else True,
        )

        if ok:
            print(f"✅ 回補完成！成功處理 {count} 話，已原子寫入: {out_path} (metadata_version: {m_ver})")
            sys.exit(0)
        else:
            print(f"❌ 回補失敗！失敗話數: {failed_ids}，基於全有全無原子原則，Manifest 零寫入！", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == '__main__':
    run_cli()
