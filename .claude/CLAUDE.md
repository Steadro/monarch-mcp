# monarch-mcp — project rules

Local MCP server (FastMCP) exposing Monarch Money to Claude. Read + categorize only,
no money movement. Built on the unofficial async `monarchmoney` library.

## Push-on-functional-change workflow

This repo is published at github.com/Steadro/monarch-money-mcp. Keep the public
repo in sync with working local code.

After any **functional** change (tools in `server.py`, auth flow, `config.py`,
`requirements.txt`), before considering the task done:

1. Verify locally: `./.venv/Scripts/python.exe -c "import asyncio, server; print(len(asyncio.run(server.mcp.list_tools())))"` — must import clean and list the expected tool count.
2. `git status --short` and confirm no `.mm`/`.env`/`.pickle`/`.venv` files are staged.
3. Commit with a conventional-commit message (feat/fix/refactor/chore/docs).
4. Push to `origin main`.

Docs-only or comment-only tweaks: committing is enough; pushing is optional.

Note: `main` is the default branch. Pushing follows the user's global push policy
(confirm before pushing to main) unless the user has added a settings permission rule
to allow it automatically.

## Never commit

- The session token (`.mm/`, `*.pickle`), any real `.env`, or `.venv/`. All are
  gitignored — keep them that way. The token is full account access.
- Deps live in `.venv` (not global Python).
