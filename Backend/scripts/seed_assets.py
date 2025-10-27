from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from backblaze_client import BackblazeClient

ASSETS_PATH = Path(__file__).resolve().parents[1] / "data" / "assets.json"
PREVIEW_DIR = Path(__file__).resolve().parents[1] / "previews"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed WaveMint assets")
    parser.add_argument("--sku", required=True)
    parser.add_argument("--path", required=True, help="Path to the full-quality audio file")
    parser.add_argument("--title", required=True)
    parser.add_argument("--usd", type=float, required=True)
    parser.add_argument("--royalty-split", required=True, help="Comma-separated splits, e.g. creator:0.7,treasury:0.2")
    parser.add_argument("--preview", help="Optional preview file (if omitted we reuse the original)")
    args = parser.parse_args()

    client = BackblazeClient.from_env()
    file_id = await client.upload_file(name=args.sku, file_path=args.path)

    preview_path = Path(args.preview) if args.preview else Path(args.path)
    PREVIEW_DIR.mkdir(exist_ok=True)
    preview_dest = PREVIEW_DIR / f"{args.sku}-preview.wav"
    preview_dest.write_bytes(preview_path.read_bytes())

    asset = {
        "id": args.sku,
        "title": args.title,
        "price_usd": args.usd,
        "royalty_split": args.royalty_split,
        "preview_url": str(preview_dest),
        "b2_file_id": file_id,
    }

    assets = {}
    if ASSETS_PATH.exists():
        assets = json.loads(ASSETS_PATH.read_text())
    assets[args.sku] = asset
    ASSETS_PATH.parent.mkdir(exist_ok=True)
    ASSETS_PATH.write_text(json.dumps(assets, indent=2, sort_keys=True))

    print("Registered asset:")
    print(json.dumps(asset, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
