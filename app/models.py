import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), unique=True, index=True, nullable=False) # youtube, instagram, facebook, tiktok
    account_name = Column(String(100), default="Not Connected")
    is_connected = Column(Boolean, default=False)
    avatar_url = Column(String(500), nullable=True)
    followers_count = Column(String(50), default="0")
    views_count = Column(String(50), default="0")
    posts_count = Column(String(50), default="0")
    credentials_json = Column(Text, nullable=True)
    profile_dir = Column(String(255), nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(String(255), nullable=True) # comma-separated
    video_filename = Column(String(255), nullable=False)
    video_path = Column(String(500), nullable=False)
    scheduled_at = Column(DateTime, nullable=True) # Null if publish immediately
    status = Column(String(50), default="draft") # draft, scheduled, publishing, completed, partial, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    platform_statuses = relationship("PostPlatformStatus", back_populates="post", cascade="all, delete-orphan")

class PostPlatformStatus(Base):
    __tablename__ = "post_platform_statuses"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    platform = Column(String(50), nullable=False)
    status = Column(String(50), default="pending") # pending, uploading, success, failed
    external_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    post = relationship("Post", back_populates="platform_statuses")
