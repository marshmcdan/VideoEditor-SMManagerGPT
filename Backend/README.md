# WaveMint Gateway Mock

A FastAPI service that mimics the production settlement gateway. It is intentionally simple so you can replace any subsystem (x402 client, Backblaze connector, persistence layer) when you are ready.

## Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/catalog` | Returns the current asset catalog. |
| `GET` | `/assets/{asset_id}/preview` | Serves a preview WAV for the requested asset. |
| `POST` | `/transactions/prepare` | Creates a pending invoice and returns a payment request + receipt token. |
| `POST` | `/transactions/settle` | Marks an invoice as settled (mock). |
| `POST` | `/transactions/confirm` | Exchanges the receipt token for a signed download URL. |

## Configuration

Load the following environment variables (e.g. via `.env` and `python-dotenv`):

- `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_ID`, `B2_DOWNLOAD_URL`
- `X402_NODE_URL`, `X402_API_KEY`

If these are absent the service falls back to deterministic demo values for quick testing.

## Development

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

## Data files

- `data/assets.json` — persisted catalog
- `data/pending.json` — outstanding receipt tokens
- `data/settlements.ndjson` — append-only ledger you can import into your treasury system or future token accounting module

These paths are relative to the `Backend/` directory.
