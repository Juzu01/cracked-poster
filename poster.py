"""
cracked.st thread poster
-------------------------
Auto-post threads on cracked.st with BBCode formatting.
Supports posting the same thread to multiple forums at once.

Requires:
  - cookies.txt (from cracked.st — same as bumper)

USAGE:
    py poster.py --dry-run     # show what would be posted, don't post
    py poster.py               # post to all configured forums
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://cracked.st"
COOKIES_FILE = Path(__file__).parent / "cookies.txt"
LOG_FILE = Path(__file__).parent / "poster.log"

# ===== CONFIGURE THESE =====

# Forum IDs to post to. Find yours at: cracked.st/forumdisplay.php?fid=XXX
FORUMS = ["YOUR_FID_1", "YOUR_FID_2"]

# Thread title
THREAD_TITLE = "Your Thread Title Here"

# Thread body in BBCode. Use {link} as placeholder for your link/content.
# Example with centered text, large font, and [hide] tag:
THREAD_BODY_TEMPLATE = """[align=center][size=large]
[b]YOUR HEADING HERE[/b]

[hide]
{link}
[/hide]

YOUR FOOTER TEXT HERE
[/size][/align]"""

# The link or content to put inside {link} placeholder
POST_LINK = "https://your-link-here.com"

# ===========================

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def notify(title: str, message: str) -> None:
    t = title.replace("'", "''")
    m = message.replace("'", "''")
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, "
        "Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "[Windows.Data.Xml.Dom.XmlDocument, "
        "Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null;"
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        f"$xml.LoadXml('<toast><visual><binding template=\"ToastGeneric\">"
        f"<text>{t}</text><text>{m}</text></binding></visual></toast>');"
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);"
        "[Windows.UI.Notifications.ToastNotificationManager]"
        "::CreateToastNotifier('CrackedPoster').Show($toast);"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            timeout=10, capture_output=True,
        )
    except Exception:
        pass


def parse_cookies_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise SystemExit(
            f"!! Missing {path.name}.\n"
            "Copy cookies from cracked.st:\n"
            "  F12 -> Console -> copy(document.cookie)\n"
            "  Paste into cookies.txt"
        )
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise SystemExit("!! cookies.txt is empty.")

    cookies: dict[str, str] = {}
    if ";" in raw and "\n" not in raw.strip():
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies[parts[5]] = parts[6]
                continue
            if len(parts) >= 2:
                cookies[parts[0]] = parts[1]
                continue
        m = re.match(r"(\S+)\s+(\S+)", line)
        if m:
            name, val = m.group(1), m.group(2)
            if name.lower() in {"name", "cookie"}:
                continue
            cookies[name] = val
            continue
        if "=" in line:
            for part in line.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookies[k.strip()] = v.strip()

    if not cookies:
        raise SystemExit("!! Could not parse cookies.txt.")
    return cookies


def make_session(cookies: dict[str, str], ua: str) -> requests.Session:
    s = requests.Session()
    for k, v in cookies.items():
        s.cookies.set(k, v, domain=".cracked.st")
    s.headers.update({
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": BASE + "/",
        "Sec-Ch-Ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    })
    return s


def check_logged_in(s: requests.Session) -> str | None:
    r = s.get(BASE + "/", timeout=20)
    if r.status_code != 200:
        log(f"GET / returned {r.status_code}")
        return None
    m = re.search(r"Welcome back,?\s*<[^>]+>([^<]+)<", r.text)
    if m:
        return m.group(1).strip()
    if "member.php?action=login" in r.text.lower():
        return None
    return "(logged in)"


def build_post_body(link: str) -> str:
    return THREAD_BODY_TEMPLATE.format(link=link)


def get_newthread_form(s: requests.Session, fid: str) -> dict:
    url = f"{BASE}/newthread.php?fid={fid}"
    log(f"Fetching form fid={fid}")
    r = s.get(url, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"GET newthread fid={fid} returned {r.status_code}")

    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.find("form", {"method": "post"})
    if not form:
        if "no permission" in r.text.lower() or "not have permission" in r.text.lower():
            raise RuntimeError(f"No permission to post on fid={fid}")
        (Path(__file__).parent / f"last_newthread_{fid}.html").write_text(r.text, encoding="utf-8")
        raise RuntimeError(f"Form not found fid={fid}. Check last_newthread_{fid}.html")

    hidden = {}
    for inp in form.find_all("input", {"type": "hidden"}):
        name = inp.get("name")
        if name:
            hidden[name] = inp.get("value", "")

    my_post_key = hidden.get("my_post_key", "")
    if not my_post_key:
        m = re.search(r'my_post_key\s*=\s*["\']([a-f0-9]+)["\']', r.text)
        if m:
            my_post_key = m.group(1)
    if not my_post_key:
        raise RuntimeError("my_post_key not found. Cookies expired?")

    return {"my_post_key": my_post_key, "hidden": hidden}


def post_thread(s: requests.Session, fid: str, title: str, message: str, form_data: dict) -> str | None:
    url = f"{BASE}/newthread.php?fid={fid}&processed=1"
    data = {
        "my_post_key": form_data["my_post_key"],
        "subject": title,
        "message": message,
        "action": "do_newthread",
        "fid": fid,
        "posthash": form_data["hidden"].get("posthash", ""),
        "tid": "",
        "submit": "Post Thread",
    }
    for k, v in form_data["hidden"].items():
        if k not in data:
            data[k] = v

    log(f"Posting to fid={fid}...")
    r = s.post(url, data=data, timeout=30, allow_redirects=True, headers={
        "Referer": f"{BASE}/newthread.php?fid={fid}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": BASE,
    })

    # Success: redirect to thread OR thread page in response
    if "showthread.php" in r.url:
        log(f"OK fid={fid}: {r.url}")
        return r.url

    # MyBB sometimes doesn't redirect but returns the thread page
    tid_match = re.search(r'showthread\.php\?tid=(\d+)', r.text)
    if tid_match:
        thread_url = f"{BASE}/showthread.php?tid={tid_match.group(1)}"
        log(f"OK fid={fid}: {thread_url}")
        return thread_url

    body = r.text.lower()
    if "error" in body or "you cannot" in body:
        soup = BeautifulSoup(r.text, "html.parser")
        err = soup.find("div", class_="error")
        if err:
            log(f"!! Error fid={fid}: {err.get_text(strip=True)[:200]}")
        (Path(__file__).parent / f"last_post_{fid}.html").write_text(r.text, encoding="utf-8")
        return None

    (Path(__file__).parent / f"last_post_{fid}.html").write_text(r.text, encoding="utf-8")
    log(f"!! Unknown result fid={fid}. Status: {r.status_code}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="cracked.st thread poster")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be posted, don't post")
    ap.add_argument("--link", default=POST_LINK, help="Link to put in the post")
    ap.add_argument("--cookies", default=str(COOKIES_FILE))
    ap.add_argument("--ua", default=DEFAULT_UA)
    args = ap.parse_args()

    if "YOUR_FID" in FORUMS[0]:
        raise SystemExit(
            "!! You need to configure poster.py first.\n"
            "Open poster.py and set:\n"
            "  FORUMS = [\"123\", \"456\"]     # your forum IDs\n"
            "  THREAD_TITLE = \"...\"          # your thread title\n"
            "  THREAD_BODY_TEMPLATE = \"...\"  # your BBCode template\n"
            "  POST_LINK = \"...\"             # your link"
        )

    log("=" * 60)
    log("cracked.st poster start")

    # 1. Cookies
    cookies = parse_cookies_file(Path(args.cookies))
    log(f"{len(cookies)} cookies loaded")
    s = make_session(cookies, args.ua)

    user = check_logged_in(s)
    if not user:
        log("!! NOT logged in. Refresh cookies.txt")
        return 1
    log(f"Logged in as: {user}")

    # 2. Build post
    post_body = build_post_body(args.link)

    if args.dry_run:
        log("--- DRY RUN ---")
        log(f"Title: {THREAD_TITLE}")
        log(f"Link: {args.link}")
        log(f"Forums: {', '.join(FORUMS)}")
        log(f"Post:\n{post_body}")
        log("--- nothing posted ---")
        return 0

    # 3. Post to all forums
    posted = 0
    for i, fid in enumerate(FORUMS):
        if i > 0:
            log("Waiting 15s...")
            time.sleep(15)

        try:
            form_data = get_newthread_form(s, fid)
            url = post_thread(s, fid, THREAD_TITLE, post_body, form_data)
            if url:
                posted += 1
            else:
                log(f"!! fid={fid} not posted")
        except Exception as e:
            log(f"!! fid={fid} error: {e}")

    log("=" * 60)
    log(f"DONE. Posted: {posted}/{len(FORUMS)}")
    notify("CrackedPoster", f"Posted: {posted}/{len(FORUMS)}")
    return 0 if posted == len(FORUMS) else 1


if __name__ == "__main__":
    sys.exit(main())
