# Monarch MCP

A local [Model Context Protocol](https://modelcontextprotocol.io) server that gives Claude **read + categorize** access to your [Monarch](https://www.monarch.com) finances — Monarch is the personal financial tracking and management tool — so Claude can see accounts, transactions, budgets and cashflow, and recategorize / tag / annotate transactions. **It never moves money** (no transfers, no account open/close, no deletes).

Built to run entirely on your machine, with **no official API** and **no third-party package trusted with your account** (see [How it works](#how-it-works)).

---

## What you can do

**Read + categorize only. No money movement.**

| Tool | What it does |
|---|---|
| `list_accounts` | Accounts, balances, institutions, rough net worth |
| `get_transactions` | Transactions with date / search / category / account / tag filters |
| `get_spending_summary` | Income / expense aggregates |
| `get_cashflow` | Cashflow grouped by category over a date range |
| `list_categories` | Categories + IDs (needed to recategorize) |
| `list_tags` | Tags + IDs |
| `update_transaction` | Set category, add notes, hide from reports, clear needs-review |
| `set_transaction_tags` | Overwrite a transaction's tags |
| `set_budget_amount` | Set a monthly budget for a category / group |
| `get_budgets` | ⚠️ Not yet implemented (see [Known limitations](#known-limitations)) |

9 of 10 tools are live. Reads + categorize work fully.

---

## How it works

Monarch has **no official public API**. This server talks to Monarch's private GraphQL backend (`api.monarch.com/graphql`) the same way the web app does. Two deliberate design choices, learned the hard way:

- **Our own client, not a library.** The popular community library (`hammem/monarchmoney`) is abandoned (last release 0.1.15) and its queries are stale — Monarch now returns `HTTP 400`. The maintained forks would fix the queries, but installing one means running unaudited third-party code *with full access to your financial account*. We refused that risk. Instead this repo ships [`monarch_client.py`](monarch_client.py): ~150 lines of raw `aiohttp` + hand-written GraphQL queries that request only the fields the tools need. You can read every line.
- **Browser-cookie auth.** Monarch's web app authenticates with a **session cookie**. The old token-login endpoint is heavily rate-limited (`HTTP 429`) and is **unavailable to Google/Apple SSO accounts** (they have no password). So the primary, universal auth path is to replay your existing browser session — no password, no rate limit, works for everyone.

---

## Security — read this

- Your Monarch **session = full account access.** It's stored only in `.mm/` on your machine, which is gitignored. **Never commit or share it**, and don't paste it into chats or issues.
- **Don't log out of Monarch** while using this — that invalidates the session cookie the server depends on. (Just re-capture if it expires.)
- Nothing is sent anywhere except Monarch's own API. No telemetry, no third-party services.

---

## Setup (~5 minutes)

### 1. Clone and install

**Python 3.10+ required** — check with `python --version`.

```bash
git clone https://github.com/Steadro/monarch-mcp.git
cd monarch-mcp
python -m venv .venv
# Windows:
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# macOS/Linux:
# ./.venv/bin/python -m pip install -r requirements.txt
```

A venv keeps these dependencies out of your global Python. Requires Python 3.10+.

### 2. Authenticate (choose ONE)

**Option A — Browser cookie (recommended; works for everyone, including Google/Apple sign-in).**

1. Log into Monarch in your browser.
2. Open DevTools (`F12`) → **Network** tab, type `graphql` in the filter, and click around the app so a request appears (status `200`).
3. Right-click any `graphql` request → **Copy** → **Copy as cURL** (bash *or* cmd — both are handled).
4. Create the `.mm/` folder if it doesn't exist (`mkdir .mm`), paste the cURL into a new file `.mm/request.curl`, then run:

   ```bash
   # Windows:
   .\.venv\Scripts\python.exe auth_from_curl.py
   ```

   It replays your browser's headers, verifies against your account, saves `.mm/mm_auth.json` (gitignored), and deletes the raw cURL. If it prints "found N account(s)," you're set.

**Option B — Email + password (only if you have a Monarch password — i.e. you did *not* sign up with Google/Apple).**

```bash
.\.venv\Scripts\python.exe auth_setup.py
```

Prompts for email, password, and an MFA code if 2FA is on. (Optional: set `MONARCH_MFA_SECRET` to skip MFA prompts on re-login.) If you get `HTTP 429`, you've been rate-limited — wait it out, or use Option A.

> SSO users: you *can* instead add a password in Monarch (Settings → Security → create a password) and then use Option B — but Option A is simpler and avoids the rate limit.

### 3. Register with your Claude client

**Claude Code / cowork** (run in the repo directory):

```bash
claude mcp add monarch-money -- /absolute/path/to/.venv/Scripts/python.exe /absolute/path/to/server.py
```

**Claude Desktop** — Settings → Developer → Edit Config, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "monarch-money": {
      "command": "/absolute/path/to/monarch-mcp/.venv/Scripts/python.exe",
      "args": ["/absolute/path/to/monarch-mcp/server.py"]
    }
  }
}
```

Use absolute paths. On Windows, escape backslashes in JSON (`C:\\path\\to\\...`) or use forward slashes. Pointing `command` at the venv interpreter avoids any PATH dependency.

### 4. Restart and test

**Restart your Claude client** (MCP servers load their code at startup — after any code change you must restart for it to take effect). Then ask: *"What's my net worth, and what did I spend on dining last month?"*

Quick local sanity check without Claude:

```bash
.\.venv\Scripts\python.exe -c "import asyncio, json, server; print(json.loads(asyncio.run(server.list_accounts()))['count'], 'accounts')"
```

---

## Auth expiry

Browser sessions expire sooner than password sessions. When reads start failing with auth errors, just redo **Option A** (capture a fresh `request.curl`, run `auth_from_curl.py`). The password session (`auth_setup.py`) lasts much longer — over a year — if you prefer Option B.

---

## Troubleshooting (things we hit, so you don't have to)

| Symptom | Cause & fix |
|---|---|
| `HTTP 429 Too Many Requests` on `auth_setup.py` | Monarch rate-limits the login endpoint after repeated attempts; resets in hours–days. **Stop retrying** (it resets the clock) and use **Option A** instead. |
| `401 Unauthorized` after capturing a cookie | Stale/expired session — recapture a fresh `request.curl`. Or you logged out of Monarch (don't). |
| `Client.execute_async() missing 1 required positional argument` | `gql` 4.0 incompatibility — `requirements.txt` pins `gql<4`; reinstall deps. |
| Tools return data in a direct test but fail in Claude | The MCP server process is running old code — **restart your Claude client**. |
| `Something went wrong while processing` (HTTP 400) | The old `monarchmoney` library's stale queries. This repo's `monarch_client.py` avoids them. |

---

## What's in here

| File | Purpose |
|---|---|
| `server.py` | The MCP server — defines the 10 tools and trims Monarch's payloads. |
| `monarch_client.py` | Self-contained Monarch API client (raw aiohttp + hand-written queries). |
| `auth_from_curl.py` | **Option A** auth — capture browser session from a copied cURL. |
| `auth_setup.py` | **Option B** auth — email/password login (caches a token). |
| `token_setup.py` | Advanced: write a raw API token directly to the session file. |
| `config.py` | File paths (`.mm/mm_auth.json`, `.mm/mm_session.pickle`), env-overridable. |
| `.env.example` | Documents optional env vars (no secrets). |

Secrets live in `.mm/` and are gitignored.

---

## Known limitations

- **`get_budgets` is not implemented** on the custom client yet — Monarch's budget query is large and nested. The other 9 tools work. PRs welcome.
- This is an **unofficial** integration. Monarch can change their private API at any time and break it; that's the trade-off. When a query breaks, it's usually a field rename — fixable in `monarch_client.py`.

## Disclaimer — use at your own risk

This is an independent, **unofficial** project. It is **not affiliated with, endorsed by, or supported by Monarch** in any way.

- It works by talking to Monarch's **private, undocumented API** using your own session. Monarch can change or block this at any time, and doing so may **break the tool without warning**.
- Using it may be against **Monarch's Terms of Service**. You are responsible for reviewing those terms and deciding whether to proceed.
- Your session grants **full access to your financial account**. You alone are responsible for safeguarding your credentials and the `.mm/` files, and for anything the tools do (including the categorize/budget *writes*).
- This software is provided **"AS IS", without warranty of any kind**, express or implied. The authors are **not liable** for any damages, data loss, account issues, or financial consequences arising from its use.

**By using this, you accept these risks.** If that's not acceptable, don't use it. When in doubt, use read-only and review every write before approving it.

## License

MIT — see [LICENSE](LICENSE). (The MIT license's "AS IS / no warranty" terms apply in addition to the disclaimer above.)
