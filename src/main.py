from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.courses import router as courses_router
from src.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):  # noqa: RUF029
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(courses_router)
