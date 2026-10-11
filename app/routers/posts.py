import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Post, PostPlatformStatus
from app.schemas import PostCreate, PostOut, ActionResponse
from app.config import VIDEOS_DIR, SUPPORTED_PLATFORMS
from app.services.scheduler_service import scheduler_service
from app.services.uploader_service import execute_post_upload

router = APIRouter(prefix="/api/posts", tags=["posts"])

@router.get("", response_model=list[PostOut])
def get_posts(db: Session = Depends(get_db)):
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return posts

@router.post("/upload-video")
async def upload_video_file(file: UploadFile = File(...)):
    filename = f"{int(datetime.utcnow().timestamp())}_{file.filename.replace(' ', '_')}"
    file_path = VIDEOS_DIR / filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "filename": filename,
        "path": str(file_path),
        "size": file_path.stat().st_size
    }

@router.post("", response_model=PostOut)
def create_and_schedule_post(data: PostCreate, db: Session = Depends(get_db)):
    video_path = VIDEOS_DIR / data.video_filename
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video file does not exist. Please upload first.")

    # Status determination
    initial_status = "scheduled" if data.scheduled_at and data.scheduled_at > datetime.utcnow() else "draft"

    post = Post(
        title=data.title,
        description=data.description,
        tags=data.tags,
        video_filename=data.video_filename,
        video_path=str(video_path),
        scheduled_at=data.scheduled_at,
        status=initial_status
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    # Add platform entries
    for p in data.platforms:
        if p in SUPPORTED_PLATFORMS:
            plat_status = PostPlatformStatus(
                post_id=post.id,
                platform=p,
                status="pending"
            )
            db.add(plat_status)
    db.commit()
    db.refresh(post)

    # If scheduled in future, register with APScheduler
    if data.scheduled_at and data.scheduled_at > datetime.utcnow():
        scheduler_service.schedule_post(post.id, data.scheduled_at)

    return post

@router.post("/{post_id}/publish-now", response_model=ActionResponse)
async def publish_now(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Cancel any pending schedule
    scheduler_service.cancel_post(post_id)

    # Run upload asynchronously in background
    import asyncio
    asyncio.create_task(execute_post_upload(post_id))

    return ActionResponse(success=True, message=f"Publishing triggered for post #{post_id}")

@router.delete("/{post_id}", response_model=ActionResponse)
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    scheduler_service.cancel_post(post_id)
    db.delete(post)
    db.commit()

    return ActionResponse(success=True, message="Post deleted successfully")
