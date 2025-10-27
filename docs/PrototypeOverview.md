# WaveMint AU Prototype

This document captures the conceptual prototype for the WaveMint Audio Unit (AUv3) plug-in that demonstrates how the creative-economy flows from the WaveMint brief can be modelled in software. The goal is to provide an immediately hackable reference implementation you can open in Xcode, wire up to a JUCE host, or reuse as scaffolding when you are ready to ship production code.

> **Important:** This repository does not compile on its own inside this Linux-based environment—the Swift source is meant to be copied into a macOS/iOS AUv3 project. The Python microservice can be executed locally to simulate x402 testnet transactions and asset delivery from Backblaze B2.

## High-level architecture

```
┌──────────────────────────┐
│   AU Host (Logic, etc.)  │
└────────────┬─────────────┘
             │ AUv3 IPC
┌────────────▼─────────────┐
│ WaveMintAudioUnit (DSP)  │  ◄─ pulls stems after settlement
├──────────────────────────┤
│ WaveMintViewController   │  ◄─ presents pay-to-unlock UI
└────────────┬─────────────┘
             │ REST/WebSocket
┌────────────▼─────────────┐
│  WaveMint Gateway API    │  ◄─ Python FastAPI mock in `Backend/`
├──────────────────────────┤
│  x402 Testnet Client     │  ◄─ Simulated settlement + receipt
├──────────────────────────┤
│  Backblaze B2 Retriever  │  ◄─ Pre-signed download URLs
└──────────────────────────┘
```

### Flow
1. **Creator uploads assets** to a private Backblaze B2 bucket via the provided CLI helper. Metadata (SKU, preview URL, price in USD, payout splits) is registered in the gateway.
2. **User browses sounds** inside the AU plug-in. Preview streams are unauthenticated and low bitrate.
3. When the user taps **“Unlock Stem”**, the plug-in:
   - Calls the gateway's `/transactions/prepare` endpoint.
   - The gateway requests payment on the x402 testnet and returns a `payment_request` (Bolt11-like string) plus an ephemeral asset key.
4. The plug-in uses a **Swift x402 client** (stubbed) to settle the invoice on testnet.
5. The gateway validates the payment (mocked) and returns a signed Backblaze URL. The plug-in downloads the full-resolution audio into its sandbox and exposes it to the host.
6. Fee flow + payouts are logged so they can be replayed when the on-chain token launches.

## Contents

| Path | Description |
| ---- | ----------- |
| `Plugin/WaveMintAudioUnit.swift` | Audio Unit kernel + asset loader hooks. |
| `Plugin/WaveMintViewController.swift` | SwiftUI/UIKit hybrid UI for showcasing unlock + settlement. |
| `Backend/app.py` | FastAPI mock gateway orchestrating x402 payments and Backblaze links. |
| `Backend/backblaze_client.py` | Helper that generates download URLs using Backblaze application keys. |
| `Backend/x402.py` | Minimal testnet client abstraction (mock). |
| `Backend/scripts/seed_assets.py` | CLI for registering B2 files with metadata. |
| `Config/example.env` | Environment variable template for secrets. |

## Getting started

### 1. Prepare environment variables
Copy `Config/example.env` to `.env` in the repo root (or export manually):

```
cp Config/example.env .env
```

Fill in your **Backblaze B2** credentials and, when available, your x402 testnet keys.

### 2. Run the mock gateway locally

```
cd Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

This exposes REST endpoints at `http://127.0.0.1:8000` that the AU can hit during development.

### 3. Seed demo assets

```
python scripts/seed_assets.py \
  --sku wavemint-demo-pack \
  --path /path/to/local/file.wav \
  --title "WaveMint Demo Stem" \
  --usd 3.00 \
  --royalty-split "creator:0.7,treasury:0.2,curator:0.1"
```

The script uploads your file to Backblaze, stores the metadata JSON in `Backend/data/assets.json`, and prints the preview + unlock IDs.

### 4. Wire the Swift sources into Xcode

1. Create a new **Audio Unit App Extension** project.
2. Replace the generated `AudioUnit.swift` and `ViewController.swift` with the files from `Plugin/`.
3. Add a Swift Package that wraps your actual x402 SDK once available. For now, the stub uses async `URLSession` calls to the Python gateway.
4. Build & run inside AU Lab / Logic Pro to test the unlocking flow.

### 5. Next steps
- Swap the mock x402 client with a real SDK when the testnet endpoints are finalised.
- Replace the naive download caching with encrypted, per-user storage (e.g., Apple File System protected directories).
- Introduce background reconciliation to push settled invoices into your token accounting ledger.
- Harden the gateway with auth, rate limiting, and production-ready storage (Postgres + Redis).

## License
The prototype is released under the same license as the parent repository. Adapt freely for internal demos.
