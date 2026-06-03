"""Token-based auth for the Monarch MCP server (use this if you sign in with Google).

If you log into Monarch via "Sign in with Google" you have no Monarch password,
so the normal `auth_setup.py` (email + password) can't work. Instead, grab the
auth TOKEN from a browser session where you're already logged in, and this script
writes it straight into the session file the server uses.

HOW TO GET YOUR TOKEN (Chrome/Edge/Firefox):
  1. Log into Monarch in your browser as usual (Google sign-in is fine).
  2. Open DevTools (F12) -> Network tab.
  3. Click around Monarch so it loads data; filter requests for "graphql".
  4. Click any graphql request -> Headers -> Request Headers.
  5. Find:  Authorization: Token abc123def456...
     Copy ONLY the part after "Token " (the abc123def456... string).

Then run:
    .\\.venv\\Scripts\\python.exe token_setup.py

Paste the token at the prompt (it won't be shown on screen). The token grants
full account access -- treat it like a password. It is stored only in the local,
gitignored session file; it is never printed or committed.
"""
import asyncio
import getpass
import os

from monarchmoney import MonarchMoney

from config import SESSION_FILE


async def main() -> None:
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)

    # Allow MONARCH_TOKEN env var for non-interactive use; otherwise prompt
    # with getpass so the token is never echoed to the terminal.
    token = os.environ.get("MONARCH_TOKEN") or getpass.getpass(
        "Paste your Monarch token (input hidden): "
    ).strip()
    if not token:
        raise SystemExit("No token provided. Aborting.")

    mm = MonarchMoney(session_file=SESSION_FILE, token=token)
    mm.save_session(SESSION_FILE)

    # Confirm the token actually works by making one real read.
    accounts = await mm.get_accounts()
    n = len(accounts.get("accounts", []))
    print(f"\nSuccess. Session saved to {SESSION_FILE}")
    print(f"Token is valid -- found {n} account(s). You're ready to run the MCP server.")


if __name__ == "__main__":
    asyncio.run(main())
