import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from app.config import VIDEOS_DIR
from app.services.ai_clipper.video_editor import video_editor
from app.services.ai_clipper.highlight_detector import highlight_detector
from app.database import SessionLocal
from app.models import Post, PostPlatformStatus

class AIClipperPipeline:
    """
    Coordinates the video clipping and compilation workflow:
    1. Cut long video into short clips
    2. Convert to vertical 9:16 format for Shorts/Reels/TikTok
    3. Stitch multiple clips into a compiled highlight reel
    4. Register into OmniPost scheduler
    """

    def process_video_to_short(
        self,
        input_video_filename: str,
        start_sec: float,
        end_sec: float,
        title: str,
        description: str = "",
        tags: str = "#shorts #reels #tiktok #viral",
        platforms: List[str] = None
    ) -> Dict[str, Any]:
        if platforms is None:
            platforms = ["youtube", "tiktok", "instagram", "facebook"]

        source_path = VIDEOS_DIR / input_video_filename
        if not source_path.exists():
            return {"success": False, "error": f"Source video not found: {input_video_filename}"}

        timestamp = int(datetime.utcnow().timestamp())
        raw_clip_filename = f"clip_{timestamp}_{input_video_filename}"
        vertical_short_filename = f"short_{timestamp}_{input_video_filename}"

        raw_clip_path = VIDEOS_DIR / raw_clip_filename
        vertical_short_path = VIDEOS_DIR / vertical_short_filename

        # 1. Cut clip
        cut_success = video_editor.cut_clip(
            str(source_path),
            str(raw_clip_path),
            start_sec,
            end_sec
        )
        if not cut_success:
            return {"success": False, "error": "Failed to cut video segment."}

        # 2. Re-frame to vertical 9:16
        reframe_success = video_editor.convert_to_vertical_9_16(
            str(raw_clip_path),
            str(vertical_short_path),
            style="blur_background"
        )

        # Cleanup intermediate raw horizontal cut if vertical succeeded
        if reframe_success and raw_clip_path.exists():
            raw_clip_path.unlink()

        final_filename = vertical_short_filename if reframe_success else raw_clip_filename
        final_path = vertical_short_path if reframe_success else raw_clip_path

        # 3. Register as an OmniPost draft post in the database
        db = SessionLocal()
        try:
            post = Post(
                title=title,
                description=description,
                tags=tags,
                video_filename=final_filename,
                video_path=str(final_path),
                status="draft"
            )
            db.add(post)
            db.commit()
            db.refresh(post)

            for p in platforms:
                plat_status = PostPlatformStatus(
                    post_id=post.id,
                    platform=p,
                    status="pending"
                )
                db.add(plat_status)
            db.commit()
            db.refresh(post)

            return {
                "success": True,
                "post_id": post.id,
                "video_filename": final_filename,
                "duration": round(end_sec - start_sec, 2),
                "title": title
            }
        finally:
            db.close()

    def combine_and_make_short(
        self,
        input_video_filename: str,
        segments: List[tuple], # list of (start_sec, end_sec)
        title: str,
        description: str = "",
        tags: str = "#shorts #highlights #viral"
    ) -> Dict[str, Any]:
        """
        Takes multiple segments from a video, cuts each, combines them,
        converts the compilation to 9:16 vertical, and registers into OmniPost.
        """
        source_path = VIDEOS_DIR / input_video_filename
        if not source_path.exists():
            return {"success": False, "error": "Source video not found"}

        timestamp = int(datetime.utcnow().timestamp())
        extracted_clips = []

        for i, (start, end) in enumerate(segments):
            clip_name = f"temp_seg_{timestamp}_{i}.mp4"
            clip_path = VIDEOS_DIR / clip_name
            if video_editor.cut_clip(str(source_path), str(clip_path), start, end):
                extracted_clips.append(str(clip_path))

        if not extracted_clips:
            return {"success": False, "error": "No clips could be extracted."}

        # Combine clips
        combined_filename = f"combined_{timestamp}.mp4"
        combined_path = VIDEOS_DIR / combined_filename
        combine_ok = video_editor.combine_clips(extracted_clips, str(combined_path))

        # Cleanup temporary segment cuts
        for c in extracted_clips:
            if Path(c).exists():
                Path(c).unlink()

        if not combine_ok:
            return {"success": False, "error": "Failed to stitch video clips together."}

        # Convert compilation to 9:16 vertical
        vertical_compilation_filename = f"short_reel_{timestamp}.mp4"
        vertical_compilation_path = VIDEOS_DIR / vertical_compilation_filename
        reframe_ok = video_editor.convert_to_vertical_9_16(
            str(combined_path),
            str(vertical_compilation_path),
            style="blur_background"
        )

        if reframe_ok and combined_path.exists():
            combined_path.unlink()

        final_filename = vertical_compilation_filename if reframe_ok else combined_filename
        final_path = vertical_compilation_path if reframe_ok else combined_path

        # Register to DB
        db = SessionLocal()
        try:
            post = Post(
                title=title,
                description=description,
                tags=tags,
                video_filename=final_filename,
                video_path=str(final_path),
                status="draft"
            )
            db.add(post)
            db.commit()
            db.refresh(post)

            for p in ["youtube", "tiktok", "instagram", "facebook"]:
                plat_status = PostPlatformStatus(
                    post_id=post.id,
                    platform=p,
                    status="pending"
                )
                db.add(plat_status)
            db.commit()

            return {
                "success": True,
                "post_id": post.id,
                "video_filename": final_filename,
                "title": title
            }
        finally:
            db.close()

ai_clipper_pipeline = AIClipperPipeline()
