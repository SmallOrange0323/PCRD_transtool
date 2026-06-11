import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')

STORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "story")
local_files = set(os.listdir(STORY_DIR))

# Check if story files for event 10213 exist
target_ids = [5201000, 5201001, 5201002, 5201003, 5201004, 5201005, 5201006, 5201007, 5201008, 5201009]
for sid in target_ids:
    fname = f"{sid}.json"
    fpath = os.path.join(STORY_DIR, fname)
    exists = fname in local_files
    is_file = os.path.isfile(fpath)
    print(f"{fname}: in local_files={exists}, isfile={is_file}")
    if is_file:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            stills = [e for e in data if e.get("type") == "still"]
            bgs = [e for e in data if e.get("type") == "background"]
            print(f"  stills: {[e.get('still','?') for e in stills[:3]]}, bgs: {[e.get('background','?') for e in bgs[:3]]}")
