import sys, sqlite3, os, json
sys.stdout.reconfigure(encoding='utf-8')

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "redive_tw.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

tbl_detail = "v1_12ee700accb4e213404602824efabca5f2349d87cbdee98c8a816f1077e3d485"

c.execute(f"PRAGMA table_info({tbl_detail})")
cols_detail = [col[1] for col in c.fetchall()]
col_dt_ev_id = cols_detail[8]
col_dt_story_id = cols_detail[14]

STORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "story")
local_files = set(os.listdir(STORY_DIR))

# Get detail story_ids for event 10213
c.execute(f'SELECT "{col_dt_ev_id}", "{col_dt_story_id}" FROM "{tbl_detail}" WHERE "{col_dt_ev_id}" = 10213 ORDER BY "{col_dt_story_id}" ASC')
rows = c.fetchall()
print(f"Event 10213 detail rows: {len(rows)}")
found = 0
not_found = 0
for r in rows:
    fname = f"{r[1]}.json"
    exists = fname in local_files
    if exists:
        found += 1
    else:
        not_found += 1
        print(f"  NOT FOUND: story_id={r[1]}, fname={fname}")
print(f"Found: {found}, Not found: {not_found}")

# Also check event 10201
c.execute(f'SELECT "{col_dt_ev_id}", "{col_dt_story_id}" FROM "{tbl_detail}" WHERE "{col_dt_ev_id}" = 10201 ORDER BY "{col_dt_story_id}" ASC')
rows = c.fetchall()
print(f"\nEvent 10201 detail rows: {len(rows)}")
for r in rows[:10]:
    fname = f"{r[1]}.json"
    exists = fname in local_files
    print(f"  story_id={r[1]}, fname={fname}, exists={exists}")

conn.close()
