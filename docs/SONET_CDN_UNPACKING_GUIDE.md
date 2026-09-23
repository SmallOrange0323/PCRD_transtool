# So-net CDN Unpacking Guide for AI Agents

> Audience: AI coding agents working inside this repository.
>
> Goal: safely inspect and unpack Princess Connect! Re:Dive Taiwan (So-net) CDN assets using the repository's existing tools and conventions.
>
> Default rule: **research/unpacking tasks are read-only with respect to production state unless the user explicitly asks for an update.**

---

## 1. Safety contract

For an ordinary unpacking/research request, an AI agent MUST:

- prefer an **explicit TruthVersion** supplied by the user or already established by verified evidence;
- write experiments and temporary outputs under `scratch/` or another explicitly requested non-production path;
- avoid overwriting `dashboard/redive_tw.db`;
- avoid mutating `dashboard/versions/version_history.json`;
- avoid running `update_story_map.py` unless the user explicitly asked to update the site;
- never deploy;
- never touch `dist_story_map/.git`;
- never run broad cleanup commands such as `git clean`, `git reset --hard`, or `git restore .`;
- distinguish **CDN availability** from **active/live game version**;
- record provenance: TruthVersion, manifest name, bundle name, pool hash, and relevant integrity metadata.

For a pure unpacking task, do not commit, push, or deploy unless the user explicitly requests it.

---

## 2. So-net CDN model

The basic resource chain is:

```text
TruthVersion
  -> Resources/{TruthVersion}/Jpn/AssetBundles/{Platform}/manifest/{manifest_name}
  -> manifest entry
  -> bundle name + bundle identity fields + pool hash
  -> /dl/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}
  -> Unity AssetBundle
  -> UnityPy / project parser
  -> extracted object or normalized output
```

Primary CDN root used by this repository:

```text
https://img-pc.so-net.tw/dl
```

Typical Android manifest URL:

```text
https://img-pc.so-net.tw/dl/Resources/{TruthVersion}/Jpn/AssetBundles/Android/manifest/{manifest_name}
```

Typical pool URL:

```text
https://img-pc.so-net.tw/dl/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}
```

### Important terminology

Do not conflate these:

```text
CDN_AVAILABLE_VERSION
!=
ACTIVE_TRUTH_VERSION
```

If a manifest exists for a TruthVersion, that proves the resources are present on So-net CDN. It does **not** by itself prove that the game server has activated that version.

Likewise:

- `pool_hash` is the CDN pool identifier used to construct the bundle URL;
- manifest MD5 and pool hash are separate fields;
- SQLite SHA-256 is a separate content hash.

Do not label one as another.

---

## 3. Relevant repository tools

### 3.1 Version existence / CDN candidate probing

Use:

```text
tools/diagnostics/probe_sonet_versions.py
```

Example:

```powershell
python tools/diagnostics/probe_sonet_versions.py --versions 00610007 00610008 00610009
```

The tool classifies candidates such as:

- `EXISTS`
- `NOT_FOUND`
- `INVALID_MANIFEST`
- `NETWORK_ERROR`

It validates `masterdata2_assetmanifest` and extracts the `masterdata_master.unity3d` entry.

**Do not describe the highest observed candidate as globally latest unless the search horizon and active-version evidence justify that claim.**

---

### 3.2 Story JSON

Preferred public entry point:

```powershell
python -m pipeline.fetch fetch-story --story-id <STORY_ID>
```

Example:

```powershell
python -m pipeline.fetch fetch-story --story-id 2001001
```

The canonical primitive is implemented in `tools/pcrd_fetch.py`:

```text
fetch_story_json_by_id(...)
```

Conceptual flow:

```text
story_id
  -> storydata2_assetmanifest
  -> matching storydata_{story_id}.unity3d bundle
  -> pool hash
  -> So-net bundle
  -> project story parser
  -> dashboard/story/{story_id}.json
```

The CLI writes into the production-style story directory, so if the task is only exploratory and must not modify repository data, call the underlying primitive with an appropriate non-writing mode or create a scratch-only diagnostic wrapper instead of invoking the mutating CLI blindly.

---

### 3.3 Story thumbnails

Use:

```text
tools/fetch_story_thumbnails.py
```

Example:

```powershell
python tools/fetch_story_thumbnails.py --story-id 2001001 --truth-version 00610008 --update-manifest
```

Relevant manifest:

```text
icon2_assetmanifest
```

Expected bundle family:

```text
a/icon_thumb_story_{story_id}.unity3d
```

Extraction flow:

```text
icon2_assetmanifest
  -> story thumbnail bundle
  -> pool hash
  -> UnityPy
  -> first matching Texture2D
  -> WebP
```

For AI research tasks, prefer redirecting output to scratch or adapting the helper instead of overwriting tracked assets unless explicitly requested.

---

### 3.4 Event top thumbnails

Use:

```text
tools/fetch_event_top_thumbnails.py
```

Example with explicit TruthVersion:

```powershell
python tools/fetch_event_top_thumbnails.py --truth-version 00610008
```

Relevant bundle family:

```text
a/icon_thumb_event_story_top_*.unity3d
```

This tool is a useful reference implementation because it already handles:

- explicit or resolved TruthVersion;
- manifest parsing;
- pool hash lookup;
- bundle size / MD5 identity checks;
- UnityPy Texture2D extraction;
- deterministic local verification.

For pure research, inspect or reuse its primitives rather than necessarily running the full production-output pipeline.

---

## 4. Raw Master DB extraction

### 4.1 Recommended public-main primitives

For raw Master DB research, prefer functions in:

```text
pipeline/extract_chapter_titles.py
```

Relevant functions:

```python
discover_bundle_from_cdn_manifest(...)
download_bundle_by_pool_hash(...)
extract_master_sqlite_from_bundle(...)
```

These allow an AI agent to retrieve a specific TruthVersion's Master DB without using the legacy direct-write script.

Example scratch-only extractor:

```python
from pathlib import Path

from pipeline.extract_chapter_titles import (
    discover_bundle_from_cdn_manifest,
    download_bundle_by_pool_hash,
    extract_master_sqlite_from_bundle,
)

truth_version = "00610008"

bundle_info = discover_bundle_from_cdn_manifest(
    truth_version=truth_version,
    manifest_name="masterdata2_assetmanifest",
    target_bundle="a/masterdata_master.unity3d",
)

pool_hash = bundle_info["bundle_pool_hash"]

bundle_bytes = download_bundle_by_pool_hash(pool_hash)
sqlite_bytes = extract_master_sqlite_from_bundle(bundle_bytes)

out = Path("scratch") / f"master_raw_{truth_version}.db"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(sqlite_bytes)

print("truth_version:", truth_version)
print("bundle:", bundle_info["bundle_path"])
print("pool_hash:", pool_hash)
print("output:", out)
print("sqlite_size:", len(sqlite_bytes))
```

Run:

```powershell
python scratch/unpack_master_db.py
```

### 4.2 How raw SQLite is identified

The extractor searches `TextAsset` raw bytes for:

```python
b"SQLite format 3\x00"
```

When the magic header is found, the SQLite payload begins at that offset.

For binary `TextAsset` data, prefer:

```python
obj.get_raw_data()
```

Do not pass binary DB payloads through text decoding.

### 4.3 Raw DB schema obfuscation

A successfully extracted official Master DB may still have obfuscated table and column names.

Example physical table form:

```text
v1_<hex token>
```

Therefore:

```text
AssetBundle successfully unpacked
!=
database schema normalized to plaintext names
```

Do not declare DB extraction failed merely because `story_detail`, `unit_data`, etc. are not visible as plaintext table names.

Do not guess mappings from row count or column count alone.

---

## 5. Legacy DB scripts: read for reference, do not use as the default

### `tools/fetch_db_from_sonet.py`

This is an older experimental script and is **not** the preferred generic unpacking entry point.

Reasons:

- it contains historical TruthVersion assumptions;
- it writes directly to `dashboard/redive_tw.db`;
- it does not provide the same safety boundaries expected for a scratch-only unpacking task.

### `tools/monitor_sonet_update.py`

Useful as historical reference for:

- manifest lookup;
- pool URL construction;
- UnityPy Master DB extraction.

But its old version-scanning logic is not authoritative for current research. In particular, older scanners may stop at a 404 and should not be treated as proof that no later sparse version exists.

For current candidate probing, prefer:

```text
tools/diagnostics/probe_sonet_versions.py
```

---

## 6. Inspecting an arbitrary AssetBundle

If a manifest entry and pool hash are known, a minimal inspection flow is:

```python
import urllib.request
import UnityPy

pool_hash = "PUT_POOL_HASH_HERE"
url = (
    "https://img-pc.so-net.tw/dl/pool/AssetBundles/"
    f"{pool_hash[:2]}/{pool_hash}"
)

req = urllib.request.Request(
    url,
    headers={
        "User-Agent": (
            "Dalvik/2.1.0 "
            "(Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)"
        )
    },
)

with urllib.request.urlopen(req, timeout=30) as response:
    bundle_bytes = response.read()

env = UnityPy.load(bundle_bytes)

for obj in env.objects:
    print(obj.path_id, obj.type.name)
```

Common Unity object types include:

- `Texture2D`
- `TextAsset`
- `Sprite`
- `MonoBehaviour`

### Texture2D

```python
for obj in env.objects:
    if obj.type.name == "Texture2D":
        texture = obj.read()
        image = texture.image
        image.save("scratch/texture.png")
```

### TextAsset

For text-like content:

```python
for obj in env.objects:
    if obj.type.name == "TextAsset":
        raw = obj.get_raw_data()
        print("bytes:", len(raw))
```

Whether the `TextAsset` is plain text, encoded commands, SQLite, or another binary format depends on the bundle family. Inspect before assuming.

---

## 7. Manifest-first workflow for unknown assets

When asked to locate or unpack a new asset type, AI agents should use this order:

```text
1. Establish an explicit TruthVersion.
2. Identify the likely manifest family.
3. Download only the manifest first.
4. Search bundle names for semantic clues.
5. Record bundle name, MD5, pool hash, and size fields.
6. Download one representative bundle.
7. Inspect Unity object types.
8. Extract to scratch/.
9. Verify the output format.
10. Only then build a reusable extractor.
```

Do **not** start by brute-forcing pool hashes.

Do **not** bulk-download large asset families before confirming the bundle format.

---

## 8. Common manifest families used by this project

Known examples:

```text
masterdata2_assetmanifest  -> Master DB
storydata2_assetmanifest   -> story bundles
icon2_assetmanifest        -> story/event thumbnails and other icon assets
unit2_assetmanifest        -> unit-related image assets
```

A generic manifest URL is:

```text
https://img-pc.so-net.tw/dl/Resources/{TruthVersion}/Jpn/AssetBundles/Android/manifest/{ManifestName}
```

Treat field semantics as manifest-family evidence, not as an undocumented universal protocol guarantee. Validate actual entries before building hard assumptions.

---

## 9. Integrity and provenance expectations

For a serious extractor, capture as much of the following as the manifest/tooling supports:

```text
truth_version
platform
manifest_name
manifest_url
manifest_sha256
bundle_name
bundle_md5
pool_hash
bundle_size
bundle_sha256
extracted_object_type
output_sha256
output_path
```

When the manifest supplies expected size or MD5 and the field meaning has been verified for that manifest family, validate them before parsing the bundle.

A network error must never become a successful or confirmed result.

---

## 10. Recommended AI-agent response format

After an unpacking task, report concise evidence:

```text
TruthVersion:
Manifest:
Bundle name:
Pool hash:
Bundle identity/integrity:
Unity object types:
Extracted output:
Output SHA-256 (if useful):
Production files modified: yes/no
Open uncertainties:
```

If the active TruthVersion is not independently proven, say:

```text
This TruthVersion is verified as CDN-available, not necessarily active.
```

---

## 11. Examples for first-time validation

### Probe a version

```powershell
python tools/diagnostics/probe_sonet_versions.py --versions 00610008
```

### Fetch one story

```powershell
python -m pipeline.fetch fetch-story --story-id 2001001
```

### Fetch one story thumbnail

```powershell
python tools/fetch_story_thumbnails.py --story-id 2001001 --truth-version 00610008 --update-manifest
```

### Inspect Master DB to scratch

Create the scratch wrapper from section 4 and run:

```powershell
python scratch/unpack_master_db.py
```

These demonstrate the core chain:

```text
Manifest
  -> Pool Hash
  -> AssetBundle
  -> UnityPy / project parser
  -> extracted artifact
```

---

## 12. What not to do

For a normal unpacking request, AI agents must not:

- deploy the website;
- update GitHub Pages;
- modify `dist_story_map/.git`;
- overwrite `dashboard/redive_tw.db` merely to inspect a DB;
- advance `version_history.json`;
- infer ACTIVE_TRUTH_VERSION from one HTTP 200 manifest;
- treat the first 404 after a version as proof that no later version exists;
- confuse bundle MD5, pool hash, bundle SHA-256, and SQLite SHA-256;
- assume every `TextAsset` is text;
- assume a raw obfuscated SQLite is already normalized;
- use row-count similarity as authoritative schema deobfuscation;
- bulk download an entire CDN family before a representative bundle has been inspected.

---

## 13. Repository evolution note

This guide describes tools available on the tracked repository branch at the time of writing.

If newer canonical So-net Master DB acquisition / normalization modules are added later, prefer those newer fail-closed modules over historical direct-write scripts.

When updating this guide, preserve these invariants:

1. explicit snapshot provenance;
2. manifest-first lookup;
3. pool-hash-based bundle retrieval;
4. integrity checks where supported;
5. scratch-first experimentation;
6. fail-closed behavior for unknown formats or schema;
7. no production mutation during a pure unpacking task.
