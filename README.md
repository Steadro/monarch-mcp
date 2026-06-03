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

- The session can expire; if tools start failing with auth errors, re-run `python auth_setup.py`.
- The session file path can be relocated via the `MONARCH_SESSION_FILE` env var (see `config.py`).
- All formatters trim Monarch's large GraphQL payloads to the useful fields so responses stay fast and cheap.
