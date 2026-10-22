from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.migrations import upgrade_database


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    upgrade_database()
    yield


app = FastAPI(title="Vai e Volta API", version="0.1.0", lifespan=lifespan)
