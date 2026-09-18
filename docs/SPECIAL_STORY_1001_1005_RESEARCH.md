# Special Story 1001–1005 Research Note

> Status: research note / provenance record  
> Scope: `dashboard/story/1001.json` through `dashboard/story/1005.json`  
> Branch at time of investigation: `data/npc-unit-id-migration-tia`  
> Last investigated: 2026-09-18

## Purpose

This document records the provenance investigation for the unusually short story IDs
`1001`–`1005`.

The important conclusion is that these files share a short-ID story namespace, but they
are **not one continuous five-part story**. They contain limited-time promotional /
collaboration stories that were exposed through special entry points rather than the
normal main/event/character/guild story structure.

This note exists so future cleanup, canonical rebuilds, avatar audits, or metadata work
do not incorrectly classify these files as garbage, malformed IDs, or ordinary event
stories.

---

## Repository observations

Current canonical corpus contains:

- `dashboard/story/1001.json`
- `dashboard/story/1002.json`
- `dashboard/story/1003.json`
- `dashboard/story/1004.json`
- `dashboard/story/1005.json`

No `1006.json` exists in the currently rebuilt corpus.

Language observed in the current corpus:

| Story ID | Corpus language | Notes |
| --- | --- | --- |
| `1001` | Traditional Chinese | Special game / April Fools story |
| `1002` | Traditional Chinese | Special game / April Fools story |
| `1003` | Traditional Chinese | Special game / April Fools story |
| `1004` | Japanese | 2024 Gindaco Highball Sakaba collaboration |
| `1005` | Japanese | 2024 Gindaco Highball Sakaba collaboration |

The current Story Map metadata does not normally attach these short IDs to the standard
main / character / guild / event story nodes. They should therefore be treated as
special-entry stories until explicit metadata is added.

---

## Story 1001

### Observed content

Main cast includes:

- Karyl / 凱留 — `106012`
- Kokkoro / 可可蘿 — `105913`
- Yui / 優衣 — `100213`
- Hiyori / 日和 — `100111`
- Pecorine / 貪吃佩可 — `105812`
- Rei / 怜 — `100311`

The Gourmet Guild and Twinkle Wish gather in the guildhouse. Yui brings a mysterious
board-game-like game. Everyone places their hands on its button, the device emits a
bright light, and the group is pulled into the game world.

### Provenance assessment

**High confidence:** this is the in-game limited story leading into the 2022 April Fools
title **Princess Connect! Grand Masters**.

Cygames' official 2022 announcement states that a limited story connecting Re:Dive to
Grand Masters was available from the My Page banner.

Official source:

- https://priconne-redive.jp/news/information/17175/

Note: the official page confirms the existence and purpose of the limited story, but does
not expose the internal `story_id=1001`. The ID-to-campaign mapping is established by
matching the repository story content to the officially described campaign.

---

## Story 1002

### Observed content

Main cast includes:

- Labyrista / 拉比林斯達 — `106812`
- Sheffy / 雪菲 — `106412`
- Yuni / 優妮 — `111011`
- Chloe / 克蘿依 — `110812`
- Chieru / 琪愛兒 — `110911`

The story explicitly refers back to the strange game world. Sheffy and the Friendship
Club visit Labyrista and jokingly pressure her about being implemented / usable as
leaders in the game. Labyrista eventually escapes.

### Provenance assessment

**High confidence:** this belongs to the 2023 return of **Princess Connect! Grand
Masters** and its limited in-game linking story / follow-up material.

Cygames' official 2023 announcement confirms that Re:Dive again exposed a limited story
leading into Grand Masters through a My Page banner.

Official source:

- https://priconne-redive.jp/news/information/22042/

As with `1001`, the official announcement does not publish the internal story ID; the
mapping is based on direct content correspondence.

---

## Story 1003

### Observed content

The first line explicitly identifies **April 1 / April Fools**.

Main cast includes:

- Kokkoro / 可可蘿 — `105911`
- Karyl / 凱留 — `106011`
- Pecorine / 貪吃佩可 — `105811`
- Monster — `1614`

The cast investigates a monster said to create a strange world resembling the kind of
game advertisements often seen during video streams. Karyl attacks the monster and is
then pulled into the strange world. Kokkoro asks the protagonist to help rescue her.

### Provenance assessment

**Very high confidence:** this is the Re:Dive in-game introduction to the 2024 April
Fools title **Karyl & Yabaival (キャル＆ヤバイバル)**.

The official announcement describes the game as rescuing Karyl after she is trapped in
a mysterious world created by a monster, and explicitly states that a limited in-game
story connecting to Karyl & Yabaival was available from the My Page banner.

Official source:

- https://priconne-redive.jp/news/information/26642/

### Short-ID implication

The monster's exact `unit_id=1614` is a legitimate occurrence-level ID in this special
story. This is another example showing that short numerical IDs must not be rejected
solely because they fall outside normal playable-character ranges.

---

## Stories 1004 and 1005

### Provenance

**Very high confidence:** these are the two-part collaboration stories for the 2024
**Princess Connect! Re:Dive × Gindaco Highball Sakaba
(銀だこハイボール酒場)** collaboration.

Official campaign dates:

- Collaboration: 2024-08-14 through 2024-09-10
- In-game collaboration story:
  - First half: 2024-08-14 05:00 through 2024-08-28 11:59
  - Second half: 2024-08-28 12:00 through 2024-09-11 04:59

Cygames explicitly states that the collaboration story was split into a first and second
half and could be replayed through a My Page banner during the campaign.

Official sources:

- https://priconne-redive.jp/news/information/27850/
- https://priconne-redive.jp/news/information/27834/
- https://dmg.priconne-redive.jp/news/detail.php?id=28247
- https://www.gindaco.com/news/detail/0740/

### Cast and collaboration artwork

The collaboration features newly drawn yukata artwork for:

- Yukari / 優花梨
- Yui / 優衣
- Misato / 美里

The official Gindaco announcement explicitly identifies the collaboration concept as
"summer festival" and these three characters as appearing in original newly drawn yukata
outfits.

### Story 1004

The story opens in Oedo town during a summer festival. Yui, Yukari, and Misato meet in
yukata, and Yukari takes the role of "summer festival meister" and introduces the food
stalls.

Observed exact avatar IDs:

- Yukari — `51712`
- Yui — `51812`
- Misato — `51912`

### Story 1005

The group visits the Silver Octopus / Gindaco-themed stall and eats and drinks
collaboration menu items.

Names appearing in the story directly match official collaboration products, including:

- `夏の麦しゅわ ユカリスペシャル`
- `森のヒーリングレモンサワー`
- `麦しゅわ進むユカリのおつまみたこ焼`
- `ユイの愛情たっぷり鉄板焼そば`
- `ミサト先生のごほうびおやつラスク`
- `オーエド横丁夏祭り完食ミッションセット`

The menu-name match is strong independent evidence linking `1004/1005` to the 2024
Gindaco collaboration.

---

## Important avatar-ID finding from Story 1005

Story `1005` proves that the same named character can switch exact short IDs within the
same scene and outfit.

Observed transitions:

| Character | Earlier ID | Later ID | Context |
| --- | ---: | ---: | --- |
| Yukari | `51712` | `51711` | switches when serving/eating takoyaki |
| Yui | `51812` | `51811` | switches when reacting shyly to the "Yui's love-filled yakisoba" name |
| Misato | `51912` | `51911` | switches later in the same food-stall scene |

There is no costume change or scene reset associated with these transitions.

Therefore the evidence strongly supports interpreting these IDs as **different
story-portrait / expression / pose variants of the same collaboration outfit**, rather
than different character identities.

### Consequence for avatar resolution

Do **not** resolve dialogue portraits using:

- speaker name → one fixed avatar
- short-ID → generic NPC
- numerical range heuristics
- a canonicalized playable-character ID

Instead, preserve the **exact official `unit_id` on each dialogue occurrence**.

Story `1005` should be retained as a regression fixture for exact-ID avatar rendering.

Recommended targeted assertions:

- Yukari: `51712 → 51711`
- Yui: `51812 → 51811`
- Misato: `51912 → 51911`

---

## Region / availability caution

The current corpus contains Traditional Chinese text for `1001`–`1003`, while
`1004`–`1005` remain Japanese.

The 2024 Gindaco Highball Sakaba campaign is documented by the Japanese official site and
Japanese physical-store campaign materials. During this investigation, no evidence was
identified that `1004/1005` were exposed through the normal Taiwan story UI.

Do not convert that observation into a parser rule.

The safe metadata distinction is:

- **asset/story exists in CDN/corpus**
- **known campaign provenance**
- **known or unknown region/client exposure**

In particular:

> CDN existence does not imply that the story was normally visible to players in every
> regional client.

---

## Classification guidance

For future Story Map metadata, a dedicated category such as
`special / limited / collaboration` is preferable to forcing these stories into normal
event-story numbering.

Possible metadata fields:

```json
{
  "story_id": 1004,
  "category": "special",
  "availability_type": "limited_banner",
  "campaign": "Princess Connect! Re:Dive × Gindaco Highball Sakaba",
  "region_origin": "JP",
  "language_in_corpus": "ja",
  "release_date": "2024-08-14",
  "notes": "Collaboration story, first half"
}
```

This is a documentation suggestion only. Do not alter production metadata solely from
this note without a separate design review.

---

## Engineering takeaways

1. Short story IDs are not automatically malformed.
2. Short `unit_id` values are not automatically NPC placeholders.
3. Special / limited stories may sit outside normal Story Map navigation metadata.
4. Language differences can reveal regional or campaign-specific provenance.
5. Exact per-occurrence `unit_id` is the authoritative avatar key.
6. Historical or limited CDN content should be preserved first and classified second;
   do not delete it merely because it is not exposed by the current Taiwan UI.
7. Future short-ID audits should investigate provenance before applying range-based
   cleanup rules.

---

## Follow-up opportunities

- Build a complete inventory of all unusually short `story_id` values.
- Build a provenance table for all 4–5 digit `unit_id` values.
- Identify other April Fools / collaboration / limited-banner stories.
- Add explicit special-story metadata to Story Map after a separate design review.
- Preserve `1005` as an avatar exact-ID regression fixture.
