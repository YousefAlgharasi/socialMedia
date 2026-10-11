from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.ai_clipper.pipeline import ai_clipper_pipeline
from app.services.ai_clipper.highlight_detector import highlight_detector

router = APIRouter(prefix="/api/clipper", tags=["clipper"])

class CutShortRequest(BaseModel):
    video_filename: str
    start_sec: float
    end_sec: float
    title: str
    description: Optional[str] = ""
    tags: Optional[str] = "#shorts #reels #tiktok #viral"
    platforms: Optional[List[str]] = ["youtube", "tiktok", "instagram", "facebook"]

class CombineShortsRequest(BaseModel):
    video_filename: str
    segments: List[List[float]] # [[start1, end1], [start2, end2]]
    title: str
    description: Optional[str] = ""
    tags: Optional[str] = "#shorts #highlights #viral"

class HighlightDetectRequest(BaseModel):
    transcript_segments: List[dict]

@router.post("/cut-short")
def cut_single_short(data: CutShortRequest):
    res = ai_clipper_pipeline.process_video_to_short(
        input_video_filename=data.video_filename,
        start_sec=data.start_sec,
        end_sec=data.end_sec,
        title=data.title,
        description=data.description,
        tags=data.tags,
        platforms=data.platforms
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@router.post("/combine-shorts")
def combine_clips_to_short(data: CombineShortsRequest):
    formatted_segments = [(s[0], s[1]) for s in data.segments]
    res = ai_clipper_pipeline.combine_and_make_short(
        input_video_filename=data.video_filename,
        segments=formatted_segments,
        title=data.title,
        description=data.description,
        tags=data.tags
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@router.post("/detect-highlights")
def detect_transcript_highlights(data: HighlightDetectRequest):
    highlights = highlight_detector.detect_highlights_heuristic(data.transcript_segments)
    return {"highlights": highlights}
