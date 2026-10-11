import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import Account
from app.schemas import AccountOut, ActionResponse
from app.config import SUPPORTED_PLATFORMS, PLATFORM_URLS
from app.services.youtube_official import youtube_official_service
from app.services.telegram_official import telegram_official_service

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

class YouTubeSetupKeysRequest(BaseModel):
    client_id: str
    client_secret: str

class TelegramSetupRequest(BaseModel):
    bot_token: str
    chat_id: str

@router.get("", response_model=list[AccountOut])
async def get_accounts(db: Session = Depends(get_db)):
    accounts = []
    for platform in SUPPORTED_PLATFORMS:
        acc = db.query(Account).filter(Account.platform == platform).first()
        if not acc:
            acc = Account(
                platform=platform,
                account_name="Not Connected",
                is_connected=False,
                followers_count="0",
                views_count="0",
                posts_count="0"
            )
            db.add(acc)
            db.commit()
            db.refresh(acc)

        # Refresh metrics if connected
        if acc.platform == "youtube" and youtube_official_service.has_token():
            acc.is_connected = True
            try:
                metrics = youtube_official_service.get_channel_metrics()
                if metrics.get("connected"):
                    acc.account_name = metrics.get("title", acc.account_name)
                    acc.avatar_url = metrics.get("avatar_url", acc.avatar_url)
                    acc.followers_count = str(metrics.get("subscribers_count", "0"))
                    acc.views_count = str(metrics.get("views_count", "0"))
                    acc.posts_count = str(metrics.get("posts_count", "0"))
                    acc.last_checked_at = datetime.utcnow()
                    db.commit()
            except Exception:
                pass

        elif acc.platform == "telegram" and telegram_official_service.has_config():
            try:
                metrics = await telegram_official_service.get_channel_metrics()
                if metrics.get("connected"):
                    acc.is_connected = True
                    acc.account_name = metrics.get("title", acc.account_name)
                    acc.avatar_url = metrics.get("avatar_url", acc.avatar_url)
                    acc.followers_count = str(metrics.get("subscribers_count", "0"))
                    acc.views_count = metrics.get("views_count", "Active")
                    acc.posts_count = metrics.get("posts_count", "Channel")
                    acc.last_checked_at = datetime.utcnow()
                    db.commit()
            except Exception:
                pass

        accounts.append(acc)
    return accounts

# --- YOUTUBE OFFICIAL API ---

@router.post("/youtube/setup-keys")
def setup_youtube_keys(data: YouTubeSetupKeysRequest):
    youtube_official_service.save_client_secrets(data.client_id, data.client_secret)
    return {"success": True, "message": "Google Client Credentials saved successfully."}

@router.post("/youtube/reset-keys")
def reset_youtube_keys(db: Session = Depends(get_db)):
    if youtube_official_service.client_secrets_file.exists():
        youtube_official_service.client_secrets_file.unlink()
    if youtube_official_service.token_file.exists():
        youtube_official_service.token_file.unlink()

    acc = db.query(Account).filter(Account.platform == "youtube").first()
    if acc:
        acc.is_connected = False
        acc.account_name = "Not Connected"
        acc.avatar_url = None
        acc.followers_count = "0"
        acc.views_count = "0"
        acc.posts_count = "0"
        db.commit()

    return {"success": True, "message": "YouTube credentials reset successfully."}

@router.get("/youtube/auth-url")
def get_youtube_auth_url():
    if not youtube_official_service.has_client_secrets():
        raise HTTPException(status_code=400, detail="Please enter your Google Client ID and Secret first.")
    try:
        url = youtube_official_service.get_auth_url()
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/youtube/callback")
def youtube_oauth_callback(request: Request, db: Session = Depends(get_db)):
    import urllib.parse
    try:
        metrics = youtube_official_service.handle_auth_callback(str(request.url))
        acc = db.query(Account).filter(Account.platform == "youtube").first()
        if acc:
            acc.is_connected = True
            if metrics.get("connected"):
                acc.account_name = metrics.get("title", "My YouTube Channel")
                acc.avatar_url = metrics.get("avatar_url")
                acc.followers_count = str(metrics.get("subscribers_count", "0"))
                acc.views_count = str(metrics.get("views_count", "0"))
                acc.posts_count = str(metrics.get("posts_count", "0"))
            else:
                acc.account_name = "YouTube Account Connected"
            acc.last_checked_at = datetime.utcnow()
            db.commit()

        if metrics.get("warning"):
            return RedirectResponse(url=f"/?tab=accounts&warning={urllib.parse.quote(metrics['warning'])}")
        elif not metrics.get("connected") and metrics.get("error"):
            return RedirectResponse(url=f"/?tab=accounts&error={urllib.parse.quote(metrics['error'])}")
        else:
            return RedirectResponse(url="/?tab=accounts&connected=youtube")
    except Exception as e:
        import urllib.parse
        return RedirectResponse(url=f"/?tab=accounts&error={urllib.parse.quote(str(e))}")

# --- TELEGRAM OFFICIAL API ---

@router.post("/telegram/setup")
async def setup_telegram(data: TelegramSetupRequest, db: Session = Depends(get_db)):
    telegram_official_service.save_config(data.bot_token, data.chat_id)
    metrics = await telegram_official_service.get_channel_metrics()

    if not metrics.get("connected"):
        raise HTTPException(status_code=400, detail=metrics.get("error", "Failed to connect to Telegram chat. Make sure bot is an admin."))

    acc = db.query(Account).filter(Account.platform == "telegram").first()
    if acc:
        acc.is_connected = True
        acc.account_name = metrics.get("title", data.chat_id)
        acc.avatar_url = metrics.get("avatar_url")
        acc.followers_count = str(metrics.get("subscribers_count", "0"))
        acc.views_count = "Active"
        acc.posts_count = "Live Channel"
        acc.last_checked_at = datetime.utcnow()
        db.commit()
        db.refresh(acc)

    return {"success": True, "channel": metrics}

# --- BROWSER SESSION PLATFORMS (TikTok / Instagram / Facebook) ---

BROWSER_PLATFORMS = ("tiktok", "instagram", "facebook")

def _apply_session_result(db: Session, platform: str, result: dict):
    acc = db.query(Account).filter(Account.platform == platform).first()
    if acc:
        acc.is_connected = bool(result.get("is_connected"))
        acc.account_name = result.get("account_name") if acc.is_connected else "Not Connected"
        if acc.is_connected:
            for field in ("avatar_url", "followers_count", "views_count", "posts_count"):
                if result.get(field) is not None:
                    setattr(acc, field, result[field])
        acc.last_checked_at = datetime.utcnow()
        db.commit()

def _check_browser_platform(platform: str):
    if platform not in BROWSER_PLATFORMS:
        raise HTTPException(status_code=400, detail="This platform does not use browser sessions.")

@router.post("/{platform}/import-cookies")
async def import_browser_cookies(platform: str, close_browser: bool = False, db: Session = Depends(get_db)):
    """Copy the user's already-signed-in session from Brave/Chrome/Edge into the app."""
    import asyncio
    from app.services.session_manager import session_manager
    _check_browser_platform(platform)
    result = await asyncio.to_thread(session_manager.import_cookies_and_verify, platform, close_browser)
    _apply_session_result(db, platform, result)
    return {"success": bool(result["is_connected"]), **result}

@router.post("/{platform}/login-window")
def open_login_window(platform: str):
    """Open a visible browser window to log in once; the session is saved permanently."""
    from app.services.session_manager import session_manager
    _check_browser_platform(platform)
    return {"success": True, **session_manager.launch_interactive_login_process(platform)}

@router.post("/{platform}/verify")
async def verify_browser_session(platform: str, db: Session = Depends(get_db)):
    """Check whether the saved login is valid (run after closing the login window)."""
    import asyncio
    from app.services.session_manager import session_manager
    _check_browser_platform(platform)
    result = await asyncio.to_thread(session_manager.check_session_sync, platform)
    _apply_session_result(db, platform, result)
    return {"success": bool(result["is_connected"]), **result}

# --- DISCONNECT ---

@router.post("/{platform}/disconnect", response_model=ActionResponse)
def disconnect_account(platform: str, db: Session = Depends(get_db)):
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    acc = db.query(Account).filter(Account.platform == platform).first()
    if acc:
        acc.is_connected = False
        acc.account_name = "Not Connected"
        acc.avatar_url = None
        acc.followers_count = "0"
        acc.views_count = "0"
        acc.posts_count = "0"
        acc.last_checked_at = datetime.utcnow()
        db.commit()

    if platform == "youtube":
        if youtube_official_service.token_file.exists():
            youtube_official_service.token_file.unlink()
    elif platform == "telegram":
        if telegram_official_service.config_file.exists():
            telegram_official_service.config_file.unlink()

    return ActionResponse(success=True, message=f"{platform.capitalize()} disconnected.")
