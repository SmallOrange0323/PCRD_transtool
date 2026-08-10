"""Download and extract a Taiwan story still from the cached live manifest."""
import argparse
import os
import urllib.request

import UnityPy


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "dashboard", "versions", "cached_manifests", "storydata2_assetmanifest.txt")
OUT_DIR = os.path.join(ROOT, "dashboard", "still", "story")
HEADER = {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL)"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--still-id", type=int, required=True)
    args = parser.parse_args()
    needle = f"storydata_still_{args.still_id}.unity3d"
    with open(MANIFEST, encoding="utf-8", errors="ignore") as file:
        row = next((line.strip().split(",") for line in file if needle in line), None)
    if not row or len(row) < 3:
        raise SystemExit(f"Story still not found in manifest: {args.still_id}")

    pool_hash = row[2]
    request = urllib.request.Request(
        f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}",
        headers=HEADER,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        bundle = response.read()

    UnityPy.config.FALLBACK_UNITY_VERSION = "2021.3.20f1"
    environment = UnityPy.load(bundle)
    os.makedirs(OUT_DIR, exist_ok=True)
    for obj in environment.objects:
        if obj.type.name in {"Texture2D", "Sprite"}:
            output = os.path.join(OUT_DIR, f"{args.still_id}.webp")
            obj.read().image.save(output, format="WEBP", quality=90)
            print(f"Extracted {args.still_id}: {output}")
            return
    raise SystemExit("No image object in story still bundle")


if __name__ == "__main__":
    main()
