import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.api.auth import router as auth_router
from src.api.courses import router as courses_router
from src.database import Base, engine
from src.deps.auth import get_service_client_info, token_manager
from src.middleware.auth_middleware import AuthMiddleware

refresh_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.refresh_task = await token_manager.start_refresh_task()

    yield

    if hasattr(app.state, "refresh_task") and app.state.refresh_task:
        app.state.refresh_task.cancel()
        try:
            await app.state.refresh_task
        except asyncio.CancelledError:
            contextlib.suppress(asyncio.CancelledError)


app = FastAPI(
    title="Courses API",
    description="API для управления курсами с авторизацией через SSO",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    AuthMiddleware,
    public_paths=[
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/metrics",
        "/service-client-info",
        "/debug/token"
    ],
    admin_paths=[
        "/admin/"
    ]
)


@app.get("/service-client-info", tags=["debug"])
async def get_service_client_info_endpoint(client_info=Depends(get_service_client_info)):
    """Получить информацию о клиенте-сервисе"""
    return client_info


@app.get("/debug/token", tags=["debug"])
async def get_debug_token():
    """Получить текущий токен клиента (только для отладки)"""
    token = await token_manager.get_token()
    return {"token": token[:10] + "..." if token else None}


@app.get("/health", tags=["system"])
async def health_check():
    """Проверка работоспособности сервиса"""
    return {"status": "ok"}


app.include_router(courses_router)
app.include_router(auth_router)
