from typing import Any, Optional, cast

import json
from http import HTTPStatus

import httpx
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.sso import SSOClient
from src.auth.token_manager import TokenManager
from src.config import settings
from src.models.auth import ClientClaims, UserClaims
from src.utils.error_handling import raise_http_exception

http_bearer = HTTPBearer(auto_error=False)


# ruff: noqa: RUF029
async def oauth2_scheme(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)
) -> Optional[str]:
    if credentials:
        return credentials.credentials
    return None


token_manager = TokenManager(
    sso_url=settings.sso_url,
    realm=settings.sso_realm,
    client_id=settings.sso_client_id,
    client_secret=settings.sso_client_secret,
)

sso_client = SSOClient(
    sso_url=settings.sso_url,
    realm=settings.sso_realm,
    client_id=settings.sso_client_id,
    client_secret=settings.sso_client_secret,
)


async def introspect_client_token(token: str, auth_token: Optional[str] = None) -> ClientClaims:
    """
    Проверяет токен клиента через SSO сервис.

    Args:
        token: Токен для проверки
        auth_token: Токен для авторизации запроса (если None, используется токен сервиса)

    Returns:
        ClientClaims: Информация о клиенте

    Raises:
        HTTPException: Если проверка токена не удалась
    """
    try:
        if auth_token is None:
            auth_token = await token_manager.get_token()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.sso_url}/api/v1/{settings.sso_realm}/oauth/introspect",
                json={"token": token},
                headers={"Authorization": f"Bearer {auth_token}"},
                timeout=10.0
            )

            if response.status_code != HTTPStatus.OK:
                raise_http_exception(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token introspection failed: {response.text}"
                )

            data = response.json()
            return ClientClaims.from_dict(data)
    except httpx.RequestError as e:
        raise_http_exception(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with SSO service: {e}"
        )
        return ClientClaims(active=False, cause=str(e))  # type: ignore[return-value, call-arg]
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        raise_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}"
        )
        return ClientClaims(active=False, cause=str(e))  # type: ignore[return-value, call-arg]


async def get_service_client_info() -> ClientClaims:
    """Получает информацию о самом клиенте (сервисе)."""
    try:
        client_token = await token_manager.get_token()
        return await introspect_client_token(client_token, client_token)
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, httpx.RequestError) as e:
        raise_http_exception(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting service client info: {e}"
        )
        return ClientClaims(active=False, cause=str(e))  # type: ignore[return-value, call-arg]


def extract_token_from_request(request: Request) -> Optional[str]:
    """Извлекает токен из заголовка Authorization запроса."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def extract_session_id_from_request(request: Request) -> Optional[str]:
    """Извлекает session_id из куки запроса."""
    return request.cookies.get("session_id")


def extract_auth_data_from_request(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Извлекает токен и session_id из запроса."""
    token = extract_token_from_request(request)
    session_id = extract_session_id_from_request(request)
    return token, session_id


async def get_current_client(token: Optional[str] = Depends(oauth2_scheme)) -> ClientClaims:
    """Получает информацию о текущем клиенте из токена."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    client_claims = await introspect_client_token(cast(str, token))

    if not client_claims.active:
        error_detail = getattr(client_claims, "cause", None) or "Invalid or expired token"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail
        )

    return client_claims


async def get_current_user(
        token: Optional[str] = Depends(oauth2_scheme),
        session_id: Optional[str] = Cookie(None)
) -> UserClaims:
    """
    Получает информацию о текущем пользователе.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID is missing"
        )

    claims = await sso_client.introspect_user_token(cast(str, token), cast(str, session_id))

    if not claims.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=claims.cause or "Invalid or expired token"
        )

    return claims


async def get_optional_user(
        token: Optional[str] = Depends(oauth2_scheme),
        session_id: Optional[str] = Cookie(None)
) -> Optional[UserClaims]:
    """
    Получает информацию о пользователе, если он аутентифицирован, иначе None.
    """
    if not token or not session_id:
        return None

    try:
        claims = await sso_client.introspect_user_token(cast(str, token), cast(str, session_id))
        if claims.active:
            return claims
    except (httpx.RequestError, ValueError):
        pass

    return None


def require_role(role: str):
    async def role_dependency(user: UserClaims = Depends(get_current_user)) -> UserClaims:
        if not user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have required role: {role}"
            )
        return user

    return role_dependency


async def require_admin(user: UserClaims = Depends(get_current_user)) -> UserClaims:
    if not user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user


async def get_auth_context(
        user: Optional[UserClaims] = Depends(get_optional_user),
        token: Optional[str] = Depends(oauth2_scheme)
) -> dict[str, Any]:
    """Возвращает контекст аутентификации - информацию о пользователе или клиенте."""
    if user and user.active:
        return {"type": "user", "claims": user}

    if token:
        try:
            client = await get_current_client(token)
            if client.active:
                return {"type": "client", "claims": client}
        except HTTPException:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated"
    )
