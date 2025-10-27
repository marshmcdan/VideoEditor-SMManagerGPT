from __future__ import annotations

import os
import random
import string
from dataclasses import dataclass


@dataclass
class Invoice:
    payment_request: str
    amount_usd: float


class X402Client:
    def __init__(self, node_url: str, *, api_key: str | None = None) -> None:
        self.node_url = node_url
        self.api_key = api_key

    @classmethod
    def from_env(cls) -> "X402Client":
        return cls(
            node_url=os.getenv("X402_NODE_URL", "https://testnet.x402.example"),
            api_key=os.getenv("X402_API_KEY"),
        )

    async def create_invoice(self, amount_usd: float, memo: str) -> Invoice:
        payment_request = self._fake_payment_request(amount_usd, memo)
        return Invoice(payment_request=payment_request, amount_usd=amount_usd)

    async def pay_invoice(self, payment_request: str, wallet_secret: str) -> None:
        # In the prototype we simply log the payment. Real implementation would call node RPC.
        print(f"[x402] Settled invoice {payment_request[:16]}… with secret {wallet_secret[:6]}…")

    def _fake_payment_request(self, amount_usd: float, memo: str) -> str:
        suffix = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(24))
        return f"lnx402-test-{int(amount_usd * 100)}-{suffix}"
