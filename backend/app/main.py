from contextlib import asynccontextmanager

from app.api.router import api_router
from app.core.errors import register_error_handlers

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db import mongo

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    await mongo.ensure_indexes(mongo.get_db())
    yield
    await mongo.close()


app = FastAPI(
    title="BookLeaf Author Support Portal API",
    version="1.0.0",
    description="Author and admin support ticketing with AI-assisted triage and drafting.",
    lifespan=lifespan,
)

register_error_handlers(app)
app.include_router(api_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


@app.get("/health", tags=["system"])
async def health():
    await mongo.get_db().command("ping")
    return {"status": "ok", "db": "ok"}