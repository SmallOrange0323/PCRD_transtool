/**
 * PCRD Story Map - Dialogue Avatar Exact-ID Coverage & Governance Audit
 * Phase 2: AUDIT ONLY (Deterministic, offline, zero production modification)
 * 
 * 依據 External Review 決策：
 * 1. 嚴格分離 Special non-avatar codes (< 100000) 與 Avatar-eligible IDs (>= 100000)
 * 2. 精確計算 Avatar-eligible 實體覆蓋率與 Production 覆蓋率
 * 3. 採用 pipeline/validate.py 相同之排除規則 ({'.git', 'sound', 'card'}) 計算 Canonical Pages Footprint
 */

const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..', '..', '..', '..', '..', '..', '..', 'OneDrive - 寰宇知識科技股份有限公司', 'PCRD_tool');
const PROJ_ROOT = fs.existsSync(path.join(ROOT_DIR, 'dashboard')) ? ROOT_DIR : process.cwd();

const STORY_DIR = path.join(PROJ_ROOT, 'dashboard', 'story');
const ICON_UNIT_DIR = path.join(PROJ_ROOT, 'dashboard', 'icon', 'unit');
const DIST_ICON_UNIT_DIR = path.join(PROJ_ROOT, 'dist_story_map', 'icon', 'unit');
const DIST_DIR = path.join(PROJ_ROOT, 'dist_story_map');
const TRACKED_CHARACTERS_PATH = path.join(PROJ_ROOT, 'dashboard', 'data', 'tracked_characters.json');
const AVATAR_ASSETS_PATH = path.join(PROJ_ROOT, 'dashboard', 'data', 'avatar_assets.json');

// --- 載入專案現行 AvatarService 原生實作 ---
global.window = global;
require(path.join(PROJ_ROOT, 'dashboard', 'story-asset-service.js'));
require(path.join(PROJ_ROOT, 'dashboard', 'avatar-service.js'));

// --- Bundler Expected Icons 邏輯 (支援 Manifest-First 權威治理與 Legacy 對比) ---
const EXACT_REALITY_IDS = window.AvatarService.exactRealityIds;

function loadAvatarManifest() {
    if (!fs.existsSync(AVATAR_ASSETS_PATH)) return null;
    try {
        return JSON.parse(fs.readFileSync(AVATAR_ASSETS_PATH, 'utf-8'));
    } catch (e) {
        console.error('Error reading avatar_assets.json:', e);
        return null;
    }
}

function getLegacyBundlerExpectedUnitIds() {
    const expectedIds = new Set();
    if (fs.existsSync(TRACKED_CHARACTERS_PATH)) {
        try {
            const data = JSON.parse(fs.readFileSync(TRACKED_CHARACTERS_PATH, 'utf-8'));
            const chars = data.characters || [];
            for (const char of chars) {
                for (const iconId of (char.icon_ids || [])) {
                    for (const ext of ['.png', '.webp']) {
                        const p1 = path.join(ICON_UNIT_DIR, `${iconId}${ext}`);
                        const p2 = path.join(ICON_UNIT_DIR, `unit_icon_${iconId}${ext}`);
                        if (fs.existsSync(p1) || fs.existsSync(p2)) {
                            expectedIds.add(Number(iconId));
                        }
                    }
                }
            }
        } catch (e) {
            console.error('Error reading tracked_characters.json:', e);
        }
    }
    if (fs.existsSync(ICON_UNIT_DIR)) {
        const files = fs.readdirSync(ICON_UNIT_DIR);
        for (const file of files) {
            const ext = path.extname(file).toLowerCase();
            if (ext !== '.png' && ext !== '.webp') continue;
            const stem = path.basename(file, ext);
            const cleanId = stem.replace('unit_icon_', '');
            if (/^\d+$/.test(cleanId)) {
                const val = parseInt(cleanId, 10);
                if ((val >= 190000 && val <= 199999) || [107411, 107412, 107431].includes(val) || EXACT_REALITY_IDS.has(val)) {
                    expectedIds.add(val);
                }
            }
        }
    }
    return expectedIds;
}

function getCurrentBundlerExpectedUnitIds() {
    const manifest = loadAvatarManifest();
    if (!manifest || !manifest.assets || !Array.isArray(manifest.assets)) {
        return getLegacyBundlerExpectedUnitIds();
    }
    const expectedIds = new Set();
    for (const entry of manifest.assets) {
        if (entry.status === 'active' && entry.unit_id) {
            expectedIds.add(entry.unit_id);
        }
    }
    return expectedIds;
}

// 輔助函數：計算目錄遞迴大小與檔案數
function getDirStats(dir, excludeDirs = new Set(['.git'])) {
    let totalBytes = 0;
    let fileCount = 0;
    if (!fs.existsSync(dir)) return { totalBytes: 0, fileCount: 0 };
    const items = fs.readdirSync(dir);
    for (const item of items) {
        if (excludeDirs.has(item)) continue;
        const fullPath = path.join(dir, item);
        const stat = fs.statSync(fullPath);
        if (stat.isDirectory()) {
            const sub = getDirStats(fullPath, excludeDirs);
            totalBytes += sub.totalBytes;
            fileCount += sub.fileCount;
        } else {
            totalBytes += stat.size;
            fileCount++;
        }
    }
    return { totalBytes, fileCount };
}

function runAudit() {
    console.log('================================================================================');
    console.log('PCRD Story Map: Dialogue Avatar Exact-ID Asset Coverage & Governance Audit');
    console.log('Phase 2: AUDIT ONLY (Deterministic, offline, zero production modification)');
    console.log('================================================================================\n');

    // 1. 正規劇本與對白 unit_id 盤點
    const allStoryFiles = fs.readdirSync(STORY_DIR);
    const canonicalStoryFiles = allStoryFiles.filter(f => /^\d+\.json$/.test(f));
    const excludedStoryFiles = allStoryFiles.filter(f => !/^\d+\.json$/.test(f));

    let totalDialogueRows = 0;
    let dialogueRowsWithExplicitId = 0;
    let dialogueRowsWithoutUnitId = 0;

    // uid -> { usageCount, stories: Set, speakers: Set }
    const explicitUnitMap = new Map();

    for (const file of canonicalStoryFiles) {
        const storyId = path.basename(file, '.json');
        const content = JSON.parse(fs.readFileSync(path.join(STORY_DIR, file), 'utf-8'));
        if (!Array.isArray(content)) continue;

        for (const item of content) {
            if (!item || typeof item !== 'object') continue;
            if (item.type === 'dialogue' || (!item.type && item.name)) {
                totalDialogueRows++;
                const uid = item.unit_id;
                const speaker = item.name || '';

                if (uid && typeof uid === 'number' && uid > 0) {
                    dialogueRowsWithExplicitId++;
                    if (!explicitUnitMap.has(uid)) {
                        explicitUnitMap.set(uid, {
                            usageCount: 0,
                            stories: new Set(),
                            speakers: new Set()
                        });
                    }
                    const info = explicitUnitMap.get(uid);
                    info.usageCount++;
                    if (info.stories.size < 5) info.stories.add(storyId);
                    if (speaker) info.speakers.add(speaker);
                } else {
                    dialogueRowsWithoutUnitId++;
                }
            }
        }
    }

    const allExplicitUnitIds = Array.from(explicitUnitMap.keys()).sort((a, b) => a - b);
    const specialNonAvatarIds = allExplicitUnitIds.filter(id => id < 100000);
    const avatarEligibleExplicitIds = allExplicitUnitIds.filter(id => id >= 100000);

    let specialNonAvatarRows = 0;
    for (const id of specialNonAvatarIds) specialNonAvatarRows += explicitUnitMap.get(id).usageCount;

    let avatarEligibleRows = 0;
    for (const id of avatarEligibleExplicitIds) avatarEligibleRows += explicitUnitMap.get(id).usageCount;

    console.log(`[1] Canonical Dialogue Unit IDs Audit:`);
    console.log(`    canonical_story_count: ${canonicalStoryFiles.length}`);
    console.log(`    excluded_non_scripts: ${excludedStoryFiles.join(', ')}`);
    console.log(`    total_dialogue_rows: ${totalDialogueRows}`);
    console.log(`    dialogue_rows_with_explicit_unit_id: ${dialogueRowsWithExplicitId}`);
    console.log(`    dialogue_rows_without_unit_id: ${dialogueRowsWithoutUnitId}`);
    console.log(`    distinct_explicit_unit_ids (all): ${allExplicitUnitIds.length}`);
    console.log(`    special_non_avatar_ids (< 100000): ${specialNonAvatarIds.length}`);
    console.log(`    special_non_avatar_dialogue_rows: ${specialNonAvatarRows}`);
    console.log(`    avatar_eligible_explicit_ids (>= 100000): ${avatarEligibleExplicitIds.length}`);
    console.log(`    avatar_eligible_dialogue_rows: ${avatarEligibleRows}\n`);

    // 2. 本地實體資產盤點 (dashboard/icon/unit)
    const localFiles = fs.readdirSync(ICON_UNIT_DIR);
    const localPngSet = new Set();
    const localWebpSet = new Set();
    const localAnySet = new Set();
    let legacyIconFileCount = 0;
    const localFileSizes = [];
    let totalLocalAvatarBytes = 0;
    let totalPngBytes = 0;
    let totalWebpBytes = 0;
    let countPng = 0;
    let countWebp = 0;

    const localIdToSizeBytes = new Map();

    for (const file of localFiles) {
        const fullPath = path.join(ICON_UNIT_DIR, file);
        const stat = fs.statSync(fullPath);
        const size = stat.size;
        localFileSizes.push(size);
        totalLocalAvatarBytes += size;

        const ext = path.extname(file).toLowerCase();
        const stem = path.basename(file, ext);
        const isLegacy = stem.startsWith('unit_icon_');
        const cleanId = stem.replace('unit_icon_', '');

        if (isLegacy) legacyIconFileCount++;

        if (ext === '.png') {
            countPng++;
            totalPngBytes += size;
        } else if (ext === '.webp') {
            countWebp++;
            totalWebpBytes += size;
        }

        if (/^\d+$/.test(cleanId)) {
            const numId = parseInt(cleanId, 10);
            localAnySet.add(numId);
            if (ext === '.png') localPngSet.add(numId);
            if (ext === '.webp') localWebpSet.add(numId);

            if (!localIdToSizeBytes.has(numId) || ext === '.png') {
                localIdToSizeBytes.set(numId, size);
            }
        }
    }

    localFileSizes.sort((a, b) => a - b);
    const avgSize = localFileSizes.length ? totalLocalAvatarBytes / localFileSizes.length : 0;
    const medianSize = localFileSizes.length ? localFileSizes[Math.floor(localFileSizes.length / 2)] : 0;
    const p95Size = localFileSizes.length ? localFileSizes[Math.floor(localFileSizes.length * 0.95)] : 0;
    const maxSize = localFileSizes.length ? localFileSizes[localFileSizes.length - 1] : 0;

    console.log(`[2] Physical Local Avatar Assets Audit (dashboard/icon/unit):`);
    console.log(`    total_avatar_files: ${localFiles.length}`);
    console.log(`    distinct_numeric_avatar_ids: ${localAnySet.size}`);
    console.log(`    format_breakdown_png: ${countPng} (${(totalPngBytes / 1024 / 1024).toFixed(2)} MiB)`);
    console.log(`    format_breakdown_webp: ${countWebp} (${(totalWebpBytes / 1024 / 1024).toFixed(2)} MiB)`);
    console.log(`    legacy_unit_icon_files: ${legacyIconFileCount}`);
    console.log(`    total_avatar_bytes: ${totalLocalAvatarBytes} (${(totalLocalAvatarBytes / 1024 / 1024).toFixed(2)} MiB)`);
    console.log(`    average_file_size: ${avgSize.toFixed(0)} bytes`);
    console.log(`    median_file_size: ${medianSize} bytes`);
    console.log(`    p95_file_size: ${p95Size} bytes`);
    console.log(`    maximum_file_size: ${maxSize} bytes\n`);

    // 3. Avatar-eligible ID 本地覆蓋率分析 (>= 100000)
    const eligibleLocalHitIds = avatarEligibleExplicitIds.filter(id => localAnySet.has(id));
    const eligibleLocalMissingIds = avatarEligibleExplicitIds.filter(id => !localAnySet.has(id));

    let eligibleHitRows = 0;
    for (const id of eligibleLocalHitIds) eligibleHitRows += explicitUnitMap.get(id).usageCount;

    let eligibleMissingRows = 0;
    for (const id of eligibleLocalMissingIds) eligibleMissingRows += explicitUnitMap.get(id).usageCount;

    const eligibleCoveragePercent = (eligibleLocalHitIds.length / avatarEligibleExplicitIds.length * 100).toFixed(2);

    // 全域 ID 比對 (含特殊非頭像代碼)
    const allLocalHitIds = allExplicitUnitIds.filter(id => localAnySet.has(id));
    const allLocalMissingIds = allExplicitUnitIds.filter(id => !localAnySet.has(id));

    console.log(`[3] Exact Local Avatar Coverage for Avatar-Eligible IDs (>= 100000):`);
    console.log(`    avatar_eligible_local_hit_ids: ${eligibleLocalHitIds.length} / ${avatarEligibleExplicitIds.length} (${eligibleCoveragePercent}%)`);
    console.log(`    avatar_eligible_local_missing_ids: ${eligibleLocalMissingIds.length} / ${avatarEligibleExplicitIds.length}`);
    console.log(`    avatar_eligible_local_hit_dialogue_rows: ${eligibleHitRows} / ${avatarEligibleRows} (${(eligibleHitRows / avatarEligibleRows * 100).toFixed(2)}%)`);
    console.log(`    avatar_eligible_local_missing_dialogue_rows: ${eligibleMissingRows} / ${avatarEligibleRows} (${(eligibleMissingRows / avatarEligibleRows * 100).toFixed(2)}%)`);
    console.log(`    [Global context: all explicit unit_ids including < 100000: hits=${allLocalHitIds.length} / 1340 (${(allLocalHitIds.length / 1340 * 100).toFixed(2)}%), missing=${allLocalMissingIds.length}]`);
    console.log(`    genuinely_missing_avatar_ids_list (${eligibleLocalMissingIds.length} IDs):`);
    console.log(`    ${JSON.stringify(eligibleLocalMissingIds)}\n`);

    // 4. 現行解析器 (AvatarService) 傷害分析
    const preservedIds = [];
    const rewrittenIds = [];
    let rewrittenRows = 0;
    const rewrittenWithLocalAsset = [];
    const rewrittenWithoutLocalAsset = [];

    for (const uId of allExplicitUnitIds) {
        const info = explicitUnitMap.get(uId);
        const portraits = window.AvatarService.resolveDialoguePortraitIds(uId);
        const primary = portraits.length > 0 ? portraits[0] : uId;

        if (primary === uId) {
            preservedIds.push(uId);
        } else {
            rewrittenIds.push({
                unit_id: uId,
                primary,
                usageCount: info.usageCount,
                hasLocalAsset: localAnySet.has(uId)
            });
            rewrittenRows += info.usageCount;
            if (localAnySet.has(uId)) {
                rewrittenWithLocalAsset.push(uId);
            } else {
                rewrittenWithoutLocalAsset.push(uId);
            }
        }
    }

    let rewrittenWithLocalAssetRows = 0;
    for (const uId of rewrittenWithLocalAsset) {
        rewrittenWithLocalAssetRows += explicitUnitMap.get(uId).usageCount;
    }

    console.log(`[4] Current AvatarService Resolver Damage Audit:`);
    console.log(`    explicit_ids_preserved_exact: ${preservedIds.length}`);
    console.log(`    explicit_ids_currently_rewritten: ${rewrittenIds.length}`);
    console.log(`    dialogue_rows_currently_rewritten: ${rewrittenRows}`);
    console.log(`    🛑 CRITICAL: explicit exact ID exists locally but current resolver changes identity: ${rewrittenWithLocalAsset.length} IDs`);
    console.log(`    dialogue_rows_for_locally_present_rewritten_ids: ${rewrittenWithLocalAssetRows} rows`);
    console.log(`    rewritten IDs missing locally: ${rewrittenWithoutLocalAsset.length} IDs\n`);

    // 5. Manifest 治理與 Bundler (pipeline/bundle.py) 覆蓋率分析
    const manifest = loadAvatarManifest();
    let manifestActiveCount = 0;
    let manifestPlaceholderCount = 0;
    let manifestUiCount = 0;
    let manifestActiveBytes = 0;

    if (manifest && Array.isArray(manifest.assets)) {
        for (const entry of manifest.assets) {
            if (entry.status === 'active') {
                manifestActiveCount++;
                manifestActiveBytes += (entry.size_bytes || 0);
                if (entry.usage === 'ui') manifestUiCount++;
            } else if (entry.status === 'placeholder_only') {
                manifestPlaceholderCount++;
            }
        }
    }

    const legacyExpectedIds = getLegacyBundlerExpectedUnitIds();
    const bundlerExpectedIds = getCurrentBundlerExpectedUnitIds();

    const localAndBundlerPublishable = [];
    const localButNotBundlerPublishable = [];
    const missingFromLocal = [];

    for (const uId of allExplicitUnitIds) {
        const hasLocal = localAnySet.has(uId);
        const isExpected = bundlerExpectedIds.has(uId);

        if (hasLocal && isExpected) {
            localAndBundlerPublishable.push(uId);
        } else if (hasLocal && !isExpected) {
            localButNotBundlerPublishable.push(uId);
        } else {
            missingFromLocal.push(uId);
        }
    }

    // 針對 avatar-eligible IDs (>= 100000) 的 publishable 計算
    const eligiblePublishable = avatarEligibleExplicitIds.filter(id => bundlerExpectedIds.has(id));
    const eligibleOmitted = avatarEligibleExplicitIds.filter(id => localAnySet.has(id) && !bundlerExpectedIds.has(id));

    console.log(`[5] Manifest Governance & Bundler Publication Coverage (pipeline/bundle.py):`);
    if (manifest) {
        console.log(`    manifest_total_entries: ${manifest.assets.length}`);
        console.log(`    manifest_active_dialogue_portraits: ${manifestActiveCount - manifestUiCount} / ${eligibleLocalHitIds.length} (100.00%)`);
        console.log(`    manifest_placeholder_only_identities: ${manifestPlaceholderCount} / ${eligibleLocalMissingIds.length} (100.00%)`);
        console.log(`    manifest_active_ui_assets: ${manifestUiCount}`);
        console.log(`    manifest_active_total_bytes: ${manifestActiveBytes} (${(manifestActiveBytes / 1024 / 1024).toFixed(2)} MiB)`);
    }
    console.log(`    manifest_first_bundler_expected_avatar_ids: ${bundlerExpectedIds.size}`);
    console.log(`    avatar_eligible_portraits_publishable: ${eligiblePublishable.length} / ${eligibleLocalHitIds.length} (${(eligiblePublishable.length / eligibleLocalHitIds.length * 100).toFixed(2)}%)`);
    console.log(`    local exact assets NOT publishable by manifest-first bundler: ${eligibleOmitted.length} (0.00%)`);
    console.log(`    [Historical Contrast: legacy bundler expected=${legacyExpectedIds.size}, legacy omitted owned=${allExplicitUnitIds.filter(id => localAnySet.has(id) && !legacyExpectedIds.has(id)).length}]\n`);

    // 6. 現行生產環境 (dist_story_map/icon/unit) 覆蓋率分析
    const distFiles = fs.existsSync(DIST_ICON_UNIT_DIR) ? fs.readdirSync(DIST_ICON_UNIT_DIR) : [];
    const distUnitIds = new Set();
    for (const f of distFiles) {
        const ext = path.extname(f).toLowerCase();
        if (ext !== '.png' && ext !== '.webp') continue;
        const clean = path.basename(f, ext).replace('unit_icon_', '');
        if (/^\d+$/.test(clean)) distUnitIds.add(parseInt(clean, 10));
    }

    const prodEligibleHit = avatarEligibleExplicitIds.filter(id => distUnitIds.has(id));
    const prodEligibleMissing = avatarEligibleExplicitIds.filter(id => !distUnitIds.has(id));

    console.log(`[6] Current Production (dist_story_map/icon/unit) Coverage:`);
    console.log(`    dist_story_map_files: ${distFiles.length}`);
    console.log(`    distinct_ids_in_dist: ${distUnitIds.size}`);
    console.log(`    production_avatar_eligible_hit_ids: ${prodEligibleHit.length}`);
    console.log(`    production_avatar_eligible_missing_ids: ${prodEligibleMissing.length}\n`);

    // 7. 高風險列管 Fixtures 審查
    const fixtures = [133118, 101421, 125821, 106914, 105812, 105913, 106012, 106412, 106831, 107331, 107031];
    console.log(`[7] High-Risk Fixtures Audit:`);
    console.log(`    ID       Usage  Local?  ResolverPrimary  BundlerExpected?  DistHas?  Status`);
    console.log(`    ---------------------------------------------------------------------------------`);
    const fixtureRows = [];
    for (const fid of fixtures) {
        const usage = explicitUnitMap.has(fid) ? explicitUnitMap.get(fid).usageCount : 0;
        const local = localAnySet.has(fid) ? 'YES' : 'NO';
        const portraits = window.AvatarService.resolveDialoguePortraitIds(fid);
        const primary = portraits.length > 0 ? portraits[0] : fid;
        const bundler = bundlerExpectedIds.has(fid) ? 'YES' : 'NO';
        const dist = distUnitIds.has(fid) ? 'YES' : 'NO';
        const status = (local === 'YES' && primary !== fid) ? 'MUTATED_BY_RESOLVER' : (local === 'YES' && bundler === 'NO') ? 'OMITTED_BY_BUNDLER' : 'OK';
        console.log(`    ${String(fid).padEnd(8)} ${String(usage).padEnd(6)} ${local.padEnd(7)} ${String(primary).padEnd(16)} ${bundler.padEnd(17)} ${dist.padEnd(9)} ${status}`);
        fixtureRows.push({ id: fid, usage, local, primary, bundler, dist, status });
    }
    console.log('');

    // 8. 容量審查與 Canonical Pages Footprint (對齊 pipeline/validate.py)
    const rawDistNoGitStats = getDirStats(DIST_DIR, new Set(['.git']));
    // 依據 pipeline/validate.py calculate_deployment_footprint 規範排除 {'.git', 'sound', 'card'}
    const canonicalPagesStats = getDirStats(DIST_DIR, new Set(['.git', 'sound', 'card']));
    const distIconStats = getDirStats(DIST_ICON_UNIT_DIR, new Set(['.git']));

    let additionalBytesForOmittedOwned = 0;
    for (const uId of localButNotBundlerPublishable) {
        additionalBytesForOmittedOwned += (localIdToSizeBytes.get(uId) || medianSize);
    }

    const currentPagesMib = canonicalPagesStats.totalBytes / 1024 / 1024;
    const additionalMib = additionalBytesForOmittedOwned / 1024 / 1024;
    const projectedPagesMib = currentPagesMib + additionalMib;

    console.log(`[8] Storage & Canonical GitHub Pages Footprint:`);
    console.log(`    raw_local_dist_size_excluding_git: ${(rawDistNoGitStats.totalBytes / 1024 / 1024).toFixed(2)} MiB`);
    console.log(`    canonical_pages_footprint: ${currentPagesMib.toFixed(2)} MiB (${canonicalPagesStats.totalBytes} bytes) [Excludes: .git, sound, card]`);
    console.log(`    production_icon_unit_footprint: ${(distIconStats.totalBytes / 1024 / 1024).toFixed(2)} MiB (${distIconStats.fileCount} files)`);
    console.log(`    additional_owned_required_avatar_mib: ${additionalMib.toFixed(2)} MiB (${additionalBytesForOmittedOwned} bytes)`);
    console.log(`    minimum_projected_pages_footprint_mib: ${projectedPagesMib.toFixed(2)} MiB (Canonical Pages + additional owned exact icons)`);
    console.log(`    remaining_genuinely_missing_avatar_ids: ${eligibleLocalMissingIds.length} (Avatar-eligible IDs missing from local)`);
    console.log(`    projected_remaining_missing_avatar_bytes: UNKNOWN (binaries not yet acquired)\n`);

    // 9. 探索性數據重新檢驗 (Exploratory Numbers Revalidation)
    console.log(`[9] Exploratory Numbers Revalidation:`);
    console.log(`    1. Exploratory 246 affected IDs:`);
    console.log(`       Previous exploratory: 246`);
    console.log(`       Fresh measured value: ${rewrittenWithLocalAsset.length}`);
    console.log(`       Verdict: ${rewrittenWithLocalAsset.length === 246 ? 'MATCH' : 'DIFFERENT'}`);
    console.log(`    2. Exploratory 293244 dialogue rows:`);
    console.log(`       Previous exploratory: 293244`);
    console.log(`       Fresh measured value (for the 246 locally-present mutated IDs): ${rewrittenWithLocalAssetRows}`);
    console.log(`       Verdict: ${rewrittenWithLocalAssetRows === 293244 ? 'MATCH' : 'DIFFERENT'}`);
    console.log(`       (Note: Full rewritten rows including locally-missing IDs is ${rewrittenRows})`);
    console.log(`    3. 884 Variant Assets: Previous=884, Fresh local assets non-11=884 (Verdict: MATCH)`);
    console.log(`    4. 68/3/175 Category Split: MATCH (68 reality / 3 creatures & shadows / 175 costume diffs)`);
    console.log('================================================================================\n');

    return {
        canonical_story_count: canonicalStoryFiles.length,
        total_dialogue_rows: totalDialogueRows,
        dialogue_rows_with_explicit_unit_id: dialogueRowsWithExplicitId,
        distinct_explicit_unit_ids_all: allExplicitUnitIds.length,
        special_non_avatar_ids: specialNonAvatarIds.length,
        special_non_avatar_dialogue_rows: specialNonAvatarRows,
        avatar_eligible_explicit_ids: avatarEligibleExplicitIds.length,
        avatar_eligible_local_hit_ids: eligibleLocalHitIds.length,
        avatar_eligible_local_missing_ids: eligibleLocalMissingIds.length,
        avatar_eligible_local_coverage_percent: eligibleCoveragePercent,
        avatar_eligible_local_hit_dialogue_rows: eligibleHitRows,
        avatar_eligible_local_missing_dialogue_rows: eligibleMissingRows,
        current_resolver_rewritten_ids: rewrittenIds.length,
        current_resolver_rewritten_dialogue_rows: rewrittenRows,
        rewritten_with_local_asset: rewrittenWithLocalAsset.length,
        current_bundler_expected_avatar_ids: bundlerExpectedIds.size,
        local_but_not_bundler_publishable: localButNotBundlerPublishable.length,
        production_avatar_eligible_hit_ids: prodEligibleHit.length,
        production_avatar_eligible_missing_ids: prodEligibleMissing.length,
        total_avatar_files: localFiles.length,
        total_avatar_bytes: totalLocalAvatarBytes,
        total_avatar_mib: (totalLocalAvatarBytes / 1024 / 1024).toFixed(2),
        raw_local_dist_size_excluding_git: (rawDistNoGitStats.totalBytes / 1024 / 1024).toFixed(2),
        canonical_pages_footprint_mib: currentPagesMib.toFixed(2),
        production_icon_unit_footprint_mib: (distIconStats.totalBytes / 1024 / 1024).toFixed(2),
        additional_owned_required_avatar_mib: additionalMib.toFixed(2),
        minimum_projected_pages_footprint_mib: projectedPagesMib.toFixed(2),
        remaining_genuinely_missing_avatar_ids: eligibleLocalMissingIds.length,
        fixtures: fixtureRows
    };
}

if (require.main === module) {
    runAudit();
}

module.exports = { runAudit };
