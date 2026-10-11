"""Клиент Chat API: APP token, платформа web, те же peer-действия, что у ботов."""

from __future__ import annotations

from typing import Any

import httpx


class ChatApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class ChatApiClient:
    def __init__(self, base_url: str, token: str, bot_key: str, *, timeout: float = 15.0) -> None:
        self._root = base_url.rstrip("/")
        self._bot_key = bot_key
        self._http = httpx.AsyncClient(
            base_url=f"{self._root}/api/v1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    def _path(self, user_id: int, action: str) -> str:
        return f"/peers/web/{self._bot_key}/{user_id}/{action}"

    async def _request(
        self,
        method: str,
        user_id: int,
        action: str,
        *,
        json: dict | None = None,
    ) -> Any:
        path = self._path(user_id, action)
        try:
            response = await self._http.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise ChatApiError(503, f"Chat API недоступен: {exc}") from exc
        if response.status_code == httpx.codes.NO_CONTENT:
            return None
        if response.is_error:
            raise ChatApiError(response.status_code, response.text or response.reason_phrase)
        if not response.content:
            return None
        return response.json()

    async def visit(self, user_id: int) -> None:
        await self._request("POST", user_id, "visit")

    async def state(self, user_id: int) -> dict:
        return await self._request("GET", user_id, "state")

    async def search(self, user_id: int) -> dict:
        return await self._request("POST", user_id, "search")

    async def stop(self, user_id: int) -> dict:
        return await self._request("POST", user_id, "stop")

    async def report(self, user_id: int) -> dict:
        return await self._request("POST", user_id, "report")

    async def send_message(self, user_id: int, text: str) -> dict:
        return await self._request("POST", user_id, "messages", json={"text": text})

    async def delivery_failed(self, user_id: int) -> None:
        await self._request("POST", user_id, "delivery-failed")

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._root}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
