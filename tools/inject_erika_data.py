# -*- coding: utf-8 -*-
import sqlite3, shutil, os, sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw_db = os.path.join(BASE_DIR, 'scratch', 'temp_sonet_00600025.db')
tw_db = os.path.join(BASE_DIR, 'dashboard', 'redive_tw.db')

conn_raw = sqlite3.connect(raw_db)
conn_tw = sqlite3.connect(tw_db)
cur_raw = conn_raw.cursor()
cur_tw = conn_tw.cursor()

# 輔助 prefix 找 column
def get_col(cols, prefix):
    for c in cols:
        if c.startswith(prefix):
            return c
    raise KeyError(f"Prefix {prefix} not found in cols")

# 載入 mapping 模組
sys.path.insert(0, r'C:\Users\m8203\.gemini\antigravity\brain\ff55b746-cb99-4eea-a4a4-96597f51ddd8\scratch')
import solve_all_mappings

# 1. unit_data
print("Injecting unit_data...")
cur_raw.execute('PRAGMA table_info(v1_b700c5cdbe9c68c08e66489c003a4f96bd93131d990be24bf1eefb8d6f919795)')
ud_raw_cols = [c[1] for c in cur_raw.fetchall()]
pk_col = get_col(ud_raw_cols, "28c6c20939")
cur_raw.execute(f'SELECT * FROM v1_b700c5cdbe9c68c08e66489c003a4f96bd93131d990be24bf1eefb8d6f919795 WHERE CAST("{pk_col}" AS TEXT)="139401"')
ud_raw = cur_raw.fetchone()
ud_raw_dict = dict(zip(ud_raw_cols, ud_raw))

ud_data = {
    'unit_id': 139401,
    'unit_name': ud_raw_dict[get_col(ud_raw_cols, '5d2bcf2561')],
    'kana': ud_raw_dict[get_col(ud_raw_cols, '0da1764734')],
    'search_area_width': ud_raw_dict[get_col(ud_raw_cols, '476e048183')],
    'rarity': ud_raw_dict[get_col(ud_raw_cols, 'a98b335e60')],
    'atk_type': ud_raw_dict[get_col(ud_raw_cols, '60508ff4a3')],
    'guild_id': ud_raw_dict[get_col(ud_raw_cols, '7ec77edfa6')],
    'comment': ud_raw_dict[get_col(ud_raw_cols, '48a6210b7d')],
    'move_speed': ud_raw_dict[get_col(ud_raw_cols, '7f358ab88c')],
    'normal_atk_cast_time': ud_raw_dict[get_col(ud_raw_cols, '835f2f49a6')],
    'motion_type': ud_raw_dict[get_col(ud_raw_cols, '1a6f04d049')],
    'se_type': ud_raw_dict[get_col(ud_raw_cols, '8555babbde')],
    'cutin_1': ud_raw_dict[get_col(ud_raw_cols, '0a3a051046')],
    'prefab_id': ud_raw_dict[get_col(ud_raw_cols, '69be87e1ac')],
    'cutin1_star6': ud_raw_dict[get_col(ud_raw_cols, '9df8302282')],
    'start_time': ud_raw_dict[get_col(ud_raw_cols, '0608be2773')],
    'end_time': ud_raw_dict[get_col(ud_raw_cols, '482112ffbf')],
    'original_unit_id': ud_raw_dict[get_col(ud_raw_cols, '1547070573')],
    'prefab_id_battle': ud_raw_dict[get_col(ud_raw_cols, '34caedd5ec')],
    'only_disp_owned': ud_raw_dict[get_col(ud_raw_cols, '5cc76335bd')],
    'is_limited': ud_raw_dict[get_col(ud_raw_cols, '28e014cb57')],
    'exskill_display': ud_raw_dict[get_col(ud_raw_cols, 'ca8ee61145')],
    'cutin_2': ud_raw_dict[get_col(ud_raw_cols, '93ae13b526')],
    'cutin2_star6': ud_raw_dict[get_col(ud_raw_cols, '33300318f5')],
    'unknown_1': ud_raw_dict[get_col(ud_raw_cols, '4145307852')]
}
cur_tw.execute(f"INSERT OR REPLACE INTO unit_data ({','.join(ud_data.keys())}) VALUES ({','.join(['?']*len(ud_data))})", list(ud_data.values()))

# 2. unit_profile
print("Injecting unit_profile...")
up_map = solve_all_mappings.up_map
cur_raw.execute('SELECT * FROM v1_bdb790958cf34a91fb2fcbd6ba56479fc7b23a45d7babffba6c8ab4e58f75875 WHERE CAST("b0c9d87a23cb89acb79011335489447d4e600949d5badfe2d45f671b50ce8b4e" AS TEXT)="139401"')
up_raw = cur_raw.fetchone()
cur_raw.execute('PRAGMA table_info(v1_bdb790958cf34a91fb2fcbd6ba56479fc7b23a45d7babffba6c8ab4e58f75875)')
up_raw_cols = [c[1] for c in cur_raw.fetchall()]
up_data = {up_map[rc]: val for rc, val in zip(up_raw_cols, up_raw) if rc in up_map}
cur_tw.execute(f"INSERT OR REPLACE INTO unit_profile ({','.join(up_data.keys())}) VALUES ({','.join(['?']*len(up_data))})", list(up_data.values()))

# 3. unit_rarity
print("Injecting unit_rarity...")
ur_map = solve_all_mappings.ur_map
cur_tw.execute('PRAGMA table_info(unit_rarity)')
ur_all_tw_cols = [c[1] for c in cur_tw.fetchall()]
cur_raw.execute('SELECT * FROM v1_8f11b266c52821f80aa504e5b6fe84fb5b9da9e29cb3374d920228c4a3d3fa13 WHERE CAST("c8f7033667820174841d5b210ae3d1744df41becf9b23c7e0920e005e02e59b0" AS TEXT)="139401"')
ur_raw_rows = cur_raw.fetchall()
cur_raw.execute('PRAGMA table_info(v1_8f11b266c52821f80aa504e5b6fe84fb5b9da9e29cb3374d920228c4a3d3fa13)')
ur_raw_cols = [c[1] for c in cur_raw.fetchall()]
for r in ur_raw_rows:
    ur_data = {c: 0.0 for c in ur_all_tw_cols}
    for rc, val in zip(ur_raw_cols, r):
        if rc in ur_map:
            ur_data[ur_map[rc]] = val
    cur_tw.execute(f"INSERT OR REPLACE INTO unit_rarity ({','.join(ur_data.keys())}) VALUES ({','.join(['?']*len(ur_data))})", list(ur_data.values()))

# 4. unit_skill_data
print("Injecting unit_skill_data...")
usd_map = solve_all_mappings.usd_map
cur_tw.execute('PRAGMA table_info(unit_skill_data)')
usd_all_tw_cols = [c[1] for c in cur_tw.fetchall()]
cur_raw.execute('SELECT * FROM v1_55253f372dc210280cd81451189fd90f507cb90ddfb96dd22a0e2f2414ad2dcb WHERE CAST("3611c2aa51a1cd72e43422b41bacc17db4a90b3161c7aa9396c037a7b5eb8b44" AS TEXT)="139401"')
usd_raw = cur_raw.fetchone()
cur_raw.execute('PRAGMA table_info(v1_55253f372dc210280cd81451189fd90f507cb90ddfb96dd22a0e2f2414ad2dcb)')
usd_raw_cols = [c[1] for c in cur_raw.fetchall()]
usd_data = {c: 0 for c in usd_all_tw_cols}
for rc, val in zip(usd_raw_cols, usd_raw):
    if rc in usd_map:
        usd_data[usd_map[rc]] = val
cur_tw.execute(f"INSERT OR REPLACE INTO unit_skill_data ({','.join(usd_data.keys())}) VALUES ({','.join(['?']*len(usd_data))})", list(usd_data.values()))

# 5. unit_attack_pattern
print("Injecting unit_attack_pattern...")
uap_map = solve_all_mappings.uap_map
cur_raw.execute('SELECT * FROM v1_f883e12bf0028b7f9dcae642643c0fbb1215a48d7ddfea692a8388a8d7981ec5 WHERE CAST("cd02bb85027eed335cceb2ec365f28120f1e94fde2eafafd9a117dc951a3ca11" AS TEXT)="139401"')
uap_raw_rows = cur_raw.fetchall()
cur_raw.execute('PRAGMA table_info(v1_f883e12bf0028b7f9dcae642643c0fbb1215a48d7ddfea692a8388a8d7981ec5)')
uap_raw_cols = [c[1] for c in cur_raw.fetchall()]
for r in uap_raw_rows:
    uap_data = {uap_map[rc]: val for rc, val in zip(uap_raw_cols, r) if rc in uap_map}
    cur_tw.execute(f"INSERT OR REPLACE INTO unit_attack_pattern ({','.join(uap_data.keys())}) VALUES ({','.join(['?']*len(uap_data))})", list(uap_data.values()))

# 6. skill_data
print("Injecting skill_data...")
sd_map = solve_all_mappings.sd_map
cur_tw.execute('PRAGMA table_info(skill_data)')
sd_all_tw_cols = [c[1] for c in cur_tw.fetchall()]
cur_raw.execute('PRAGMA table_info(v1_27ace2830e51ca02d07330dc5d9cbd8041e64cd269368567dfa69879b2df4246)')
sd_raw_cols = [c[1] for c in cur_raw.fetchall()]
desc_raw_col = get_col(sd_raw_cols, '23f8b142d6')
pk_sd_col = get_col(sd_raw_cols, '83413c5996')
cur_raw.execute(f'SELECT * FROM v1_27ace2830e51ca02d07330dc5d9cbd8041e64cd269368567dfa69879b2df4246 WHERE CAST("{pk_sd_col}" AS TEXT) IN ("1394001", "1394002", "1394003", "1394501", "1394511")')
sd_raw_rows = cur_raw.fetchall()
for r in sd_raw_rows:
    sd_data = {c: 0 for c in sd_all_tw_cols}
    for rc, val in zip(sd_raw_cols, r):
        if rc in sd_map:
            sd_data[sd_map[rc]] = val
    sd_data['description'] = r[sd_raw_cols.index(desc_raw_col)]
    cur_tw.execute(f"INSERT OR REPLACE INTO skill_data ({','.join(sd_data.keys())}) VALUES ({','.join(['?']*len(sd_data))})", list(sd_data.values()))

# 7. story_detail
print("Injecting story_detail...")
story_raw_tbl = 'v1_5e51cfc597692b46540e990a16d43a8d48dc7e99c1540610b769982cc320e10f'
cur_tw.execute('PRAGMA table_info(story_detail)')
story_all_tw_cols = [c[1] for c in cur_tw.fetchall()]
cur_raw.execute(f'PRAGMA table_info("{story_raw_tbl}")')
story_raw_cols = [c[1] for c in cur_raw.fetchall()]
sid_col = get_col(story_raw_cols, '45eb61e7')
title_col = story_raw_cols[26]
sub_col = story_raw_cols[27]
cur_raw.execute(f'SELECT * FROM "{story_raw_tbl}" WHERE CAST("{title_col}" AS TEXT) LIKE "%艾麗卡%"')
story_raw_rows = cur_raw.fetchall()
for r in story_raw_rows:
    st_data = {c: 0 for c in story_all_tw_cols}
    st_data['story_id'] = r[story_raw_cols.index(sid_col)]
    st_data['story_group_id'] = 1394
    st_data['title'] = r[26]
    st_data['sub_title'] = r[27]
    st_data['start_time'] = '2026/09/12 16:00:00'
    st_data['end_time'] = '2030/12/31 15:00:00'
    st_data['force_unlock_time'] = '2030/12/31 15:00:00'
    st_data['force_unlock_time_2'] = '2030/12/31 15:00:00'
    st_data['lock_all_text'] = ''
    cur_tw.execute(f"INSERT OR REPLACE INTO story_detail ({','.join(st_data.keys())}) VALUES ({','.join(['?']*len(st_data))})", list(st_data.values()))

conn_tw.commit()
print("\n✅ All Erika data injected successfully into test database!")

# 驗證查詢
print("\n=== VERIFYING FRONTEND QUERIES ===")
# Query 1: Character List Query
q1 = """
SELECT t.max_id as unit_id, u.unit_name, u.rarity, u.search_area_width as pos, p.race, p.guild 
FROM (
    SELECT MAX(unit_id) as max_id, unit_name 
    FROM unit_data 
    WHERE unit_id < 200000 AND unit_id > 100000 AND unit_name NOT LIKE '%怪物%' AND unit_id IN (SELECT DISTINCT unit_id FROM unit_rarity)
    GROUP BY unit_name
) as t
JOIN unit_data as u ON u.unit_id = t.max_id
LEFT JOIN unit_profile as p ON u.unit_id = p.unit_id
WHERE u.unit_id = 139401
"""
cur_tw.execute(q1)
row = cur_tw.fetchone()
print("1. Character List Query for 139401:", row)

# Query 2: Stats Query
cur_tw.execute("SELECT hp, hp_growth, atk, atk_growth, def, def_growth, rarity FROM unit_rarity WHERE unit_id = 139401 ORDER BY rarity DESC LIMIT 1")
print("2. Rarity 5 stats for 139401:", cur_tw.fetchone())

# Query 3: Search Area Width
cur_tw.execute("SELECT search_area_width FROM unit_data WHERE unit_id = 139401")
print("3. Position for 139401:", cur_tw.fetchone()[0])

# Query 4: Skills Query
cur_tw.execute("SELECT union_burst, main_skill_1, main_skill_2, ex_skill_1 FROM unit_skill_data WHERE unit_id = 139401")
skills = cur_tw.fetchone()
print("4. Skill IDs for 139401:", skills)
for sid in skills:
    cur_tw.execute("SELECT name, description, icon_type FROM skill_data WHERE skill_id = ?", (sid,))
    srow = cur_tw.fetchone()
    print(f"   Skill {sid}: {srow[0]} | icon:{srow[2]} | {srow[1][:25]}...")

# Query 5: Attack Pattern
cur_tw.execute("SELECT loop_start, loop_end, atk_pattern_1, atk_pattern_2, atk_pattern_3, atk_pattern_4, atk_pattern_5 FROM unit_attack_pattern WHERE unit_id = 139401")
for p in cur_tw.fetchall():
    print("5. Attack Pattern:", p)

# Query 6: Story Detail
cur_tw.execute("SELECT story_id, title, sub_title FROM story_detail WHERE CAST(story_id AS TEXT) LIKE '139400%' ORDER BY story_id ASC")
for s in cur_tw.fetchall():
    print("6. Story Detail:", s)

conn_raw.close()
conn_tw.close()
