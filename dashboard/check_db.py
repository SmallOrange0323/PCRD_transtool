import sys
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), 'redive_tw.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

tbl_event = "v1_bcb39dad8fe906d3586223af561e36515101ac44636074abcfa35504ba963222"
tbl_detail = "v1_12ee700accb4e213404602824efabca5f2349d87cbdee98c8a816f1077e3d485"

try:
    c.execute(f"PRAGMA table_info({tbl_detail})")
    cols_detail = [col[1] for col in c.fetchall()]
    print("Detail cols:", cols_detail)
    
    col_dt_ev_id = cols_detail[8]
    col_dt_story_id = cols_detail[14]
    print(f"ev_id col: {col_dt_ev_id}")
    print(f"story_id col: {col_dt_story_id}")
    
    c.execute(f'SELECT "{col_dt_ev_id}", "{col_dt_story_id}" FROM "{tbl_detail}" ORDER BY "{col_dt_ev_id}" ASC LIMIT 10')
    rows = c.fetchall()
    print("Sample rows (ev_id, story_id):")
    for r in rows:
        print(f"  ev_id={r[0]}, story_id={r[1]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
