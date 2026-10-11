import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import SESSIONS_DIR, PLATFORM_URLS, BROWSER_EXECUTABLE, BROWSER_NAME

class SessionManager:
    """Manages persistent browser profiles and interactive login flows using the user's browser (Brave)."""

    def __init__(self):
        self.active_login_processes = {}

    def get_profile_path(self, platform: str) -> Path:
        path = SESSIONS_DIR / platform
        path.mkdir(parents=True, exist_ok=True)
        return path

    def clear_stale_locks(self, platform: str):
        """Removes lockfiles left behind if browser was closed abruptly."""
        profile_path = self.get_profile_path(platform)
        lock_files = ["lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"]
        for lock in lock_files:
            target = profile_path / lock
            if target.exists():
                try:
                    if target.is_dir():
                        import shutil
                        shutil.rmtree(target, ignore_errors=True)
                    else:
                        target.unlink(missing_ok=True)
                except Exception:
                    pass

    def launch_interactive_login_process(self, platform: str):
        """
        Spawns a visible, focused Brave browser window for the user to log in and solve 2FA.
        """
        profile_path = str(self.get_profile_path(platform))
        target_url = PLATFORM_URLS.get(platform, {}).get("login", "https://google.com")

        # Terminate any previously opened login process for this platform
        if platform in self.active_login_processes:
            try:
                proc = self.active_login_processes[platform]
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass

        self.clear_stale_locks(platform)
        browser_exe = BROWSER_EXECUTABLE or ""

        script = f"""import sys
import time
import threading
from playwright.sync_api import sync_playwright

def run():
    print("=" * 65)
    print("  OmniPost - Visual Login for {platform.upper()} in {BROWSER_NAME}")
    print("=" * 65)
    print("Opening your browser window now...")
    print("1. Log in to your account with your credentials.")
    print("2. Approve any 2-factor authentication prompts.")
    print("3. When you are finished, CLOSE the browser window.")
    print("   (Or press ENTER in this terminal to finish & save)")
    print("=" * 65)

    with sync_playwright() as p:
        launch_kwargs = {{
            "user_data_dir": r"{profile_path}",
            "headless": False,
            "viewport": None,
            "ignore_default_args": ["--enable-automation"],
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized"
            ]
        }}
        if r"{browser_exe}":
            launch_kwargs["executable_path"] = r"{browser_exe}"
        else:
            launch_kwargs["channel"] = "msedge"

        try:
            context = p.chromium.launch_persistent_context(**launch_kwargs)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("{target_url}")

            # Keep window open until all pages are closed or user presses Enter
            stop_event = threading.Event()

            def listen_enter():
                try:
                    input()
                    stop_event.set()
                except Exception:
                    pass

            t = threading.Thread(target=listen_enter, daemon=True)
            t.start()

            while not stop_event.is_set():
                time.sleep(1)
                try:
                    if not context.pages or all(p.is_closed() for p in context.pages):
                        break
                except Exception:
                    break

            context.close()
            print("\\n[SUCCESS] Session saved permanently! You can now close this window.")
            time.sleep(2)
        except Exception as e:
            print(f"\\n[ERROR] {{e}}")
            input("Press Enter to exit...")

if __name__ == "__main__":
    run()
"""
        temp_script_path = SESSIONS_DIR / f"login_{platform}.py"
        temp_script_path.write_text(script, encoding="utf-8")

        # Windows: launch in its own interactive console window so it pops up in front of user
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_CONSOLE

        proc = subprocess.Popen(
            [sys.executable, str(temp_script_path)],
            creationflags=creation_flags
        )
        self.active_login_processes[platform] = proc
        return {"status": "launched", "pid": proc.pid, "browser": BROWSER_NAME}

    async def verify_session(self, platform: str) -> dict:
        """
        Launches headless browser using the saved profile to check if the session is authenticated.
        """
        profile_path = str(self.get_profile_path(platform))
        self.clear_stale_locks(platform)
        
        is_logged_in = False
        account_name = "Connected"
        details = ""

        launch_kwargs = {
            "user_data_dir": profile_path,
            "headless": True,
            "ignore_default_args": ["--enable-automation"],
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

                if platform == "youtube":
                    await page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(3000)
                    current_url = page.url
                    if "accounts.google.com" not in current_url and "studio.youtube.com" in current_url:
                        is_logged_in = True
                        try:
                            channel_el = await page.query_selector("#channel-title, #entity-name")
                            if channel_el:
                                text = await channel_el.text_content()
                                if text:
                                    account_name = text.strip()
                        except Exception:
                            pass
                    else:
                        details = "Redirected to Google sign-in"

                elif platform == "tiktok":
                    await page.goto("https://www.tiktok.com/creator-center/upload", wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(3000)
                    current_url = page.url
                    if "login" not in current_url:
                        is_logged_in = True
                        account_name = "TikTok Creator"
                    else:
                        details = "Redirected to TikTok login"

                elif platform == "instagram":
                    await page.goto("https://www.instagram.com", wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(3000)
                    current_url = page.url
                    if "accounts/login" not in current_url:
                        is_logged_in = True
                        account_name = "Instagram Account"
                    else:
                        details = "Redirected to Instagram login"

                elif platform == "facebook":
                    await page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(3000)
                    current_url = page.url
                    if "login" not in current_url and "recover" not in current_url:
                        is_logged_in = True
                        account_name = "Facebook Account"
                    else:
                        details = "Redirected to Facebook login"

                await context.close()

        except Exception as e:
            is_logged_in = False
            details = f"Verification error: {str(e)}"

        return {
            "platform": platform,
            "is_connected": is_logged_in,
            "account_name": account_name if is_logged_in else "Not Connected",
            "details": details
        }

    def _launch_kwargs(self, platform: str) -> dict:
        kwargs = {
            "user_data_dir": str(self.get_profile_path(platform)),
            "headless": True,
            "ignore_default_args": ["--enable-automation"],
            "args": ["--disable-blink-features=AutomationControlled"]
        }
        if BROWSER_EXECUTABLE:
            kwargs["executable_path"] = BROWSER_EXECUTABLE
        else:
            kwargs["channel"] = "msedge"
        return kwargs

    def import_cookies_and_verify(self, platform: str, close_browser: bool = False) -> dict:
        """
        Copies the user's existing signed-in cookies from Brave/Chrome/Edge into this app's
        persistent profile, then confirms a real session exists. Blocking: call from a thread.
        """
        from playwright.sync_api import sync_playwright
        from app.services.cookie_extractor import extract_cookies_with_report, has_auth_cookie

        cookies, report = extract_cookies_with_report(platform)
        if report["locked"] and not has_auth_cookie(platform, cookies) and close_browser:
            exe_names = {"Brave": "brave.exe", "Chrome": "chrome.exe", "Edge": "msedge.exe"}
            for b in set(report["locked"]):
                subprocess.run(["taskkill", "/F", "/IM", exe_names.get(b, "brave.exe")],
                               capture_output=True)
            time.sleep(2.5)
            cookies, report = extract_cookies_with_report(platform)
            if BROWSER_EXECUTABLE:
                try:
                    subprocess.Popen([BROWSER_EXECUTABLE, "--restore-last-session"])
                except Exception:
                    pass

        if not cookies or not has_auth_cookie(platform, cookies):
            needs_close = bool(report["locked"])
            if needs_close:
                msg = (f"{', '.join(sorted(set(report['locked'])))} is open and locks its cookie file. "
                       "It must be closed once to import your login.")
            elif report["undecryptable"]:
                msg = ("Your browser uses protected cookie encryption that can't be read. "
                       "Use 'Login Window' once instead - it is remembered permanently.")
            else:
                msg = (f"No signed-in {platform.capitalize()} session found in your browsers "
                       f"({', '.join(report['browsers_checked']) or 'none detected'}). "
                       "Log in there first or use 'Login Window'.")
            return {"platform": platform, "is_connected": False, "account_name": "Not Connected",
                    "details": msg, "needs_browser_closed": needs_close,
                    "locked_browsers": sorted(set(report["locked"]))}

        self.clear_stale_locks(platform)
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(**self._launch_kwargs(platform))
                try:
                    valid = []
                    for c in cookies:
                        try:
                            context.add_cookies([c])
                            valid.append(c)
                        except Exception:
                            continue
                    result = self._check_context(context, platform)
                    result["details"] = result["details"] or f"Imported {len(valid)} cookies"
                    return result
                finally:
                    context.close()
        except Exception as e:
            return {"platform": platform, "is_connected": False, "account_name": "Not Connected",
                    "details": f"Could not open app browser profile (close any open Login Window): {e}"}

    def check_session_sync(self, platform: str) -> dict:
        """Checks whether the app's saved profile is signed in. Blocking: call from a thread."""
        from playwright.sync_api import sync_playwright
        self.clear_stale_locks(platform)
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(**self._launch_kwargs(platform))
                try:
                    return self._check_context(context, platform)
                finally:
                    context.close()
        except Exception as e:
            return {"platform": platform, "is_connected": False, "account_name": "Not Connected",
                    "details": f"Verification error: {e}"}

    def _check_context(self, context, platform: str) -> dict:
        from app.services.cookie_extractor import has_auth_cookie
        url = {
            "tiktok": "https://www.tiktok.com/",
            "instagram": "https://www.instagram.com/",
            "facebook": "https://www.facebook.com/",
        }.get(platform, "https://www.google.com/")
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
        except Exception:
            pass
        cookies = context.cookies()
        logged_in = has_auth_cookie(platform, cookies)
        name = f"{platform.capitalize()} Account"
        extra = {}
        if logged_in and platform == "instagram":
            try:
                uid = next((c["value"] for c in cookies if c["name"] == "ds_user_id"), None)
                if uid:
                    resp = context.request.get(
                        f"https://i.instagram.com/api/v1/users/{uid}/info/",
                        headers={"X-IG-App-ID": "936619743392459", "Accept": "*/*"},
                        timeout=20000,
                    )
                    if resp.ok:
                        user = resp.json().get("user", {})
                        name = user.get("username") or name
                        extra = {
                            "avatar_url": user.get("profile_pic_url"),
                            "followers_count": str(user.get("follower_count", 0)),
                            "posts_count": str(user.get("media_count", 0)),
                            "views_count": "-",
                        }
            except Exception:
                pass
        return {
            "platform": platform,
            "is_connected": logged_in,
            "account_name": name if logged_in else "Not Connected",
            "details": "" if logged_in else "Session cookies were rejected (expired or logged out).",
            **extra,
        }

session_manager = SessionManager()
