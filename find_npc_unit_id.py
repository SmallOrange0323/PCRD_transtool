import os
import json

STORY_DIR = "dashboard/story"
files = [f for f in os.listdir(STORY_DIR) if f.endswith(".json")]

for f in files:
    try:
        with open(os.path.join(STORY_DIR, f), "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, list):
                for item in data:
                    name = item.get("name", "")
                    unit_id = item.get("unit_id")
                    if "八斗" in name or "菲絲" in name or "倭" in name:
                        print(f"File: {f}, Character: {name}, Unit ID: {unit_id}, Words: {item.get('words')[:30]}...")
    except Exception as e:
        pass
