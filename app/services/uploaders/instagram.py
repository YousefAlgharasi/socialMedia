import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import SESSIONS_DIR, BROWSER_EXECUTABLE
from app.services.uploaders.base import BaseUploader

class InstagramUploader(BaseUploader):
    def __init__(self):
        super().__init__("instagram")

    async def upload(self, video_path: str, title: str, description: str, tags: str = "") -> dict:
        profile_path = str(SESSIONS_DIR / "instagram")
        if not Path(video_path).exists():
            return {"success": False, "error": f"Video file not found at: {video_path}"}

        launch_kwargs = {
            "user_data_dir": profile_path,
            "headless": True,
            "viewport": {"width": 1366, "height": 900},
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

                # 1. Open Instagram
                await page.goto("https://www.instagram.com", wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(4000)

                if "accounts/login" in page.url:
                    await context.close()
                    return {"success": False, "error": "Not logged in to Instagram. Please connect your account first."}

                # 2. Create -> Post
                await page.locator("svg[aria-label='New post'], svg[aria-label='Create']").first.click(timeout=20000)
                await page.wait_for_timeout(1500)
                post_item = page.locator("a:has-text('Post'), div[role='menuitem']:has-text('Post'), span:text-is('Post')").first
                if await post_item.count():
                    await post_item.click(timeout=5000)
                    await page.wait_for_timeout(1500)

                # 3. Pick file
                async with page.expect_file_chooser(timeout=20000) as fc_info:
                    await page.locator("button:has-text('Select from computer'), button:has-text('Select From Computer')").first.click(timeout=15000)
                chooser = await fc_info.value
                await chooser.set_files(video_path)
                await page.wait_for_timeout(5000)

                # Dismiss 'Video posts are now shared as reels' dialog
                ok_btn = page.locator("button:has-text('OK')").first
                if await ok_btn.count():
                    await ok_btn.click()
                    await page.wait_for_timeout(1000)

                # 4/5. Next (crop) and Next (edit)
                for _ in range(2):
                    nxt = page.locator("div[role='button']:text-is('Next'), button:text-is('Next')").first
                    await nxt.click(timeout=30000)
                    await page.wait_for_timeout(2000)

                # 6. Caption
                caption = f"{title}\n\n{description}\n\n{tags}".strip()
                caption_area = page.locator("div[aria-label='Write a caption...'], div[role='textbox']").first
                await caption_area.click(timeout=15000)
                await page.keyboard.type(caption[:2000], delay=10)

                # 7. Share and wait for confirmation
                await page.locator("div[role='button']:text-is('Share'), button:text-is('Share')").first.click(timeout=15000)
                try:
                    await page.wait_for_selector("text=/shared|has been shared/i", timeout=180000)
                except Exception:
                    await page.screenshot(path=str(SESSIONS_DIR.parent / "instagram_last_share.png"))
                    await context.close()
                    return {"success": False, "error": "Clicked Share but Instagram never confirmed. See storage/instagram_last_share.png"}

                await context.close()
                return {
                    "success": True,
                    "post_url": "https://www.instagram.com",
                    "error": None
                }

        except Exception as e:
            return {"success": False, "error": f"Instagram upload failed: {type(e).__name__}: {e}"}
