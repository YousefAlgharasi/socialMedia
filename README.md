# OmniPost — Multi-Platform Auto-Publisher & Scheduler

OmniPost is an automated social media video publishing engine that allows you to upload once and publish across **YouTube Shorts**, **TikTok**, **Instagram Reels**, and **Facebook Reels/Videos** on demand or on a scheduled timeline.

---

## Features

- **Multi-Platform Automation**: Uploads and publishes to YouTube, TikTok, Instagram, and Facebook.
- **No Developer API Bottlenecks**: Uses direct browser automation powered by Microsoft Edge and Playwright. No waiting for Meta/TikTok developer app reviews or API quotas.
- **Visual One-Click Login**: Opens an isolated browser window once so you can log in, verify 2FA, and save cookies permanently.
- **Time-Based Scheduler**: Set videos to publish immediately or schedule them for a specific date/time with persistent APScheduler.
- **Modern Glassmorphic UI**: Real-time stats, video file drag & drop, inline video previews, platform toggles, and live publishing queue.
- **Future AI Video Ready**: Built natively in Python for seamless integration with `faster-whisper`, `MediaPipe`, and local LLMs.

---

## Quick Start

### 1. Launch the Server & Dashboard
You can double-click **`run.bat`** or run:

```powershell
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open your browser at:
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## How to Connect Your Accounts

1. Navigate to the **Accounts** tab in the dashboard.
2. Click **Connect / Login** next to the platform you want to link (**YouTube**, **TikTok**, **Instagram**, or **Facebook**).
3. A Microsoft Edge browser window will open automatically.
4. Log into your account as you normally would and complete any 2-factor authentication.
5. Close the browser window when finished. Your login cookies are automatically saved to `storage/sessions/{platform}/`.
6. Click **Test Session** to verify connection status.

---

## How to Schedule a Video

1. Go to the **Create & Schedule** tab.
2. Drag and drop your video file (MP4, MOV, WEBM).
3. Enter your **Title**, **Description**, and **Hashtags**.
4. Check the platforms you want to publish to: `[✓] YouTube`, `[✓] TikTok`, `[✓] Instagram`, `[✓] Facebook`.
5. Select **Publish Immediately** or **Schedule for Later** (pick date and time).
6. Click **Publish to Platforms** / **Schedule Auto-Publish**.
7. Monitor live upload progress and status in the **Posts & Queue** tab.
