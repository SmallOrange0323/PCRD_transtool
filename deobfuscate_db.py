import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_BAK_PATH = os.path.join(BASE_DIR, "dashboard", "redive_tw_template.db")
DB_NEW_PATH = os.path.join(BASE_DIR, "dashboard", "redive_tw.db")

def main():
    if not os.path.exists(DB_BAK_PATH):
        print(f"❌ 找不到備份的明文資料庫: {DB_BAK_PATH}，無法進行數據比對還原。")
        return
        
    # ==========================================
    # 步驟一：載入舊明文資料庫結構與數據特徵
    # ==========================================
    print("[INFO] 正在載入舊明文資料庫結構與數據特徵...")
    conn_bak = sqlite3.connect(DB_BAK_PATH)
    c_bak = conn_bak.cursor()
    
    c_bak.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    bak_tables = [row[0] for row in c_bak.fetchall()]
    
    bak_table_infos = {}
    for table in bak_tables:
        c_bak.execute(f"PRAGMA table_info({table})")
        cols = c_bak.fetchall()
        col_names = [col[1] for col in cols]
        col_types = [col[2] for col in cols]
        
        c_bak.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = c_bak.fetchone()[0]
        
        data_sample = []
        if row_count > 0:
            c_bak.execute(f"SELECT * FROM {table} LIMIT 5")
            data_sample = c_bak.fetchall()
            
        bak_table_infos[table] = {
            "col_names": col_names,
            "col_types": col_types,
            "row_count": row_count,
            "data_sample": data_sample
        }
    conn_bak.close()
    print(f"[SUCCESS] 舊資料庫特徵載入完成，共 {len(bak_table_infos)} 個表。")
    
    # ==========================================
    # 步驟二：從新混淆資料庫提取特徵並關閉連接 (避免 Lock)
    # ==========================================
    print("[INFO] 正在載入新混淆資料庫結構與數據特徵...")
    conn_new_read = sqlite3.connect(DB_NEW_PATH)
    c_new_read = conn_new_read.cursor()
    
    c_new_read.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_%'")
    new_tables = [row[0] for row in c_new_read.fetchall()]
    
    new_table_infos = {}
    for table in new_tables:
        c_new_read.execute(f"PRAGMA table_info({table})")
        cols = c_new_read.fetchall()
        col_names = [col[1] for col in cols]
        col_types = [col[2] for col in cols]
        
        try:
            c_new_read.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = c_new_read.fetchone()[0]
        except Exception:
            row_count = -1
            
        data_sample = []
        if row_count > 0:
            try:
                c_new_read.execute(f"SELECT * FROM {table} LIMIT 5")
                data_sample = c_new_read.fetchall()
            except Exception:
                pass
                
        new_table_infos[table] = {
            "col_names": col_names,
            "col_types": col_types,
            "row_count": row_count,
            "data_sample": data_sample
        }
    conn_new_read.close() # 💡 讀取完畢後立刻關閉連接，釋放所有讀取鎖！
    print(f"[SUCCESS] 新資料庫特徵載入完成，共 {len(new_table_infos)} 個混淆表。")
    
    # ==========================================
    # 步驟三：在記憶體中進行比對與對照關係計算
    # ==========================================
    print("\n[START] 開始在記憶體中對比數據特徵...")
    rename_actions = []
    used_new_tables = set()
    
    for bak_table, bak_info in bak_table_infos.items():
        bak_col_count = len(bak_info["col_names"])
        bak_row_count = bak_info["row_count"]
        bak_data = bak_info["data_sample"]
        
        candidates = []
        for new_table, new_info in new_table_infos.items():
            if new_table in used_new_tables:
                continue
            if len(new_info["col_names"]) == bak_col_count and new_info["row_count"] == bak_row_count:
                candidates.append(new_table)
                
        if not candidates:
            continue
            
        matched_table = None
        
        if bak_row_count == 0:
            # 空表：比對欄位型態序列
            type_matched = []
            for cand in candidates:
                if new_table_infos[cand]["col_types"] == bak_info["col_types"]:
                    type_matched.append(cand)
            if len(type_matched) == 1:
                matched_table = type_matched[0]
        else:
            # 有數據表：比對前 5 行數據
            data_matched = []
            for cand in candidates:
                if new_table_infos[cand]["data_sample"] == bak_data:
                    data_matched.append(cand)
            if len(data_matched) == 1:
                matched_table = data_matched[0]
                
        if matched_table:
            used_new_tables.add(matched_table)
            col_mapping = []
            new_cols = new_table_infos[matched_table]["col_names"]
            for i in range(bak_col_count):
                col_mapping.append((new_cols[i], bak_info["col_names"][i]))
                
            rename_actions.append((matched_table, bak_table, col_mapping))
            
    # ==========================================
    # 步驟四：全新開啟讀寫連接，執行 ALTER 重命名 (無鎖干擾)
    # ==========================================
    if not rename_actions:
        print("❌ 未能匹配成功任何資料表。")
        return
        
    print(f"[INFO] 比對成功！準備執行資料庫結構變更 (共 {len(rename_actions)} 個表)...")
    
    conn_new = sqlite3.connect(DB_NEW_PATH)
    c_new = conn_new.cursor()
    
    restored_tables = 0
    restored_columns = 0
    
    for hashed_table, orig_table, col_mapping in rename_actions:
        try:
            # 1. 重新命名表名 (使用雙引號括住識別字)
            c_new.execute(f'ALTER TABLE "{hashed_table}" RENAME TO "{orig_table}"')
            restored_tables += 1
            
            # 2. 重新命名欄位
            for hashed_col, orig_col in col_mapping:
                if hashed_col != orig_col:
                    try:
                        c_new.execute(f'ALTER TABLE "{orig_table}" RENAME COLUMN "{hashed_col}" TO "{orig_col}"')
                        restored_columns += 1
                    except Exception as e:
                        print(f"  ⚠️ 還原欄位失敗 {orig_table}.{orig_col}: {e}")
            print(f"  ✅ 已還原: {orig_table}")
        except Exception as e:
            print(f"  ❌ 還原表名失敗 {orig_table}: {e}")
            
    conn_new.commit()
    conn_new.close()
    
    print(f"\n====================================================")
    print(f"  🎉 還原完畢！")
    print(f"  📂 還原資料表: {restored_tables} 個")
    print(f"  📂 還原欄位: {restored_columns} 個")
    print(f"====================================================\n")

if __name__ == "__main__":
    main()
