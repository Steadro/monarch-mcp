"""Shared config for the Monarch MCP server.

The session file holds your Monarch auth token. Treat it like a password:
it grants full access to your account. It lives on this machine only and is
gitignored. By default it sits next to this file in ./.mm/mm_session.pickle,
but you can override the location with the MONARCH_SESSION_FILE env var.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SESSION_FILE = os.environ.get(
    "MONARCH_SESSION_FILE",
    os.path.join(BASE_DIR, ".mm", "mm_session.pickle"),
)

# Cookie/header auth (for SSO accounts or when the login endpoint is rate-limited).
# Holds a captured set of browser request headers (incl. the session cookie) so the
# server can talk to Monarch's GraphQL API without ever calling /auth/login/.
AUTH_FILE = os.environ.get(
    "MONARCH_AUTH_FILE",
    os.path.join(BASE_DIR, ".mm", "mm_auth.json"),
)
