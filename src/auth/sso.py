from typing import Any, Optional

import json
import logging
from http import HTTPStatus

import httpx

from src.config import settings
from src.models.auth import ClientClaims, TokenPair, UserClaims
from src.utils.error_handling import raise_http_error

logger = logging.getLogger(__name__)


class SSOClient:
    """Клиент для взаимодействия с SSO сервисом"""

    def __init__(
            self,
            sso_url: str = settings.sso_url,
            realm: str = settings.sso_realm,
            client_id: str = settings.sso_client_id,
            client_secret: str = settings.sso_client_secret
    ):
        self.sso_url = sso_url
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret

    @staticmethod
    async def _make_request(
            url: str,
            json_data: dict[str, Any],
            cookies: Optional[dict[str, str]] = None,
            error_prefix: str = "Request"
    ) -> httpx.Response:
        """Выполняет HTTP-запрос с обработкой ошибок"""
        try:
            async with httpx.AsyncClient() as client:
                return await client.post(
                    url,
                    json=json_data,
                    cookies=cookies,
                    timeout=10.0
                )
        except httpx.RequestError as e:
            logger.exception("HTTP request error during %s", error_prefix)
            raise ValueError("HTTP request error") from e
        except Exception as e:  # Оставляем общий перехват, так как это внутренний метод
            logger.exception("Unexpected error during %s", error_prefix)
            raise ValueError("Unexpected error") from e

    @staticmethod
    def _process_auth_response(response: httpx.Response) -> tuple[TokenPair, str]:
        """Обрабатывает ответ аутентификации и возвращает пару токенов и session_id"""
        data = response.json()
        session_id = response.cookies.get("session_id")

        if session_id is None:
            logger.error("Session ID missing in authentication response")
            raise ValueError("Authentication response missing session_id cookie")

        return TokenPair(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"]
        ), session_id

    async def introspect_token(self, token: str, session_id: Optional[str] = None) -> ClientClaims:
        """Проверяет токен клиента через SSO сервис"""
        cookies = {}
        if session_id:
            cookies["session_id"] = session_id

        url = f"{self.sso_url}/api/v1/{self.realm}/oauth/introspect"
        response = await self._make_request(
            url=url,
            json_data={"token": token},
            cookies=cookies,
            error_prefix="token introspection"
        )

        if response.status_code != HTTPStatus.OK:
            logger.error("Token introspection failed: %s", response.text)
            raise_http_error("Token introspection failed", response.status_code)

        data = response.json()
        return ClientClaims.from_dict(data)

    async def get_client_token(self) -> str:
        """Получает токен для service-to-service взаимодействия"""
        url = f"{self.sso_url}/api/v1/{self.realm}/oauth/token"
        response = await self._make_request(
            url=url,
            json_data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "openid profile email roles"
            },
            error_prefix="client token request"
        )

        if response.status_code != HTTPStatus.OK:
            logger.error("Failed to get client token: %s", response.text)
            raise_http_error("Failed to get client token", response.status_code)

        data = response.json()
        return data["access_token"]

    # МЕТОДЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ

    async def introspect_user_token(self, token: str, session_id: str) -> UserClaims:
        """Проверяет токен пользователя через SSO сервис"""
        try:
            url = f"{self.sso_url}/api/v1/{self.realm}/auth/introspect"
            response = await self._make_request(
                url=url,
                json_data={"token": token},
                cookies={"session_id": session_id},
                error_prefix="user token introspection"
            )

            if response.status_code != HTTPStatus.OK:
                logger.error("User token introspection failed: %s", response.text)
                return UserClaims(
                    active=False,
                    cause=f"Token introspection failed: {response.status_code}"
                )

            data = response.json()
            return UserClaims.from_dict(data)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.exception("HTTP error introspecting user token")
            return UserClaims(active=False, cause=f"HTTP error: {e!s}")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.exception("Data processing error introspecting user token")
            return UserClaims(active=False, cause=f"Data processing error: {e!s}")

    async def login_user(self, email: str, password: str) -> tuple[TokenPair, str]:
        """Аутентифицирует пользователя через SSO сервис"""
        url = f"{self.sso_url}/api/v1/{self.realm}/auth/login"
        response = await self._make_request(
            url=url,
            json_data={"email": email, "password": password},
            error_prefix="login"
        )

        if response.status_code != HTTPStatus.OK:
            logger.error("User login failed: %s", response.text)
            raise_http_error("Login failed", response.status_code)

        return self._process_auth_response(response)

    async def refresh_token(self, refresh_token: str, session_id: str) -> tuple[TokenPair, str]:
        """Обновляет токены пользователя"""
        try:
            url = f"{self.sso_url}/api/v1/{self.realm}/auth/refresh"
            response = await self._make_request(
                url=url,
                json_data={"refresh_token": refresh_token},
                cookies={"session_id": session_id},
                error_prefix="token refresh"
            )

            if response.status_code != HTTPStatus.OK:
                logger.error("Token refresh failed: %s", response.text)
                raise_http_error("Token refresh failed", response.status_code)

            return self._process_auth_response(response)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.exception("HTTP error refreshing token")
            raise ValueError("HTTP error refreshing token") from e
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.exception("Data processing error refreshing token")
            raise ValueError("Data processing error refreshing token") from e

    async def logout(self, session_id: str) -> bool:
        """Выполняет выход пользователя из системы"""
        try:
            url = f"{self.sso_url}/api/v1/{self.realm}/auth/logout"
            response = await self._make_request(
                url=url,
                json_data={},
                cookies={"session_id": session_id},
                error_prefix="logout"
            )
        except (httpx.RequestError, httpx.TimeoutException, ValueError):
            logger.exception("Error during logout")
            return False
        else:
            return response.status_code == HTTPStatus.NO_CONTENT
