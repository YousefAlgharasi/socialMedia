import os
import json
import base64
import sqlite3
import shutil
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

def dpapi_decrypt(encrypted_data: bytes) -> Optional[bytes]:
    p_data_in = DATA_BLOB(len(encrypted_data), ctypes.cast(ctypes.create_string_buffer(encrypted_data), ctypes.POINTER(ctypes.c_char)))
    p_data_out = DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(p_data_in), None, None, None, None, 0, ctypes.byref(p_data_out)):
        decrypted = ctypes.string_at(p_data_out.pbData, p_data_out.cbData)
        ctypes.windll.kernel32.LocalFree(p_data_out.pbData)
        return decrypted
    return None

def decrypt_cookie_value(encrypted_bytes: bytes, key: bytes, strip_hash: bool = False) -> Optional[str]:
    """Returns decrypted cookie value, or None if it cannot be decrypted (e.g. v20 app-bound)."""
    try:
        prefix = encrypted_bytes[:3]
        if prefix in (b'v10', b'v11'):
            nonce = encrypted_bytes[3:15]
            ciphertext = encrypted_bytes[15:]
            raw = AESGCM(key).decrypt(nonce, ciphertext, None)
        elif prefix == b'v20':
            return None  # Chrome/Edge app-bound encryption: cannot be decrypted by user-level code
        else:
            raw = dpapi_decrypt(encrypted_bytes)
            if raw is None:
                return None
        # Chromium DB version >= 24 prepends a 32-byte SHA256 of the host to the plaintext
        if strip_hash:
            raw = raw[32:]
        return raw.decode('utf-8', errors='ignore')
    except Exception:
        return None

def get_browser_user_data_paths() -> List[Tuple[str, Path]]:
    """Returns candidate (name, Chromium user data directory) pairs."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return []

    candidates = [
        ("Brave", Path(local_app_data) / "BraveSoftware" / "Brave-Browser" / "User Data"),
        ("Chrome", Path(local_app_data) / "Google" / "Chrome" / "User Data"),
        ("Edge", Path(local_app_data) / "Microsoft" / "Edge" / "User Data"),
    ]
    return [(n, p) for n, p in candidates if p.exists()]

PLATFORM_DOMAIN_PATTERNS = {
    "youtube": ["%google%", "%youtube%"],
    "tiktok": ["%tiktok%"],
    "instagram": ["%instagram%"],
    "facebook": ["%facebook%"]
}

# Cookie names that prove the user is really signed in
AUTH_COOKIES = {
    "youtube": {"SID", "SAPISID", "__Secure-1PSID"},
    "tiktok": {"sessionid", "sessionid_ss", "sid_tt"},
    "instagram": {"sessionid"},
    "facebook": {"c_user", "xs"},
}

def _chromium_time_to_unix(expires_utc: int) -> float:
    if not expires_utc:
        return -1
    return expires_utc / 1_000_000 - 11644473600

def _shared_copy(src: Path, dst: Path) -> bool:
    """Copy a file another process has open, using Windows share-all flags."""
    import msvcrt
    GENERIC_READ = 0x80000000
    SHARE_ALL = 0x1 | 0x2 | 0x4
    OPEN_EXISTING = 3
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = ctypes.c_void_p
    handle = k32.CreateFileW(str(src), GENERIC_READ, SHARE_ALL, None, OPEN_EXISTING, 0x80, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        return False
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
        with os.fdopen(fd, "rb") as fsrc, open(dst, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst)
        return True
    except Exception:
        return False

def _copy_db(cookies_db: Path, temp_db: Path) -> bool:
    try:
        shutil.copy2(cookies_db, temp_db)
        return True
    except Exception:
        return _shared_copy(cookies_db, temp_db)

def has_auth_cookie(platform: str, cookies: List[Dict[str, Any]]) -> bool:
    wanted = AUTH_COOKIES.get(platform, set())
    return any(c["name"] in wanted and c["value"] for c in cookies)

def extract_cookies_with_report(platform: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Extracts cookies for the platform from installed Chromium browsers (Brave/Chrome/Edge).
    Prefers the browser profile that actually contains a signed-in session.
    Returns (playwright_cookies, report).
    """
    report = {"browsers_checked": [], "locked": [], "undecryptable": 0, "found_any": False}
    patterns = PLATFORM_DOMAIN_PATTERNS.get(platform, [])
    if not patterns:
        return [], report

    best_without_auth: List[Dict[str, Any]] = []

    for browser_name, user_data_dir in get_browser_user_data_paths():
        report["browsers_checked"].append(browser_name)
        local_state_file = user_data_dir / "Local State"
        if not local_state_file.exists():
            continue

        try:
            local_state = json.loads(local_state_file.read_text(encoding="utf-8"))
            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
            master_key = dpapi_decrypt(encrypted_key)
            if not master_key:
                continue
        except Exception:
            continue

        profile_folders = [user_data_dir / "Default"] + list(user_data_dir.glob("Profile *"))
        for profile in profile_folders:
            cookies_db = profile / "Network" / "Cookies"
            if not cookies_db.exists():
                cookies_db = profile / "Cookies"
            if not cookies_db.exists():
                continue

            temp_db = profile / "temp_extract_cookies.db"
            if not _copy_db(cookies_db, temp_db):
                report["locked"].append(browser_name)
                continue

            profile_cookies: List[Dict[str, Any]] = []
            try:
                conn = sqlite3.connect(str(temp_db))
                cursor = conn.cursor()

                strip_hash = False
                try:
                    cursor.execute("SELECT value FROM meta WHERE key='version'")
                    row = cursor.fetchone()
                    strip_hash = bool(row and int(row[0]) >= 24)
                except Exception:
                    pass

                where_clauses = " OR ".join(["host_key LIKE ?" for _ in patterns])
                cursor.execute(f"""
                    SELECT host_key, name, path, encrypted_value, is_secure, is_httponly, samesite, expires_utc
                    FROM cookies
                    WHERE {where_clauses}
                """, patterns)

                for host_key, name, path, enc_val, is_secure, is_httponly, samesite, expires_utc in cursor.fetchall():
                    value = decrypt_cookie_value(enc_val, master_key, strip_hash)
                    if value is None:
                        report["undecryptable"] += 1
                        continue
                    if not value:
                        continue

                    if samesite == 2:
                        samesite_str = "Strict"
                    elif samesite == 0 and is_secure:
                        samesite_str = "None"
                    else:
                        samesite_str = "Lax"

                    profile_cookies.append({
                        "name": name,
                        "value": value,
                        "domain": host_key,
                        "path": path or "/",
                        "expires": _chromium_time_to_unix(expires_utc),
                        "secure": bool(is_secure),
                        "httpOnly": bool(is_httponly),
                        "sameSite": samesite_str,
                    })
                conn.close()
            except Exception:
                pass
            finally:
                try:
                    temp_db.unlink()
                except Exception:
                    pass

            if profile_cookies:
                report["found_any"] = True
                if has_auth_cookie(platform, profile_cookies):
                    return profile_cookies, report
                if len(profile_cookies) > len(best_without_auth):
                    best_without_auth = profile_cookies

    return best_without_auth, report

def extract_cookies_for_platform(platform: str) -> List[Dict[str, Any]]:
    """Backward compatible wrapper returning only the cookie list."""
    return extract_cookies_with_report(platform)[0]
