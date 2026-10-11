import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import SESSIONS_DIR, BROWSER_EXECUTABLE
from app.services.uploaders.base import BaseUploader

class TikTokUploader(BaseUploader):
    def __init__(self):
        super().__init__("tiktok")

    async def upload(self, video_path: str, title: str, description: str, tags: str = "") -> dict:
        profile_path = str(SESSIONS_DIR / "tiktok")
        if not Path(video_path).exists():
            return {"success": False, "error": f"Video file not found at: {video_path}"}

        launch_kwargs = {
            "user_data_dir": profile_path,
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"]
        }
        if BROWSER_EXECUTABLE:
            launch_kwargs["executable_path"] = BROWSER_EXECUTABLE
        else:
            launch_kwargs["channel"] = "msedge"

        try:
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(**launch_kwargs)
                page = await context.new_page()

                # 1. Go to TikTok Creator Center Upload
                await page.goto("https://www.tiktok.com/creator-center/upload", wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(4000)

                if "login" in page.url:
                    await context.close()
                    return {"success": False, "error": "Not logged in to TikTok. Please connect your account first."}

                # 2. Upload video file - often in an iframe or direct input
                upload_frame = page
                frames = page.frames
                file_input = None
                for frame in frames:
                    try:
                        file_input = await frame.query_selector("input[type='file']")
                        if file_input:
                            upload_frame = frame
                            break
                    except Exception:
                        pass

                if not file_input:
                    file_input = await page.wait_for_selector("input[type='file']", timeout=20000)

                if not file_input:
                    await context.close()
                    return {"success": False, "error": "Could not find video upload input on TikTok."}

                await file_input.set_input_files(video_path)
                await page.wait_for_timeout(6000)

                # 3. Enter Caption / Description
                caption_text = f"{title} {description} {tags}".strip()
                caption_input = await upload_frame.query_selector(".public-DraftEditor-content, div[contenteditable='true'], [data-e2e='caption-input']")
                if caption_input:
                    await caption_input.click()
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await caption_input.type(caption_text[:2200], delay=15)

                # 4. Wait for upload process to finish
                await page.wait_for_timeout(5000)

                # 5. Click Post button
                post_btn = await upload_frame.query_selector("button:has-text('Post'), button[data-e2e='post_video_drop']")
                if post_btn:
                    await post_btn.click()
                    await page.wait_for_timeout(6000)

                await context.close()
                return {
                    "success": True,
                    "post_url": "https://www.tiktok.com",
                    "error": None
                }

        except Exception as e:
            return {"success": False, "error": f"TikTok upload failed: {str(e)}"}
