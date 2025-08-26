from typing import Any, Optional, TypeVar

import logging
from http import HTTPStatus

from fastapi import HTTPException, status

T = TypeVar("T")

logger = logging.getLogger(__name__)


class UnauthorizedError(Exception):
    """
    Исключение, возникающее при ошибках авторизации.

    Используется, когда пользователь не авторизован или токен недействителен.
    """

    def __init__(self, message: str = "Unauthorized", cause: Optional[Exception] = None):
        self.message = message
        super().__init__(message)
        if cause:
            self.__cause__ = cause


def raise_http_error(message: str, status_code: int) -> None:
    """
    Возбуждает исключение с сообщением об ошибке HTTP.

    Args:
        message: Базовое сообщение об ошибке
        status_code: HTTP-статус код

    Raises:
        ValueError: Всегда возбуждается с форматированным сообщением
    """
    raise ValueError(f"{message}: {status_code}")


def raise_error_from_exception(message: str, exception: Exception) -> None:
    """
    Возбуждает исключение с сообщением об ошибке на основе другого исключения.

    Args:
        message: Базовое сообщение об ошибке
        exception: Исходное исключение

    Raises:
        ValueError: Всегда возбуждается с форматированным сообщением
    """
    raise ValueError(f"{message}: {exception}") from exception


def raise_http_exception(
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = "Internal server error",
        headers: Optional[dict[str, Any]] = None
) -> None:
    """
    Возбуждает HTTPException с указанными параметрами.

    Args:
        status_code: HTTP-статус код
        detail: Детальное сообщение об ошибке
        headers: Дополнительные заголовки ответа

    Raises:
        HTTPException: Всегда возбуждается с указанными параметрами
    """
    raise HTTPException(status_code=status_code, detail=detail, headers=headers)


def raise_unauthorized(message: str = "Unauthorized", cause: Optional[Exception] = None) -> None:
    """
    Возбуждает исключение UnauthorizedError с указанным сообщением.

    Args:
        message: Сообщение об ошибке
        cause: Исходное исключение, которое вызвало ошибку авторизации

    Raises:
        UnauthorizedError: Всегда возбуждается с указанным сообщением
    """
    raise UnauthorizedError(message, cause)


class ErrorHandlers:
    """
    Класс с методами для обработки ошибок.
    Используется как контейнер для статических методов.
    """

    @staticmethod
    def handle_http_response(response, error_message: str) -> None:
        """
        Проверяет HTTP-ответ и возбуждает исключение, если статус не OK.

        Args:
            response: HTTP-ответ с атрибутами status_code и text
            error_message: Сообщение об ошибке

        Raises:
            ValueError: Если статус ответа не OK
        """
        if (
                hasattr(response, "status_code")
                and hasattr(response, "text")
                and response.status_code != HTTPStatus.OK
        ):
            logger.error("%s: %s", error_message, response.text)
            raise_http_error(error_message, response.status_code)
