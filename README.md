# Project WaveMint

Project WaveMint hosts the proof-of-concept Audio Unit (AUv3) plug-in and mock gateway that demonstrate how x402-settled purchases can unlock Backblaze-hosted audio stems. Drop the Swift sources into your AU host project and run the FastAPI service locally to walk through the entire "preview → pay → download" loop.

## Repository layout

- `Plugin/` — Swift sources for the AUv3 audio unit, gateway client, and SwiftUI-based storefront UI.
- `Backend/` — FastAPI mock settlement gateway with Backblaze + x402 stubs, CLI tools, and demo data stores.
- `Config/` — Environment variable templates for local development.
- `LICENSE.md` — License for the prototype code.

A deeper, step-by-step primer lives in [`Backend/README.md`](Backend/README.md) and inline documentation across the modules.

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/Project-WaveMint.git
cd Project-WaveMint
```

> **Tip:** If you previously cloned `VideoEditor-SMManagerGPT`, you can rename that working copy to avoid confusion before adding the new remote.

### 2. Configure environment variables

Copy the example file and add your credentials:

```bash
cp Config/example.env .env
```

Fill in:

- `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_ID`, `B2_DOWNLOAD_URL`
- `X402_NODE_URL`, `X402_API_KEY`

The mock gateway falls back to deterministic demo values if these are missing, which is helpful for quick local smoke tests.

### 3. Launch the mock gateway (Python)

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

This exposes REST endpoints at `http://127.0.0.1:8000` that the AU plug-in uses during development.

### 4. Seed demo assets

```bash
python scripts/seed_assets.py \
  --sku wavemint-demo-pack \
  --path /path/to/local/file.wav \
  --title "WaveMint Demo Stem" \
  --usd 3.00 \
  --royalty-split "creator:0.7,treasury:0.2,curator:0.1"
```

The script uploads your file to Backblaze, records metadata under `Backend/data/`, and prints preview + unlock identifiers.

### 5. Integrate the AU plug-in scaffolding

1. Create a new **Audio Unit App Extension** project in Xcode (or add an AUv3 target to an existing host).
2. Replace the generated `AudioUnit.swift` and `ViewController.swift` files with the ones from `Plugin/`.
3. Wire your actual x402 SDK once it is available. The provided client currently uses async `URLSession` calls to the Python gateway to simulate settlement on the testnet.
4. Build & run inside AU Lab / Logic Pro to test the unlock workflow end-to-end.

## Next steps

- Swap the mock x402 client for the real SDK once the testnet endpoints are finalised.
- Harden the gateway with authentication, rate limiting, and persistent storage (e.g., Postgres + Redis).
- Replace the naive download caching with encrypted, per-user storage backed by the Apple File System.
- Emit detailed settlement events so they can flow into your token accounting ledger when the on-chain component launches.

## License

This prototype is released under the license specified in `LICENSE.md`. Adapt freely for internal demos and early partner explorations.
