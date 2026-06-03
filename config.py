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
