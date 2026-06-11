# -*- coding: utf-8 -*-
import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

STORY_DIR = "dashboard/story"

def search_keywords(keywords):
    results = {}
    for filename in os.listdir(STORY_DIR):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(STORY_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 遍歷所有的對白
            for entry in data:
                words = entry.get("words", "")
                name = entry.get("name", "")
                
                for kw in keywords:
                    if kw in words or kw in name:
                        story_id = filename.split(".")[0]
                        if story_id not in results:
                            results[story_id] = []
                        # 記錄前三句匹配到的對白做樣例
                        if len(results[story_id]) < 3:
                            results[story_id].append(f"[{name}]: {words[:60]}")
        except Exception as e:
            pass
    return results

def main():
    # 關鍵字：阿斯特朗、七個願望、雙唱、Andante、With You、志那都 (新活動角色)
    keywords = ["阿斯特朗", "七個願望", "雙唱", "Andante", "With You", "創世之殘響"]
    
    print("Searching for downloaded text containing keywords...")
    found = search_keywords(keywords)
    
    if not found:
        print("No matching stories found!")
    else:
        print(f"Found {len(found)} story JSONs matching keywords:")
        for story_id, samples in sorted(found.items(), key=lambda x: int(x[0])):
            print(f"\nStory ID: {story_id}")
            for s in samples:
                print(f"  {s}")

if __name__ == '__main__':
    main()
