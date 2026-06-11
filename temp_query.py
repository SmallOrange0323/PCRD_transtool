import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]

print("Total tables in DB:", len(tables))
print("=== All tables ===")
for idx, t in enumerate(sorted(tables), 1):
    print(f"{idx:3d}. {t}")
        
conn.close()
