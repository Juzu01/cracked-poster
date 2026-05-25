# cracked.st Thread Poster

Auto-post threads on cracked.st with BBCode formatting. Posts the same thread to multiple forums at once.

## Setup

1. Install dependencies:
```
pip install requests beautifulsoup4
```

2. Get your cookies:
   - Open cracked.st in Chrome and log in
   - F12 → Console → paste: `copy(document.cookie)` → Enter
   - Create `cookies.txt` next to `poster.py`, paste and save

3. Configure `poster.py` — open it and edit the config section at the top:
```python
# Forum IDs — find yours at cracked.st/forumdisplay.php?fid=XXX
FORUMS = ["123", "456"]

# Thread title
THREAD_TITLE = "Your Thread Title Here"

# BBCode template — {link} gets replaced with your link
THREAD_BODY_TEMPLATE = """[align=center][size=large]
[b]YOUR HEADING[/b]

[hide]
{link}
[/hide]

YOUR FOOTER
[/size][/align]"""

# Your link
POST_LINK = "https://your-link-here.com"
```

## Usage

```bash
py poster.py --dry-run     # preview what would be posted
py poster.py               # post to all configured forums
py poster.py --link "..."  # override the link
```

## How it works

1. Reads your cookies from `cookies.txt`
2. Checks you're logged in
3. Fetches the new thread form (grabs CSRF token)
4. Posts the thread to each forum with a 15s delay between them
5. Logs everything to `poster.log`
6. Shows a Windows toast notification when done

## BBCode Tips

| Tag | Effect |
|-----|--------|
| `[align=center]...[/align]` | Center text |
| `[size=large]...[/size]` | Large font |
| `[b]...[/b]` | Bold |
| `[hide]...[/hide]` | Hidden content (requires like/reply to see) |
| `[url=...]...[/url]` | Hyperlink |
| `[img]...[/img]` | Image |

## Files

| File | Description |
|------|-------------|
| `poster.py` | Main script |
| `cookies.txt` | Your cracked.st cookies (create this) |
| `poster.log` | Auto-generated log |

## Notes

- Cookies expire — if you get "NOT logged in", re-copy them from DevTools
- If a post fails, check `last_post_XXX.html` for the error page
- The 15s delay between forums avoids flood detection
