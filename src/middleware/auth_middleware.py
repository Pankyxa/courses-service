from typing import Optional

import logging
from urllib.parse import quote_plus

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from src.config import settings
from src.deps.auth import sso_client
from src.utils.error_handling import UnauthorizedError

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(
            self,
            app,
            public_paths: Optional[list[str]] = None,
            admin_paths: Optional[list[str]] = None
    ):
        super().__init__(app)
        self.public_paths = public_paths or []
        self.admin_paths = admin_paths or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if any(path.startswith(public_path) for public_path in self.public_paths):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        session_id = request.cookies.get("session_id")

        if not auth_header or not auth_header.startswith("Bearer "):
            return self._redirect_to_sso(request)

        token = auth_header.replace("Bearer ", "")

        try:
            if session_id:
                user_claims = await sso_client.introspect_user_token(token, session_id)

                if not user_claims.active:
                    return self._redirect_to_sso(request)

                if (
                        any(path.startswith(admin_path) for admin_path in self.admin_paths)
                        and not user_claims.has_role("admin")
                ):
                    return JSONResponse(
                        status_code=HTTP_403_FORBIDDEN,
                        content={"detail": "Admin privileges required"}
                    )

                request.state.user = user_claims
            else:
                return self._redirect_to_sso(request)
        except UnauthorizedError:
            logger.warning("Unauthorized access attempt")
            return self._redirect_to_sso(request)
        except ValueError:
            logger.exception("Value error during authentication")
            return self._redirect_to_sso(request)
        except ConnectionError:
            logger.exception("Connection error with SSO service")
            return self._redirect_to_sso(request)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected authentication error")
            return self._redirect_to_sso(request)

        return await call_next(request)

    @staticmethod
    def _redirect_to_sso(request: Request):
        """Перенаправляет на SSO для аутентификации"""
        accept_header = request.headers.get("Accept", "")
        current_url = str(request.url)
        redirect_uri = quote_plus(current_url)
        sso_login_url = (f"{settings.front_sso_url}/auth/"
                         f"?redirect_uri={redirect_uri}&realm={settings.sso_realm}")

        logger.info("Redirecting to SSO: %s", sso_login_url)

        if "application/json" in accept_header:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Not authenticated",
                    "redirect_url": sso_login_url
                }
            )

        return RedirectResponse(
            url=sso_login_url,
            status_code=302
        )
