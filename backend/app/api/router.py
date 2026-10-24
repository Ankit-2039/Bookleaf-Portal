from fastapi import APIRouter

from app.api.v1 import admin, auth, author

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(author.router)
api_router.include_router(admin.router)