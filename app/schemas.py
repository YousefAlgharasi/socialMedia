from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AccountOut(BaseModel):
    id: int
    platform: str
    account_name: str
    is_connected: bool
    avatar_url: Optional[str] = None
    followers_count: Optional[str] = "0"
    views_count: Optional[str] = "0"
    posts_count: Optional[str] = "0"
    last_checked_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PostPlatformStatusOut(BaseModel):
    id: int
    platform: str
    status: str
    external_url: Optional[str] = None
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PostCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    tags: Optional[str] = ""
    video_filename: str
    platforms: List[str] # ["youtube", "tiktok", "instagram", "facebook"]
    scheduled_at: Optional[datetime] = None

class PostOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    tags: Optional[str] = None
    video_filename: str
    video_path: str
    scheduled_at: Optional[datetime] = None
    status: str
    created_at: datetime
    platform_statuses: List[PostPlatformStatusOut] = []

    class Config:
        from_attributes = True

class ActionResponse(BaseModel):
    success: bool
    message: str
