from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./courses.db"

    # Настройки SSO
    sso_url: str = "http://sso-service:8000"  # URL SSO сервиса
    sso_realm: str = "courses"  # Realm для сервиса курсов
    sso_client_id: str = "courses-api"  # ID клиента в SSO
    sso_client_secret: str = ""  # Секрет клиента (заполняется из переменных окружения)
    api_url: str = "http://localhost:8001"
    front_sso_url: str = "http://localhost:3000"

    # Настройки приложения
    app_name: str = "Courses API"
    debug: bool = True  # По умолчанию True для разработки

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
