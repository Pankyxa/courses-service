from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.courses import router as courses_router
from src.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(courses_router)
