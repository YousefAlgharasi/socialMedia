import asyncio
from datetime import datetime
from app.database import SessionLocal
from app.models import Post, PostPlatformStatus
from app.services.uploaders.tiktok import TikTokUploader
from app.services.uploaders.instagram import InstagramUploader
from app.services.uploaders.facebook import FacebookUploader
from app.services.youtube_official import youtube_official_service
from app.services.telegram_official import telegram_official_service

UPLOADERS = {
    "tiktok": TikTokUploader(),
    "instagram": InstagramUploader(),
    "facebook": FacebookUploader()
}

def _run_in_proactor_thread(coro_factory):
    """Run a coroutine on a fresh Proactor loop (required by Playwright on Windows)."""
    import sys
    def runner():
        loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro_factory())
        finally:
            loop.close()
    return asyncio.to_thread(runner)

async def execute_post_upload(post_id: int):
    """
    Executes publishing for a post across all requested platforms and updates the DB.
    """
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return

        post.status = "publishing"
        db.commit()

        statuses = db.query(PostPlatformStatus).filter(PostPlatformStatus.post_id == post_id).all()
        any_success = False
        any_failure = False

        for status_item in statuses:
            platform = status_item.platform
            status_item.status = "uploading"
            status_item.updated_at = datetime.utcnow()
            db.commit()

            result = {"success": False, "error": "Unknown error"}

            if platform == "youtube":
                # Check if official YouTube service has credentials
                if youtube_official_service.has_token():
                    result = youtube_official_service.upload_video(
                        video_path=post.video_path,
                        title=post.title,
                        description=post.description or "",
                        tags=post.tags or ""
                    )
                else:
                    from app.services.uploaders.youtube import YouTubeUploader
                    result = await YouTubeUploader().upload(
                        video_path=post.video_path,
                        title=post.title,
                        description=post.description or "",
                        tags=post.tags or ""
                    )

            elif platform == "telegram":
                caption = f"{post.title}\n\n{post.description or ''}\n\n{post.tags or ''}".strip()
                result = await telegram_official_service.upload_video(
                    video_path=post.video_path,
                    caption=caption
                )

            elif platform in UPLOADERS:
                uploader = UPLOADERS[platform]
                result = await _run_in_proactor_thread(lambda: uploader.upload(
                    video_path=post.video_path,
                    title=post.title,
                    description=post.description or "",
                    tags=post.tags or ""
                ))
            else:
                result = {"success": False, "error": f"Unsupported platform: {platform}"}

            if result.get("success"):
                status_item.status = "success"
                status_item.external_url = result.get("post_url")
                status_item.error_message = None
                any_success = True
            else:
                status_item.status = "failed"
                status_item.error_message = result.get("error")
                any_failure = True

            status_item.updated_at = datetime.utcnow()
            db.commit()

        # Update overall post status
        if any_success and not any_failure:
            post.status = "completed"
        elif any_success and any_failure:
            post.status = "partial"
        else:
            post.status = "failed"

        post.updated_at = datetime.utcnow()
        db.commit()

    finally:
        db.close()
