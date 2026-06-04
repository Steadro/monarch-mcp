"""Capture browser auth for the Monarch MCP server (cookie/header replay).

Use this when you sign in with Google/Apple (no password) OR when the login
endpoint is rate-limiting you with HTTP 429. Instead of logging in via the API,
it replays your browser's own request headers (including the session cookie) so
the server talks to Monarch's GraphQL API exactly as your browser does --
no /auth/login/ call, so no rate limit.

HOW TO USE
  1. Log into Monarch in your browser (Google sign-in is fine).
  2. Open DevTools (F12) -> Network tab. Click around so data loads; filter "graphql".
  3. Right-click any `graphql` request (status 200) ->
        Firefox:  Copy Value -> Copy as cURL (POSIX / Linux)
        Chrome/Edge:  Copy -> Copy as cURL (bash)   (NOT "cmd")
  4. Paste it into a file at:  .mm/request.curl
  5. Run:  .\\.venv\\Scripts\\python.exe auth_from_curl.py

It tests the captured headers by fetching your accounts. On success it writes
.mm/mm_auth.json (gitignored) and deletes .mm/request.curl so the raw secrets
don't linger. These headers grant account access -- treat the .mm folder like a
password store. Nothing is printed or committed.

NOTE: browser sessions expire sooner than API tokens. If reads start failing
later, just recapture (repeat the steps above).
"""
import asyncio
import json
import os
import shlex

from config import AUTH_FILE

CURL_FILE = os.path.join(os.path.dirname(AUTH_FILE), "request.curl")

# Connection-management headers we must NOT replay (aiohttp sets these itself;
# replaying them breaks the request). Everything else from the browser is kept,
# which preserves the cookie, User-Agent, and the sec-ch-* fingerprint Cloudflare
# checks.
_DROP = {"host", "content-length", "connection", "accept-encoding"}


def _parse_curl(text: str) -> dict:
    """Pull headers (and -b/--cookie) out of a copied cURL command.

    Handles all three copy formats DevTools produces:
      - bash / POSIX  (curl '...'  with \\ line continuations)
      - Windows cmd   (curl.exe ^"...^"  with ^ line continuations and ^" escaping)
    """
    # 1. Join line continuations: cmd uses trailing ^, POSIX uses trailing \.
    text = text.replace("^\r\n", " ").replace("^\n", " ")
    text = text.replace("\\\r\n", " ").replace("\\\n", " ")
    # 2. Undo cmd caret-escaping. These sequences don't occur in POSIX copies,
    #    so running them unconditionally is a no-op there.
    text = text.replace('^"', '"').replace("^%", "%").replace("^^", "^")
    tokens = shlex.split(text, posix=True)

    headers: dict[str, str] = {}
    it = iter(tokens)
    for tok in it:
        if tok in ("-H", "--header"):
            raw = next(it, "")
            if ":" in raw:
                key, val = raw.split(":", 1)
                headers[key.strip()] = val.strip()
        elif tok in ("-b", "--cookie"):
            headers["Cookie"] = next(it, "").strip()
        elif tok.startswith("-H") and ":" in tok:  # e.g. -H'Key: Value'
            raw = tok[2:].strip()
            key, val = raw.split(":", 1)
            headers[key.strip()] = val.strip()

    # Drop connection-management headers; keep auth + fingerprint headers.
    cleaned = {k: v for k, v in headers.items() if k.lower() not in _DROP}
    return cleaned


async def main() -> None:
    if not os.path.exists(CURL_FILE):
        raise SystemExit(
            f"No cURL file found at {CURL_FILE}.\n"
            "Copy a Monarch `graphql` request from DevTools as cURL (bash/POSIX) "
            "and paste it into that file, then re-run."
        )

    with open(CURL_FILE, encoding="utf-8") as f:
        headers = _parse_curl(f.read())

    if not any(k.lower() == "cookie" for k in headers):
        raise SystemExit("No Cookie header found in the cURL. Re-copy the request (it must be a logged-in graphql call).")

    from monarch_client import CookieClient

    mm = CookieClient(headers)

    # Test: does this auth actually work?
    accounts = await mm.get_accounts()
    n = len(accounts.get("accounts", []))

    os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump({"headers": headers}, f, indent=2)
    # Restrict to owner-only (meaningful on macOS/Linux; harmless on Windows).
    # This file holds your session cookie -- treat it like a password.
    try:
        os.chmod(AUTH_FILE, 0o600)
    except OSError:
        pass

    # Remove the raw cURL (full of secrets) now that we've extracted what we need.
    try:
        os.remove(CURL_FILE)
    except OSError:
        pass

    print(f"\nSuccess. Browser auth works -- found {n} account(s).")
    print(f"Saved headers to {AUTH_FILE} (gitignored). Deleted {os.path.basename(CURL_FILE)}.")
    print("You're ready to run the MCP server. (Recapture if reads start failing later.)")


if __name__ == "__main__":
    asyncio.run(main())
