import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

story_dir = 'dashboard/story'
out_path = 'dashboard/data/story_thumbnails.json'

thumbnails = {}
for fname in os.listdir(story_dir):
    if not fname.endswith('.json'):
        continue
    sid = fname[:-5]
    try:
        with open(os.path.join(story_dir, fname), 'r', encoding='utf-8') as f:
            data = json.load(f)
            still_id = None
            bg_id = None
            for item in data:
                if item.get('type') == 'still':
                    still_id = item.get('still') or item.get('still_id')
                    # 避免 only 'end' or dummy values
                    if still_id and str(still_id).strip().lower() != 'end':
                        break
                elif item.get('type') == 'background' and not bg_id:
                    bg_id = item.get('background') or item.get('background_id') or item.get('bg') or item.get('bg_id')
            
            thumbnails[sid] = {
                'still_id': still_id,
                'bg_id': bg_id
            }
    except Exception as e:
        pass

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(thumbnails, f, ensure_ascii=False, indent=2)
print("Generated thumbnails for", len(thumbnails), "stories")
