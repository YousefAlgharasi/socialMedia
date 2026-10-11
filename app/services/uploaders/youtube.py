import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import SESSIONS_DIR, BROWSER_EXECUTABLE
from app.services.uploaders.base import BaseUploader

class YouTubeUploader(BaseUploader):
    def __init__(self):
        super().__init__("youtube")

    async def upload(self, video_path: str, title: str, description: str, tags: str = "") -> dict:
        profile_path = str(SESSIONS_DIR / "youtube")
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

                # 1. Navigate to Studio Upload
                await page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(3000)

                if "accounts.google.com" in page.url:
                    await context.close()
                    return {"success": False, "error": "Not logged in to YouTube. Please connect your account first."}

                # Click Create -> Upload videos or go directly to upload
                create_btn = await page.query_selector("#create-icon, ytcp-button#create-button, [aria-label='Create']")
                if create_btn:
                    await create_btn.click()
                    await page.wait_for_timeout(1000)
                    upload_option = await page.query_selector("tp-yt-paper-item:has-text('Upload videos'), [test-id='upload-video']")
                    if upload_option:
                        await upload_option.click()
                else:
                    await page.goto("https://studio.youtube.com/channel/videos/upload", wait_until="domcontentloaded")

                # 2. Wait for file input and attach video
                file_input = await page.wait_for_selector("input[type='file']", timeout=20000)
                if not file_input:
                    await context.close()
                    return {"success": False, "error": "Could not find video file input on YouTube Studio."}

                await file_input.set_input_files(video_path)
                await page.wait_for_timeout(5000)

                # 3. Fill Title
                title_input = await page.wait_for_selector("#title-textarea #textbox", timeout=25000)
                if title_input:
                    await title_input.click()
                    # Select all and replace
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    await title_input.type(title[:100], delay=30)

                # 4. Fill Description
                desc_input = await page.query_selector("#description-textarea #textbox")
                if desc_input and description:
                    await desc_input.click()
                    full_desc = description
                    if tags:
                        full_desc += f"\n\n{tags}"
                    await desc_input.type(full_desc[:4900], delay=10)

                # 5. Set 'Not Made for Kids'
                not_for_kids = await page.query_selector("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']")
                if not_for_kids:
                    await not_for_kids.click()

                # 6. Click 'Next' through Video Elements & Checks to Visibility
                for _ in range(3):
                    next_btn = await page.query_selector("#next-button")
                    if next_btn:
                        await next_btn.click()
                        await page.wait_for_timeout(2000)

                # 7. Select Public
                public_radio = await page.wait_for_selector("tp-yt-paper-radio-button[name='PUBLIC']", timeout=10000)
                if public_radio:
                    await public_radio.click()

                # Get the generated video link if present
                video_url = None
                link_el = await page.query_selector("a.ytcp-video-info, a.ytcp-upload-video-info")
                if link_el:
                    video_url = await link_el.get_attribute("href")

                # 8. Click Publish / Done
                done_btn = await page.wait_for_selector("#done-button", timeout=15000)
                if done_btn:
                    await done_btn.click()
                    await page.wait_for_timeout(5000)

                await context.close()
                return {
                    "success": True,
                    "post_url": video_url or "https://studio.youtube.com",
                    "error": None
                }

        except Exception as e:
            return {"success": False, "error": f"YouTube upload failed: {str(e)}"}
