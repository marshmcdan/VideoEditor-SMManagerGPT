from __future__ import annotations

import secrets
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backblaze_client import BackblazeClient
from x402 import X402Client

DATA_DIR = Path(__file__).resolve().parent / "data"
ASSET_FILE = DATA_DIR / "assets.json"

app = FastAPI(title="WaveMint Gateway Mock", version="0.1.0")
backblaze = BackblazeClient.from_env()
x402 = X402Client.from_env()


class Asset(BaseModel):
    id: str
    title: str
    price_usd: float
    royalty_split: str
    preview_url: str
    b2_file_id: str


class PreparedPurchase(BaseModel):
    payment_request: str
    receipt_token: str


class ConfirmPurchaseResponse(BaseModel):
    download_url: str


class PrepareRequest(BaseModel):
    asset_id: str
    user_id: str


class SettleRequest(BaseModel):
    payment_request: str
    wallet_secret: str


class ConfirmRequest(BaseModel):
    asset_id: str
    receipt_token: str


class CatalogResponse(BaseModel):
    items: List[Asset]


@app.on_event("startup")
async def ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not ASSET_FILE.exists():
        ASSET_FILE.write_text("{}", encoding="utf-8")


@app.get("/catalog", response_model=CatalogResponse)
async def catalog() -> CatalogResponse:
    assets = _read_assets()
    return CatalogResponse(items=list(assets.values()))


@app.get("/assets/{asset_id}/preview")
async def preview(asset_id: str):
    assets = _read_assets()
    asset = assets.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(asset.preview_url)


@app.post("/transactions/prepare", response_model=PreparedPurchase)
async def prepare(req: PrepareRequest) -> PreparedPurchase:
    assets = _read_assets()
    asset = assets.get(req.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    invoice = await x402.create_invoice(amount_usd=asset.price_usd, memo=f"WaveMint {asset.id}")
    receipt_token = secrets.token_urlsafe(32)

    _store_pending_receipt(receipt_token, asset)

    return PreparedPurchase(payment_request=invoice.payment_request, receipt_token=receipt_token)


@app.post("/transactions/settle")
async def settle(req: SettleRequest) -> Dict[str, str]:
    await x402.pay_invoice(req.payment_request, wallet_secret=req.wallet_secret)
    return {"status": "ok"}


@app.post("/transactions/confirm", response_model=ConfirmPurchaseResponse)
async def confirm(req: ConfirmRequest) -> ConfirmPurchaseResponse:
    pending = _read_pending_receipts()
    asset = pending.get(req.receipt_token)
    if not asset or asset.id != req.asset_id:
        raise HTTPException(status_code=400, detail="Unknown receipt token")

    download_url = await backblaze.generate_download_url(file_id=asset.b2_file_id)
    _record_settlement(asset, req.receipt_token)
    return ConfirmPurchaseResponse(download_url=download_url)


# ---------------------------------------------------------------------------
# In-memory + file utilities
# ---------------------------------------------------------------------------

_PENDING_FILE = DATA_DIR / "pending.json"
_SETTLEMENT_LOG = DATA_DIR / "settlements.ndjson"


def _read_assets() -> Dict[str, Asset]:
    if not ASSET_FILE.exists():
        return {}
    return {k: Asset.parse_obj(v) for k, v in _read_json(ASSET_FILE).items()}


def _store_assets(assets: Dict[str, Asset]) -> None:
    payload = {k: v.dict() for k, v in assets.items()}
    ASSET_FILE.write_text(json_dumps(payload), encoding="utf-8")


def _read_pending_receipts() -> Dict[str, Asset]:
    if not _PENDING_FILE.exists():
        return {}
    stored = _read_json(_PENDING_FILE)
    return {token: Asset.parse_obj(asset) for token, asset in stored.items()}


def _store_pending_receipt(token: str, asset: Asset) -> None:
    pending = _read_pending_receipts()
    pending[token] = asset
    _PENDING_FILE.write_text(json_dumps({k: v.dict() for k, v in pending.items()}), encoding="utf-8")


def _record_settlement(asset: Asset, receipt_token: str) -> None:
    entry = {
        "asset_id": asset.id,
        "receipt_token": receipt_token,
        "price_usd": asset.price_usd,
        "royalty_split": asset.royalty_split,
    }
    with _SETTLEMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json_dumps(entry) + "\n")


def _read_json(path: Path) -> Dict:
    import json

    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def json_dumps(obj: Dict) -> str:
    import json

    return json.dumps(obj, indent=2, sort_keys=True)
