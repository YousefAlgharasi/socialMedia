import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import SESSIONS_DIR, BROWSER_EXECUTABLE
from app.services.uploaders.base import BaseUploader

class FacebookUploader(BaseUploader):
    def __init__(self):
        super().__init__("facebook")

    async def upload(self, video_path: str, title: str, description: str, tags: str = "") -> dict:
        profile_path = str(SESSIONS_DIR / "facebook")
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

                # 1. Open Facebook
                await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(4000)

                if "login" in page.url:
                    await context.close()
                    return {"success": False, "error": "Not logged in to Facebook. Please connect your account first."}

                # 2. Look for "Photo/video" button or post creator
                photo_video_btn = await page.query_selector("span:has-text('Photo/video'), div[aria-label*='Photo/video']")
                if photo_video_btn:
                    await photo_video_btn.click()
                    await page.wait_for_timeout(2000)

                # 3. File Input
                file_input = await page.wait_for_selector("input[type='file']", timeout=20000)
                if not file_input:
                    await context.close()
                    return {"success": False, "error": "Could not find file input on Facebook."}

                await file_input.set_input_files(video_path)
                await page.wait_for_timeout(4000)

                # 4. Post text
                caption = f"{title}\n\n{description}\n\n{tags}".strip()
                text_input = await page.query_selector("div[role='textbox'], div[aria-label*='What\'s on your mind']")
                if text_input:
                    await text_input.click()
                    await text_input.type(caption[:2000], delay=15)

                # 5. Click Post button
                post_btn = await page.query_selector("div[aria-label='Post'], div[role='button']:has-text('Post')")
                if post_btn:
                    await post_btn.click()
                    await page.wait_for_timeout(8000)

                await context.close()
                return {
                    "success": True,
                    "post_url": "https://www.facebook.com",
                    "error": None
                }

        except Exception as e:
            return {"success": False, "error": f"Facebook upload failed: {str(e)}"}
