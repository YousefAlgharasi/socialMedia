import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Allow OAuth2 over HTTP for local development (127.0.0.1 / localhost)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

from app.config import GOOGLE_CLIENT_SECRETS_FILE, YOUTUBE_TOKEN_FILE

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

class YouTubeOfficialService:
    """Official YouTube Data API v3 implementation for authentication, analytics, and uploading."""

    def __init__(self):
        self.token_file = YOUTUBE_TOKEN_FILE
        self.client_secrets_file = GOOGLE_CLIENT_SECRETS_FILE
        self.verifier_file = self.token_file.parent / "youtube_pkce_verifier.txt"

    def has_client_secrets(self) -> bool:
        return self.client_secrets_file.exists()

    def has_token(self) -> bool:
        return self.token_file.exists()

    def save_client_secrets(self, client_id: str, client_secret: str):
        data = {
            "web": {
                "client_id": client_id.strip(),
                "client_secret": client_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [
                    "http://127.0.0.1:8000/api/accounts/youtube/callback",
                    "http://localhost:8000/api/accounts/youtube/callback"
                ]
            }
        }
        self.client_secrets_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_auth_url(self) -> str:
        if not self.has_client_secrets():
            raise ValueError("Google Client Secrets not configured yet.")

        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            str(self.client_secrets_file),
            scopes=SCOPES,
            redirect_uri="http://127.0.0.1:8000/api/accounts/youtube/callback"
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        # Persist PKCE verifier so the callback (a separate request) can finish the exchange
        self.verifier_file.write_text(flow.code_verifier or "", encoding="utf-8")
        return auth_url

    def handle_auth_callback(self, full_url: str) -> Dict[str, Any]:
        # Normalize localhost vs 127.0.0.1 so oauthlib doesn't reject redirect_uri mismatch
        redirect_uri = "http://127.0.0.1:8000/api/accounts/youtube/callback"
        if "localhost:8000" in full_url:
            full_url = full_url.replace("localhost:8000", "127.0.0.1:8000")

        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            str(self.client_secrets_file),
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        if self.verifier_file.exists():
            flow.code_verifier = self.verifier_file.read_text(encoding="utf-8") or None
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials

        # Save credentials for future uploads
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes
        }
        self.token_file.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
        return self.get_channel_metrics()

    def get_authenticated_service(self):
        if not self.has_token():
            return None

        data = json.loads(self.token_file.read_text(encoding="utf-8"))
        creds = google.oauth2.credentials.Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes")
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            data["token"] = creds.token
            self.token_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return build("youtube", "v3", credentials=creds)

    def get_channel_metrics(self) -> Dict[str, Any]:
        """Fetches channel statistics: title, avatar, subscriber count, total views, and total videos."""
        youtube = self.get_authenticated_service()
        if not youtube:
            return {"connected": False, "error": "Google token missing."}

        try:
            res = youtube.channels().list(mine=True, part="snippet,statistics").execute()
            items = res.get("items", [])
            if not items:
                return {
                    "connected": True,
                    "has_channel": False,
                    "title": "Connected Google Account",
                    "custom_url": "",
                    "avatar_url": "",
                    "subscribers_count": "0",
                    "views_count": "0",
                    "posts_count": "0",
                    "warning": "Authenticated! But no YouTube channel was found on this Google account. Create a channel on YouTube Studio."
                }

            item = items[0]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})

            return {
                "connected": True,
                "has_channel": True,
                "title": snippet.get("title", "My YouTube Channel"),
                "custom_url": snippet.get("customUrl", ""),
                "avatar_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "subscribers_count": stats.get("subscriberCount", "0"),
                "views_count": stats.get("viewCount", "0"),
                "posts_count": stats.get("videoCount", "0")
            }
        except Exception as e:
            err_msg = str(e)
            if "has not been used in project" in err_msg or "disabled" in err_msg.lower():
                clean_err = "YouTube Data API v3 is not enabled in your Google Cloud Project. Please enable 'YouTube Data API v3' in Google Cloud Console."
            elif "quotaExceeded" in err_msg:
                clean_err = "Google API quota exceeded for today."
            else:
                clean_err = f"YouTube API: {err_msg}"
            return {"connected": False, "error": clean_err}

    def upload_video(self, video_path: str, title: str, description: str = "", tags: str = "") -> Dict[str, Any]:
        """Uploads video to YouTube via official resumable API."""
        youtube = self.get_authenticated_service()
        if not youtube:
            return {"success": False, "error": "YouTube not connected. Please connect with Google OAuth."}

        if not Path(video_path).exists():
            return {"success": False, "error": f"Video file not found at: {video_path}"}

        tags_list = [t.strip().lstrip("#") for t in tags.split(",") if t.strip()] if tags else []

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:4900],
                "tags": tags_list[:30],
                "categoryId": "22" # People & Blogs
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(
            video_path,
            chunksize=-1, # Resumable single chunk
            resumable=True,
            mimetype="video/mp4"
        )

        try:
            req = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            response = req.execute()
            video_id = response.get("id")
            video_url = f"https://youtu.be/{video_id}" if video_id else "https://youtube.com"

            return {
                "success": True,
                "video_id": video_id,
                "post_url": video_url
            }
        except Exception as e:
            return {"success": False, "error": f"YouTube API Error: {str(e)}"}

youtube_official_service = YouTubeOfficialService()
