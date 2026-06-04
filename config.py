"""Shared config for the Monarch MCP server.

`AUTH_FILE` holds your captured browser request headers, including the Monarch
session cookie. Treat it like a password: it grants full access to your account.
It lives on this machine only and is gitignored. By default it sits next to this
file at ./.mm/mm_auth.json; override the location with the MONARCH_AUTH_FILE env var.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Browser-cookie auth: a captured set of request headers (incl. the session cookie)
# so the server talks to Monarch's GraphQL API as your browser does -- no login endpoint.
AUTH_FILE = os.environ.get(
    "MONARCH_AUTH_FILE",
    os.path.join(BASE_DIR, ".mm", "mm_auth.json"),
)
