from typing import Optional

import asyncio
import base64
import json
import logging
import time
from http import HTTPStatus

import httpx

from src.utils.error_handling import raise_http_error

logger = logging.getLogger(__name__)

JWT_PARTS_COUNT = 3
MIN_REFRESH_INTERVAL = 5
TOKEN_EXPIRY_MARGIN = 30
MAX_BACKOFF_FAILURES = 3
MAX_BACKOFF_TIME = 300


class TokenManager:
    """Менеджер для автоматического получения и обновления токена клиента."""

    def __init__(
            self,
            sso_url: str,
            realm: str,
            client_id: str,
            client_secret: str,
            scope: str = "openid profile email roles",
    ) -> None:
        """Инициализирует менеджер токенов."""
        self.sso_url = sso_url
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope

        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: Optional[asyncio.Task] = None
        self._last_refresh_attempt: float = 0
        self._refresh_failures: int = 0

    async def get_token(self) -> str:
        """Возвращает действующий токен клиента, обновляя его при необходимости."""
        current_time = time.time()

        if self._token is None or current_time >= self._expires_at - TOKEN_EXPIRY_MARGIN:
            logger.info("Token is None or about to expire, refreshing...")
            await self.refresh_token()

        if self._token is None:
            logger.error("Failed to obtain token after refresh attempt")
            raise ValueError("Unable to obtain valid token")

        return self._token

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict:
        """
        Декодирует payload JWT-токена без проверки подписи.

        Args:
            token: JWT-токен

        Returns:
            dict: Декодированный payload или пустой словарь в случае ошибки
        """
        try:
            parts = token.split(".")
            if len(parts) != JWT_PARTS_COUNT:
                return {}

            payload_b64 = parts[1]

            padding_needed = len(payload_b64) % 4
            if padding_needed:
                payload_b64 += "=" * (4 - padding_needed)

            payload_bytes = base64.b64decode(payload_b64.replace("-", "+").replace("_", "/"))
            payload = json.loads(payload_bytes)
        except Exception:
            logger.exception("Error decoding JWT payload")
            return {}
        else:
            return payload

    async def refresh_token(self) -> Optional[int]:
        """
        Обновляет токен клиента.

        Returns:
            Optional[int]: Время жизни токена в секундах или None в случае ошибки
        """
        current_time = time.time()
        if (
                current_time - self._last_refresh_attempt < MIN_REFRESH_INTERVAL
                and self._refresh_failures > 0
        ):
            logger.warning("Too many refresh attempts in short period, backing off")
            await asyncio.sleep(MIN_REFRESH_INTERVAL)

        self._last_refresh_attempt = current_time

        async with self._refresh_lock:
            current_time = time.time()
            if self._token is not None and current_time < self._expires_at - TOKEN_EXPIRY_MARGIN:
                logger.debug("Token is still valid, skipping refresh")
                return int(self._expires_at - current_time)

            try:
                logger.info(
                    "Refreshing token for client %s in realm %s", self.client_id, self.realm
                )
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.sso_url}/api/v1/{self.realm}/oauth/token",
                        json={
                            "grant_type": "client_credentials",
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                            "scope": self.scope
                        },
                        timeout=10.0
                    )

                    response_text = response.text
                    if response.status_code != HTTPStatus.OK:
                        logger.error("Failed to get client token: %s", response_text)
                        self._refresh_failures += 1
                        raise_http_error("Failed to get client token", response.status_code)

                    data = response.json()
                    self._token = data["access_token"]

                    expires_in = None

                    # 1. Проверяем expires_at в ответе
                    if "expires_at" in data:
                        self._expires_at = float(data["expires_at"])
                        expires_in = int(self._expires_at - current_time)

                    # 2. Проверяем expires_in в ответе
                    elif "expires_in" in data:
                        expires_in = int(data["expires_in"])
                        self._expires_at = current_time + expires_in

                    # 3. Пытаемся декодировать токен
                    else:
                        payload = self._decode_jwt_payload(self._token)
                        if payload and "exp" in payload and "iat" in payload:
                            exp = float(payload["exp"])
                            iat = float(payload["iat"])
                            actual_lifetime = exp - iat
                            self._expires_at = exp
                            expires_in = int(actual_lifetime)

                    logger.info(
                        "Successfully obtained client token, expires in %s seconds", expires_in
                    )

                    self._refresh_failures = 0
                    return expires_in

            except httpx.RequestError as e:
                logger.exception("HTTP request error while getting client token")
                self._refresh_failures += 1
                raise ValueError("HTTP request error") from e
            except Exception as e:
                logger.exception("Unexpected error while getting client token")
                self._refresh_failures += 1
                raise ValueError("Unexpected error") from e

    async def start_refresh_task(self, refresh_interval: int = 60,
                                 safety_margin: int = TOKEN_EXPIRY_MARGIN) -> asyncio.Task:
        """
        Запускает фоновую задачу для периодического обновления токена.

        Args:
            refresh_interval: Минимальный интервал между обновлениями в секундах
            safety_margin: Запас времени в секундах перед истечением токена

        Returns:
            asyncio.Task: Задача обновления токена
        """
        await self.stop_refresh_task()

        async def _refresh_once():
            """Выполняет одно обновление токена и возвращает время до следующего обновления."""
            try:
                expires_in = await self.refresh_token()

                if expires_in is None:
                    next_refresh = refresh_interval
                else:
                    time_before_expiry = max(1, expires_in - safety_margin)
                    next_refresh = min(time_before_expiry, refresh_interval)

                    logger.info(
                        "Token lifetime: %ss, refreshing %ss before expiry",
                        expires_in, safety_margin
                    )

                logger.info("Next token refresh in %s seconds", next_refresh)
            except Exception:
                logger.exception("Error in refresh task")
                backoff = min(
                    60 * (2 ** min(self._refresh_failures, MAX_BACKOFF_FAILURES)),
                    MAX_BACKOFF_TIME
                )
                logger.info("Will retry in %s seconds", backoff)
                return backoff
            else:
                return next_refresh

        # ruff: noqa: PERF203
        async def _refresh_periodically():
            logger.info(
                "Token refresh task started with refresh_interval=%s, safety_margin=%s",
                refresh_interval, safety_margin
            )
            while True:
                try:
                    sleep_time = await _refresh_once()
                    await asyncio.sleep(sleep_time)
                except asyncio.CancelledError:
                    logger.info("Token refresh task cancelled")
                    raise

        self._refresh_task = asyncio.create_task(_refresh_periodically())
        return self._refresh_task

    async def stop_refresh_task(self) -> None:
        """Останавливает фоновую задачу обновления токена."""
        if self._refresh_task and not self._refresh_task.done():
            logger.info("Stopping token refresh task")
            self._refresh_task.cancel()
            try:
                await self._refresh_task
                logger.info("Token refresh task stopped")
            except asyncio.CancelledError:
                logger.info("Token refresh task cancelled")
            self._refresh_task = None
