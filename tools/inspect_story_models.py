"""List numeric references in a Taiwan story bundle's raw command stream."""
import argparse
import os
import re
import urllib.request

import UnityPy
from pcrd_fetch import SONET_HEADER, _deserialize_story_raw


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "dashboard", "versions", "cached_manifests", "storydata2_assetmanifest.txt")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("story_id", type=int)
    parser.add_argument("--commands", action="store_true")
    args = parser.parse_args()
    needle = f"storydata_{args.story_id}.unity3d"
    with open(MANIFEST, encoding="utf-8", errors="ignore") as file:
        row = next((line.strip().split(",") for line in file if needle in line), None)
    if not row or len(row) < 3:
        raise SystemExit("Story bundle not found")
    pool_hash = row[2]
    request = urllib.request.Request(
        f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}",
        headers=SONET_HEADER,
    )
    UnityPy.config.FALLBACK_UNITY_VERSION = "2021.3.20f1"
    with urllib.request.urlopen(request, timeout=30) as response:
        environment = UnityPy.load(response.read())

    values = set()
    for obj in environment.objects:
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        script = getattr(data, "script", None) or getattr(data, "m_Script", None)
        if isinstance(script, str):
            script = script.encode("utf-8", "surrogateescape")
        for command_id, arguments in _deserialize_story_raw(script or b""):
            if args.commands:
                print(command_id, arguments)
            for value in arguments:
                values.update(re.findall(r"(?<!\d)(?:1[0-9]{5}|9[0-9]{5})(?!\d)", str(value)))
    print("\n".join(sorted(values)))


if __name__ == "__main__":
    main()
