import httpx
import json
from pathlib import Path
from typing import Dict, Any

from app.config import STORAGE_DIR

TELEGRAM_CONFIG_FILE = STORAGE_DIR / "telegram_config.json"

class TelegramOfficialService:
    """Official Telegram Bot API for instant video uploads and channel metrics."""

    def __init__(self):
        self.config_file = TELEGRAM_CONFIG_FILE

    def has_config(self) -> bool:
        return self.config_file.exists()

    def get_config(self) -> Dict[str, Any]:
        if self.has_config():
            try:
                return json.loads(self.config_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save_config(self, bot_token: str, chat_id: str):
        data = {
            "bot_token": bot_token.strip(),
            "chat_id": chat_id.strip()
        }
        self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def get_channel_metrics(self) -> Dict[str, Any]:
        """Fetches channel title, username, subscriber count, and avatar."""
        cfg = self.get_config()
        bot_token = cfg.get("bot_token")
        chat_id = cfg.get("chat_id")

        if not bot_token or not chat_id:
            return {"connected": False}

        base_url = f"https://api.telegram.org/bot{bot_token}"

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                # 1. Get Chat details
                chat_res = await client.get(f"{base_url}/getChat", params={"chat_id": chat_id})
                chat_data = chat_res.json()
                if not chat_data.get("ok"):
                    return {"connected": False, "error": chat_data.get("description", "Failed to get chat")}

                chat_info = chat_data.get("result", {})
                title = chat_info.get("title", chat_info.get("username", "Telegram Channel"))

                # 2. Get member count (subscribers)
                members_res = await client.get(f"{base_url}/getChatMemberCount", params={"chat_id": chat_id})
                members_count = "0"
                if members_res.status_code == 200:
                    m_data = members_res.json()
                    if m_data.get("ok"):
                        members_count = str(m_data.get("result", "0"))

                # 3. Avatar
                avatar_url = ""
                photo = chat_info.get("photo")
                if photo and photo.get("small_file_id"):
                    file_res = await client.get(f"{base_url}/getFile", params={"file_id": photo["small_file_id"]})
                    if file_res.status_code == 200:
                        file_path = file_res.json().get("result", {}).get("file_path")
                        if file_path:
                            avatar_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

                return {
                    "connected": True,
                    "title": title,
                    "avatar_url": avatar_url,
                    "subscribers_count": members_count,
                    "views_count": "Active",
                    "posts_count": "Live Channel"
                }
            except Exception as e:
                return {"connected": False, "error": str(e)}

    async def upload_video(self, video_path: str, caption: str = "") -> Dict[str, Any]:
        """Uploads video to Telegram channel / chat directly."""
        cfg = self.get_config()
        bot_token = cfg.get("bot_token")
        chat_id = cfg.get("chat_id")

        if not bot_token or not chat_id:
            return {"success": False, "error": "Telegram not configured. Please enter Bot Token & Channel ID."}

        if not Path(video_path).exists():
            return {"success": False, "error": f"Video file not found: {video_path}"}

        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"

        async with httpx.AsyncClient(timeout=180.0) as client:
            try:
                with open(video_path, "rb") as video_file:
                    files = {"video": (Path(video_path).name, video_file, "video/mp4")}
                    data = {
                        "chat_id": chat_id,
                        "caption": caption[:1024],
                        "supports_streaming": "true"
                    }
                    res = await client.post(url, data=data, files=files)
                    res_json = res.json()

                    if res_json.get("ok"):
                        message_id = res_json.get("result", {}).get("message_id")
                        channel_username = chat_id.lstrip("@")
                        post_url = f"https://t.me/{channel_username}/{message_id}" if not chat_id.startswith("-") else "https://t.me"
                        return {
                            "success": True,
                            "post_url": post_url
                        }
                    else:
                        return {
                            "success": False,
                            "error": res_json.get("description", "Telegram upload failed")
                        }
            except Exception as e:
                return {"success": False, "error": f"Telegram API Exception: {str(e)}"}

telegram_official_service = TelegramOfficialService()
