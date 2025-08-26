from typing import Optional

from pydantic import BaseModel, EmailStr


class UserClaims(BaseModel):
    """Модель для данных пользователя из токена"""
    active: bool = False
    cause: Optional[str] = None
    iss: Optional[str] = None
    sub: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None
    realm: Optional[str] = None
    roles: Optional[list[str]] = None
    exp: Optional[int] = None
    iat: Optional[int] = None

    def has_role(self, role: str) -> bool:
        """Проверяет, есть ли у пользователя указанная роль"""
        return self.roles is not None and role in self.roles

    @classmethod
    def from_dict(cls, data: dict) -> "UserClaims":
        """Создает экземпляр из словаря, преобразуя данные при необходимости"""
        if "exp" in data and isinstance(data["exp"], float):
            data["exp"] = int(data["exp"])
        if "iat" in data and isinstance(data["iat"], float):
            data["iat"] = int(data["iat"])

        if "roles" in data and isinstance(data["roles"], str):
            data["roles"] = data["roles"].split()

        return cls(**data)


class ClientClaims(BaseModel):
    """Модель для данных клиента из токена"""
    active: bool
    iss: Optional[str] = None
    sub: Optional[str] = None
    scope: Optional[str] = None
    realm: Optional[str] = None
    exp: int
    iat: int

    def get_scopes(self) -> list[str]:
        """Возвращает список разрешений"""
        return self.scope.split() if self.scope else []

    def has_scope(self, scope: str) -> bool:
        """Проверяет, есть ли у клиента указанное разрешение"""
        return scope in self.get_scopes()

    @classmethod
    def from_dict(cls, data: dict) -> "ClientClaims":
        """Создает экземпляр из словаря, преобразуя float в int для полей exp и iat"""
        if "exp" in data and isinstance(data["exp"], float):
            data["exp"] = int(data["exp"])
        if "iat" in data and isinstance(data["iat"], float):
            data["iat"] = int(data["iat"])
        return cls(**data)


class TokenPair(BaseModel):
    """Пара токенов доступа и обновления"""
    access_token: str
    refresh_token: str
    expires_at: int
