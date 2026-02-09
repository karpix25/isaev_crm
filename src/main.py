import os
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.database import init_db, close_db
from src.api import api_router
from src.bot import bot, dp


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    openapi_url=f"{settings.api_v1_str}/openapi.json",
)

# CORS middleware
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Add origins from settings if any
if settings.all_cors_origins:
    origins.extend([str(origin) for origin in settings.all_cors_origins])

# Unique origins
origins = list(set(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if settings.app_env != "development" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lifespan events
@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()

# Include API routes
app.include_router(api_router)

# Mount static files for avatars/media
media_path = os.path.join(os.getcwd(), "media")
os.makedirs(media_path, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_path), name="media")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
