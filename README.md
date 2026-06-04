# Monarch Money MCP Server

A personal [Model Context Protocol](https://modelcontextprotocol.io) server that lets Claude read and organize your [Monarch Money](https://www.monarchmoney.com) finances.

Monarch has no official public API, so this is built on the community [`monarchmoney`](https://github.com/hammem/monarchmoney) library, which talks to Monarch's private GraphQL backend. That means it's unofficial and could break if Monarch changes their API — that's the tradeoff for a fun build.

## Scope

**Read + categorize. No money movement.** The server can view your data and tidy up transactions/budgets, but it cannot transfer funds, open/close accounts, or delete anything.

| Tool | What it does |
|---|---|
| `list_accounts` | Accounts, balances, institutions, rough net worth |
| `get_transactions` | Transactions with date/search/category/account/tag filters |
| `get_spending_summary` | Income / expense / savings aggregates |
| `get_budgets` | Budgeted vs. actual by category |
| `get_cashflow` | Cashflow grouped by category over a date range |
| `list_categories` | Categories + IDs (needed for recategorizing) |
| `list_tags` | Tags + IDs |
| `update_transaction` | Set category, add notes, hide from reports, clear needs-review |
| `set_transaction_tags` | Overwrite a transaction's tags |
| `set_budget_amount` | Set a monthly budget for a category/group |

## Security — read this

Your Monarch **session token grants full account access**. After you log in once, it's saved to `.mm/mm_session.pickle` on this machine. The `.gitignore` already excludes it. Never commit it, never share it. Your password is never stored — only the resulting token.

## Setup

1. **Install dependencies** into an isolated venv (Python 3.10+):

   ```powershell
   cd monarch-mcp
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   (Using a venv keeps these deps from disturbing your global Python. On macOS/Linux the interpreter is `.venv/bin/python`.)

2. **Log in once** to cache a session token:

   ```powershell
   .\.venv\Scripts\python.exe auth_setup.py
   ```

   It prompts for your email, password, and an MFA code if you have 2FA on. On success it confirms how many accounts it found.

   *Optional:* to avoid typing MFA codes on future re-logins, grab your MFA secret from Monarch (Settings → Security → Enable MFA → "Two-factor text code") and set it as an env var: `MONARCH_MFA_SECRET=...`.

   **Sign in with Google/Apple, or hitting `HTTP 429 Too Many Requests`? Use browser-cookie auth instead** (recommended for SSO accounts — no password needed, and it never touches the rate-limited login endpoint):

   1. Log into Monarch in your browser. Open DevTools (F12) → **Network**, filter `graphql`, click around so a request appears.
   2. Right-click a `graphql` request → **Copy as cURL** (bash or cmd — both work).
   3. Paste it into `.mm/request.curl`, then run:

      ```powershell
      .\.venv\Scripts\python.exe auth_from_curl.py
      ```

   It replays your browser's headers, verifies against your account, saves `.mm/mm_auth.json` (gitignored), and deletes the raw cURL. Browser sessions expire sooner than the password login, so recapture if reads start failing.

   *(Why: SSO accounts have no password, and Monarch's web app authenticates with a session cookie — a different system than the `/auth/login/` token. This path uses that cookie directly. The server prefers `mm_auth.json` when present, else falls back to the `auth_setup.py` token session.)*

3. **Register with Claude Desktop.** Add this to your `claude_desktop_config.json`
   (Settings → Developer → Edit Config), adjusting the paths to match your machine:

   ```json
   {
     "mcpServers": {
       "monarch-money": {
         "command": "C:\\path\\to\\monarch-mcp\\.venv\\Scripts\\python.exe",
         "args": ["C:\\path\\to\\monarch-mcp\\server.py"]
       }
     }
   }
   ```

   Replace `C:\path\to\monarch-mcp` with the absolute path to where you cloned this repo. `command` points straight at the venv interpreter so Claude Desktop doesn't depend on your PATH. On macOS/Linux use `.venv/bin/python` and the POSIX path to `server.py`.

4. **Restart Claude Desktop.** You should see the `monarch-money` tools appear. Try: *"What's my net worth and what did I spend on dining last month?"*

## Notes

- **Auth expiry:** if tools start failing with auth errors, recapture (`auth_from_curl.py`) or re-login (`auth_setup.py`).
- **Custom client:** the upstream `monarchmoney` library (0.1.15) is abandoned and its queries are stale (Monarch returns HTTP 400). To avoid trusting an unaudited third-party fork with full account access, this repo ships its own minimal client (`monarch_client.py`) — raw `aiohttp` + hand-written queries requesting only the fields the tools use. `gql` is pinned `<4` (4.0 broke the transport).
- **Known gap:** `get_budgets` is not yet reimplemented on the custom client (its query is large); the other 9 tools are live. Reads + categorize work fully.
- All formatters trim Monarch's large GraphQL payloads to the useful fields so responses stay fast and cheap.
