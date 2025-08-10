from __future__ import annotations

from fastapi import FastAPI
from sqlmodel import SQLModel

from backend.db.core import engine
from backend.routes.chat.api import router as chat_router
from backend.routes.core import router as core_router


async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


app = FastAPI(title="FundamentaLLM", version="0.1.0", lifespan=lifespan)


app.include_router(core_router)
app.include_router(chat_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
