# PCRD CDN update history

## 2026-08-10 — So-net CDN 00600011

- Recovered the stable website release and deployed chapter 16 stories `2216004`, `2216005`, `2216006`, and the extra story `2216101`.
- Fixed scenario-event parsing: exported story JSON now retains background changes, movie transitions, and `still_*` CG references instead of retaining dialogue only. Rebuilt chapter 16 stories `2216001`–`2216006` and `2216101`; `221600601.webp` is available as the official static preview for chapter 16 episode 6.
- Confirmed official CDN assets for `139001` (Kyouka Gothic) and `139101` (Karyl Haten Tensei), including icons, cards, and four available character-story episodes each.
- After the Kyouka Gothic banner opened, updated `139001` from the Taiwan plaintext database with its official position, profile, and combat skill descriptions.
- Added Miroku's NPC avatar from `storydata_icon_unit_192611.unity3d`.
- Reparsed all seven available chapter 16 story bundles for still references. Each has background references but no story CG command or still ID in the current Taiwan CDN manifest.
- Confirmed `2216101` is the chapter 16 extra story. It is displayed as `第3部 第16章 幕間`, while its official story title is `新人偶像小志那`.
- Downloaded and indexed the referenced chapter 16 backgrounds for use as story thumbnails.
- The additional four preallocated character-story IDs per costume unit are not yet present in the Taiwan story manifest.
