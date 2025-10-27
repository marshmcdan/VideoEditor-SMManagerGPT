# VideoEditor-SMManagerGPT

This repository now hosts the WaveMint Audio Unit prototype scaffolding. Use it to demonstrate x402-settled unlocks for sample packs stored in Backblaze B2.

## Contents

- `WaveMintAUPrototype/README.md` — high-level documentation and setup steps.
- `WaveMintAUPrototype/Plugin/` — Swift source files to drop into an AUv3 Xcode project.
- `WaveMintAUPrototype/Backend/` — FastAPI mock gateway, Backblaze + x402 clients, and helper scripts.

Clone the repo on macOS to compile the AU plug-in and run the Python gateway locally for the full demo loop.
