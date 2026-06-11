import sqlite3
import hashlib

def get_sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

conn_bak = sqlite3.connect('dashboard/redive_tw.db.bak')
c_bak = conn_bak.cursor()

conn_new = sqlite3.connect('dashboard/redive_tw.db')
c_new = conn_new.cursor()

c_bak.execute("SELECT name FROM sqlite_master WHERE type='table'")
bak_tables = [row[0] for row in c_bak.fetchall()]

c_new.execute("SELECT name FROM sqlite_master WHERE type='table'")
new_tables = [row[0] for row in c_new.fetchall()]

print(f"Bak tables count: {len(bak_tables)}")
print(f"New tables count: {len(new_tables)}")

# 列出前5個
print("Bak tables head:", bak_tables[:5])
print("New tables head (v1_):", [t for t in new_tables if t.startswith('v1_')][:5])

# 檢查 event_data
target_hash = "v1_" + get_sha256("event_data")
print("Target hash event_data:", target_hash)
print("Is event_data hash in new_tables?", target_hash in new_tables)

conn_bak.close()
conn_new.close()
