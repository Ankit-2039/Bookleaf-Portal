from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="BookLeaf Author Support Portal API",
    version="1.0.0",
    description="Author and admin support ticketing with AI-assisted triage and drafting.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,  # explicit origins, never "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "env": settings.app_env}