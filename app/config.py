import os
from pathlib import Path

# Allow HTTP OAuth for local dev (127.0.0.1 / localhost)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
SESSIONS_DIR = STORAGE_DIR / "sessions"
VIDEOS_DIR = STORAGE_DIR / "videos"

# Ensure runtime directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Supported Platforms
SUPPORTED_PLATFORMS = ["youtube", "instagram", "facebook", "tiktok", "telegram"]

# Initialize platform session directories
for platform in SUPPORTED_PLATFORMS:
    (SESSIONS_DIR / platform).mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{STORAGE_DIR / 'scheduler.db'}"

GOOGLE_CLIENT_SECRETS_FILE = STORAGE_DIR / "client_secret.json"
YOUTUBE_TOKEN_FILE = STORAGE_DIR / "youtube_token.json"

# Detect installed browser (prioritize Brave)
def detect_browser():
    candidates = [
        # Brave Browser
        (Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"), "Brave"),
        (Path(os.environ.get("LOCALAPPDATA", "")) / r"BraveSoftware\Brave-Browser\Application\brave.exe", "Brave"),
        # Google Chrome
        (Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), "Chrome"),
        (Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe", "Chrome"),
        # Microsoft Edge
        (Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"), "Edge"),
        (Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"), "Edge"),
    ]
    for path, name in candidates:
        if path.exists():
            return str(path), name
    return None, "Chromium"

BROWSER_EXECUTABLE, BROWSER_NAME = detect_browser()

# Platform target login / home URLs
PLATFORM_URLS = {
    "youtube": {
        "login": "https://accounts.google.com/signin",
        "home": "https://studio.youtube.com",
        "upload": "https://studio.youtube.com/channel/videos/upload"
    },
    "instagram": {
        "login": "https://www.instagram.com/accounts/login/",
        "home": "https://www.instagram.com",
        "upload": "https://www.instagram.com"
    },
    "facebook": {
        "login": "https://www.facebook.com/login",
        "home": "https://www.facebook.com",
        "upload": "https://business.facebook.com/creatorstudio"
    },
    "tiktok": {
        "login": "https://www.tiktok.com/login",
        "home": "https://www.tiktok.com",
        "upload": "https://www.tiktok.com/creator-center/upload"
    }
}
