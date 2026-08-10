"""Fetch and extract one Taiwan NPC portrait from a story-data AssetBundle."""
import argparse
import os
import urllib.request

import UnityPy


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "dashboard", "versions", "cached_manifests", "storydata2_assetmanifest.txt")
OUT_DIR = os.path.join(ROOT, "dashboard", "icon", "unit")
HEADER = {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL)"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit-id", type=int, required=True)
    args = parser.parse_args()
    needle = f"storydata_icon_unit_{args.unit_id}.unity3d"
    with open(MANIFEST, encoding="utf-8", errors="ignore") as file:
        row = next((line.strip().split(",") for line in file if needle in line), None)
    if not row or len(row) < 3:
        raise SystemExit(f"NPC icon not found in manifest: {args.unit_id}")

    pool_hash = row[2]
    url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}"
    request = urllib.request.Request(url, headers=HEADER)
    with urllib.request.urlopen(request, timeout=30) as response:
        bundle = response.read()

    UnityPy.config.FALLBACK_UNITY_VERSION = "2021.3.20f1"
    environment = UnityPy.load(bundle)
    os.makedirs(OUT_DIR, exist_ok=True)
    for obj in environment.objects:
        if obj.type.name in {"Texture2D", "Sprite"}:
            image = obj.read().image
            png_path = os.path.join(OUT_DIR, f"{args.unit_id}.png")
            webp_path = os.path.join(OUT_DIR, f"{args.unit_id}.webp")
            image.save(png_path, format="PNG")
            image.save(webp_path, format="WEBP", quality=90)
            print(f"Extracted {args.unit_id}: {png_path}")
            return
    raise SystemExit("No image object in NPC bundle")


if __name__ == "__main__":
    main()
