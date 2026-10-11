from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.database import Base, engine
from app.config import VIDEOS_DIR, BASE_DIR
from app.routers import accounts, posts, clipper
from app.services.scheduler_service import scheduler_service

# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background scheduler
    scheduler_service.start()
    print("APScheduler started successfully.")
    yield
    # Shutdown
    if scheduler_service.scheduler.running:
        scheduler_service.scheduler.shutdown()
        print("APScheduler stopped.")

app = FastAPI(
    title="OmniPost - Social Media Auto-Publisher & Scheduler",
    description="Automated multi-platform video publishing for YouTube, TikTok, Instagram, and Facebook",
    version="1.0.0",
    lifespan=lifespan
)

# API Routers
app.include_router(accounts.router)
app.include_router(posts.router)
app.include_router(clipper.router)

# Video storage file serving for live video previews
app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")

# Static frontend assets
static_dir = BASE_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "OmniPost Backend Running. Static index.html not yet created."}
