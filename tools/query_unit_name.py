"""Search the local Taiwan unit table by a name fragment."""
import argparse
import os
import sqlite3


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    args = parser.parse_args()
    connection = sqlite3.connect(os.path.join(ROOT, "dashboard", "redive_tw.db"))
    rows = connection.execute(
        "SELECT unit_id, unit_name FROM unit_data WHERE unit_name LIKE ? ORDER BY unit_id",
        (f"%{args.query}%",),
    ).fetchall()
    for unit_id, unit_name in rows:
        print(f"{unit_id}\t{unit_name}")


if __name__ == "__main__":
    main()
