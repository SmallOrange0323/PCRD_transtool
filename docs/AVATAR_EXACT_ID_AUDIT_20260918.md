# Avatar Exact-ID Audit — 2026-09-18

> **Status:** Audit only / no production changes  
> **Source branch:** `data/npc-unit-id-migration-tia`  
> **Source commit inspected:** `a70d0ecfaa9ce7f4345eee97c37479e71b7d4456`  
> **Deployed asset branch inspected:** `gh-pages` @ `f794a78c8b4f31971642e6070bf40534ed2bedb2`  
> **Scope:** canonical Story JSON → avatar registry → deployed `icon/unit/` assets → frontend exact-ID behavior

## 1. Executive summary

The deployment asset layer is healthier than the previous short-ID audits suggested.

- Canonical numeric Story JSON files: **9,124**
- Actual dialogue registry entries: **947**
- Active dialogue registry entries: **944**
- Placeholder-only dialogue entries: **3**
- Deployed `gh-pages/icon/unit/` images: **1,625**
- Active dialogue registry assets missing from gh-pages: **0**
- Active dialogue registry assets with deployed size mismatch: **0**

However, the current validation gate **does not actually prove that every positive explicit Story `unit_id` is represented in the registry**.

The short-ID validation logic is circular:

1. It first defines valid short IDs from short IDs that are **already in `avatar_assets.json`**.
2. It then scans Story JSON and only includes a short Story ID if it was already in that registry-derived set.
3. Therefore, a legitimate short Story ID that is absent from the registry is silently excluded from the required-ID set and can never trigger the "missing from manifest" failure.

This audit confirms that this is not hypothetical. Current canonical stories contain official short IDs that are absent from the dialogue registry even though the corresponding PNGs already exist on gh-pages.

**Conclusion:** the current system has strong registry→asset integrity, but the Story→registry completeness claim is not valid for unregistered short IDs.

---

## 2. Canonical corpus

The inspected branch contains:

- **9,124** numeric files matching `dashboard/story/<story_id>.json`.

The canonical rebuild has already removed the historical `unit_id=1` placeholder problem. The focus of this audit is therefore no longer "repair identity by speaker name", but preservation of each explicit official occurrence-level `unit_id`.

### Required semantic contract

For a dialogue row containing a positive explicit `unit_id=X`:

```text
Story occurrence unit_id = X
        ↓
avatar_assets.json contains exact X
        ↓
exact X resolves to its declared asset (or explicit placeholder_only)
        ↓
deployed icon exists
        ↓
frontend does not substitute another identity
```

Numerical range alone must not decide whether X is legitimate.

---

## 3. Avatar registry: metadata drift found

`dashboard/data/avatar_assets.json` currently declares the following metadata:

| Field | Metadata value |
| --- | ---: |
| total_assets | 956 |
| dialogue_assets_count | 926 |
| active_dialogue_count | 923 |
| placeholder_only_count | 3 |
| ui_assets_count | 30 |
| total_active_bytes | 19,193,258 |

But parsing the actual `assets[]` array gives:

| Field | Actual value |
| --- | ---: |
| total assets | **977** |
| dialogue assets | **947** |
| active dialogue assets | **944** |
| placeholder-only dialogue assets | **3** |
| UI assets | **30** |
| all active assets | **974** |
| actual active bytes | **19,594,602** |
| actual active MiB | **18.6869 MiB** |

The count drift is exactly **+21 assets**, matching the set added during the recent canonical rebuild.

### Finding A — stale summary metadata

**Severity:** LOW (reporting / observability)

The registry body has the new entries, but its summary metadata was not recomputed.

This does not by itself break avatar rendering, but it makes audit totals misleading and should be corrected when the registry is next regenerated.

---

## 4. Registry → gh-pages deployment audit

The deployed `gh-pages` tree contains **1,625** `icon/unit/*.png|webp` files.

Every one of the **944 active dialogue registry entries** was checked by declared filename against the deployed tree.

Results:

| Check | Result |
| --- | ---: |
| Active dialogue assets checked | **944** |
| Missing on gh-pages | **0** |
| Size mismatch vs registry | **0** |

### Finding B — deployed active registry assets are complete

**Severity:** PASS

For assets that are already registered as active dialogue assets, deployment coverage is currently complete at the filename and byte-size level.

This means the main short-ID problem is **not** "the images were never deployed". It is primarily a registry / resolution-contract problem.

---

## 5. Intentional placeholder-only IDs

Three dialogue IDs are explicitly registered as `placeholder_only`:

| unit_id | provenance |
| ---: | --- |
| `105921` | `canonical_story_verified_placeholder` |
| `106913` | `canonical_story_verified_placeholder` |
| `190813` | `canonical_story_verified_placeholder` |

These are explicit states and should not be conflated with accidental missing assets.

---

## 6. Short-ID validator blind spot

Current `pipeline.validate.validate_avatar_manifest_and_assets()` contains this logic:

```python
canonical_short_uids = {
    a.get("unit_id") for a in assets
    if a.get("unit_id") is not None
    and a.get("unit_id") < 100000
    and a.get("usage") == "dialogue"
    and a.get("status") == "active"
    and a.get("asset_key")
    and a.get("filename")
}

...

n = int(uid)
if n >= 100000 or n in canonical_short_uids:
    canonical_dialogue_uids.add(n)
```

This is circular for short IDs.

An unregistered short ID from a canonical Story can never enter `canonical_short_uids`, so it is excluded from `canonical_dialogue_uids`, and therefore cannot appear in:

```python
missing_dialogue_in_manifest = canonical_dialogue_uids - manifest_uids
```

### Finding C — current PASS does not cover all explicit short IDs

**Severity:** HIGH

A successful Avatar Manifest validation currently means:

> all >=100000 Story IDs plus already-registered short IDs are covered

It does **not** mean:

> all positive explicit Story IDs are covered.

The latter is the contract required by the current exact-ID architecture.

---

## 7. Proven current canonical short-ID misses

The following IDs are directly confirmed in current canonical stories and are absent from the dialogue registry:

| unit_id | Story evidence | speaker | Registry | gh-pages asset |
| ---: | --- | --- | --- | --- |
| `1614` | Story `1003` | 魔物 | **missing** | `001614.png` ✅ |
| `51712` | Story `1004`, `1005` | ユカリ | **missing** | `051712.png` ✅ |
| `51711` | Story `1005` | ユカリ | **missing** | `051711.png` ✅ |
| `51812` | Story `1004`, `1005` | ユイ | **missing** | `051812.png` ✅ |
| `51811` | Story `1005` | ユイ | **missing** | `051811.png` ✅ |
| `51912` | Story `1004`, `1005` | ミサト | **missing** | `051912.png` ✅ |
| `51911` | Story `1005` | ミサト | **missing** | `051911.png` ✅ |

These are **not missing binary assets**. They are missing registry declarations.

### Known provenance

- `1003`: 2024 April Fools special story / Karyl & Yabaival entry story.
- `1004`–`1005`: 2024 Japanese Princess Connect! Re:Dive × Gindaco Highball Sakaba collaboration story.

The latter uses special collaboration yukata portraits for Yukari, Yui, and Misato.

---

## 8. 517xx / 518xx / 519xx asset identity correction

The Story IDs do switch within Story `1005`:

- Yukari: `51712 → 51711`
- Yui: `51812 → 51811`
- Misato: `51912 → 51911`

However, deployed binary inspection shows:

| Pair | gh-pages blob result |
| --- | --- |
| `051711.png` / `051712.png` | **same Git blob SHA**, same 19,898 bytes |
| `051811.png` / `051812.png` | **same Git blob SHA**, same 18,580 bytes |
| `051911.png` / `051912.png` | **same Git blob SHA**, same 18,816 bytes |

### Finding D — distinct official IDs can legitimately share identical portrait bytes

The earlier working hypothesis that `...11` / `...12` necessarily represented visibly different expressions is **not supported by the deployed assets**.

The correct statement is:

> The Story contains distinct official exact IDs, but each 11/12 pair currently resolves to byte-identical artwork.

This is another reason not to canonicalize identity based on visual equality. Distinct IDs must remain distinct even when their current asset bytes are aliases.

---

## 9. Frontend impact of an unregistered short ID

`dashboard/dialogue-view.js` correctly treats **any positive integer `unit_id`** as explicit:

```javascript
const hasExplicitUnitId = Number.isInteger(numUnitId) && numUnitId > 0;

if (hasExplicitUnitId) {
    avatarContent = window.AvatarService.getAvatarHtmlByUnitId(
        numUnitId,
        realName,
        speakerAvatars
    );
}
```

But `AvatarService.getAvatarHtmlByUnitId()` currently handles an unregistered short ID differently from an unregistered >=100000 ID:

```javascript
if (resolved && resolved.status === 'active') {
    // exact registered asset
}

if (numId >= 100000) {
    return this.getFallbackHtml(cleanName); // fail closed
}

// numId < 100000 and not registered:
// falls through to inferred/name-only path
```

Therefore an explicit unregistered short ID can be replaced by a name-inferred normal character portrait.

For the Gindaco stories, the current inference table includes:

- `優花梨 → 103432`
- `優衣 → 100232`
- `美里 → 101533`

So a dialogue occurrence whose official ID is `51712`, `51812`, etc. can lose its collaboration portrait identity and display an inferred regular character portrait instead.

### Finding E — explicit short-ID identity can be overwritten by name inference

**Severity:** HIGH

This violates the project's own "EXPLICIT ALWAYS WINS" contract.

For an explicit positive `unit_id`, absence from the registry must never authorize replacement with a different inferred ID.

---

## 10. Only one registered short dialogue ID

The current dialogue registry has only one `unit_id < 100000`:

| unit_id | asset_key | filename | status |
| ---: | --- | --- | --- |
| `6112` | `006112` | `006112.png` | active |

This single pilot entry is why the current short-ID gate can appear to work while still ignoring other unregistered short IDs.

The presence of `6112` proves the registry schema and resolver already support padded short-ID asset keys. The missing requirement is to derive the short-ID set from Story truth rather than from the registry itself.

---

## 11. Audit status matrix

| Layer | Status | Notes |
| --- | --- | --- |
| Canonical Story corpus presence | **PASS** | 9,124 numeric Story JSON files |
| Registry schema/body | **PASS with metadata drift** | 977 actual assets; summary counters stale by 21 |
| Active registry → gh-pages file existence | **PASS** | 944 / 944 |
| Active registry → gh-pages size parity | **PASS** | 944 / 944 |
| Placeholder-only declaration | **PASS** | 3 explicit IDs |
| >=100000 Story → registry gate | **PASS by current validator** | existing gate covers this class |
| Already-registered short Story IDs → registry gate | **PASS** | circularly defined |
| **All positive short Story IDs → registry gate** | **FAIL / not actually audited** | validator excludes unknown short IDs |
| Explicit short ID → exact frontend identity | **FAIL for missing registry IDs** | falls back to name inference |
| 1004/1005 special collaboration IDs | **FAIL registry coverage** | PNGs exist but exact IDs are unregistered |

---

## 12. What this report does NOT claim

This report does **not** claim that the seven proven short-ID misses above are the complete corpus-wide missing-short-ID set.

Why:

- the existing validator excludes unknown short IDs by design;
- the current repository does not contain a committed post-rebuild machine-readable list of all 1,386 distinct Story unit IDs;
- therefore a truly complete Story→registry set difference must be generated by scanning all canonical dialogue rows with the corrected rule:
  - **every positive integer explicit `unit_id` is eligible**.

This limitation is itself the primary audit finding.

No historical 9,033-story identity report should be substituted as the final answer for the current 9,124-story corpus.

---

## 13. Recommended next audit step (not executed in this commit)

Do not repair individual IDs manually first.

Instead, change the audit/gate definition to compute:

```text
required_exact_ids =
    all positive integer unit_id values
    appearing on canonical dialogue rows
```

Then classify every distinct ID as:

- `PASS_EXACT_ACTIVE`
- `PASS_EXPLICIT_PLACEHOLDER`
- `MISSING_REGISTRY`
- `MISSING_DEPLOYED_ASSET`
- `ASSET_SIZE_OR_HASH_MISMATCH`

The audit output should retain at least:

```text
unit_id
occurrence_count
story_count
sample story_ids
sample speakers
registry_status
declared filename
deployed existence
resolution status
```

No speaker-name mapping or numerical range heuristic should participate in PASS/FAIL.

After the corrected full scan is clean, `pipeline.validate` can be tightened to enforce the same invariant permanently.

---

## 14. Safety boundary

This audit commit intentionally performs **no remediation**:

- no Story JSON changes
- no `avatar_assets.json` changes
- no `avatar-service.js` changes
- no validator changes
- no `dist_story_map` changes
- no deployment
- no merge to `main`

It is a baseline evidence document for the next exact-ID remediation phase.
