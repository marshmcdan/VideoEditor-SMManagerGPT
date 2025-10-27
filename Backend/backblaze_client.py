from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class BackblazeConfig:
    key_id: str
    application_key: str
    bucket_id: str
    download_url: Optional[str] = None


class BackblazeClient:
    def __init__(self, config: BackblazeConfig, *, client: Optional[httpx.AsyncClient] = None) -> None:
        self.config = config
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._auth_token: Optional[str] = None
        self._api_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> "BackblazeClient":
        return cls(
            BackblazeConfig(
                key_id=os.getenv("B2_KEY_ID", "demo"),
                application_key=os.getenv("B2_APPLICATION_KEY", "demo"),
                bucket_id=os.getenv("B2_BUCKET_ID", "demo"),
                download_url=os.getenv("B2_DOWNLOAD_URL"),
            )
        )

    async def generate_download_url(self, file_id: str, *, expires_in: int = 600) -> str:
        # For the prototype we simply echo back a fake signed URL when using demo credentials
        if self.config.key_id == "demo":
            return f"https://example.com/download/{file_id}?token=fake"

        await self._authorise()
        params = {"fileId": file_id, "validDurationInSeconds": expires_in}
        response = await self._client.post(f"{self._api_url}/b2_get_download_authorization", json=params, headers=self._auth_headers)
        response.raise_for_status()
        data = response.json()
        return f"{self.config.download_url}/{data['fileName']}?Authorization={data['authorizationToken']}"

    async def upload_file(self, name: str, file_path: str) -> str:
        if self.config.key_id == "demo":
            return f"demo-file-id-{int(time.time())}"

        await self._authorise()
        upload_url = await self._client.post(
            f"{self._api_url}/b2_get_upload_url",
            json={"bucketId": self.config.bucket_id},
            headers=self._auth_headers,
        )
        upload_url.raise_for_status()
        data = upload_url.json()

        with open(file_path, "rb") as fh:
            response = await self._client.post(
                data["uploadUrl"],
                content=fh.read(),
                headers={
                    "Authorization": data["authorizationToken"],
                    "X-Bz-File-Name": name,
                    "Content-Type": "b2/x-auto",
                },
            )
        response.raise_for_status()
        return response.json()["fileId"]

    async def close(self) -> None:
        await self._client.aclose()

    async def _authorise(self) -> None:
        if self._auth_token:
            return

        response = await self._client.get(
            "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
            auth=(self.config.key_id, self.config.application_key),
        )
        response.raise_for_status()
        data = response.json()
        self._auth_token = data["authorizationToken"]
        self._api_url = data["apiUrl"]
        if not self.config.download_url:
            self.config.download_url = data["downloadUrl"]

    @property
    def _auth_headers(self) -> dict:
        return {"Authorization": self._auth_token or ""}
