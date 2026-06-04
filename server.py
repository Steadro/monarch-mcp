"""Monarch MCP server.

Exposes your Monarch financial data to Claude as MCP tools. Scope is
READ + CATEGORIZE: it can view accounts, transactions, budgets, cashflow,
categories and tags, and it can recategorize / tag / annotate transactions
and set budget amounts. It deliberately does NOT move money, open/close
accounts, or delete anything.

Auth (see README): capture your browser session once with `auth_from_curl.py`.
The server loads it from the gitignored .mm/mm_auth.json; it never sees a password.

Monarch has no official public API. Reads/writes go to its private GraphQL
backend via `monarch_client.py` -- our own hand-written client (raw aiohttp, no
third-party Monarch library trusted with your account).
"""
import json
import os
from datetime import date, timedelta
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from config import AUTH_FILE
from monarch_client import CookieClient

mcp = FastMCP("monarch-money")

# Single client, built lazily from the captured browser session on first use.
_mm: Optional[CookieClient] = None


def _client() -> CookieClient:
    global _mm
    if _mm is None:
        if not os.path.exists(AUTH_FILE):
            raise RuntimeError(
                f"No Monarch auth found at {AUTH_FILE}. Capture your browser session "
                "(see the README), then run `python auth_from_curl.py`."
            )
        with open(AUTH_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        _mm = CookieClient(saved.get("headers", {}))
    return _mm


def _dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str, ensure_ascii=False)


# ----------------------------------------------------------------------------
# Compact formatters — the raw GraphQL payloads are large and nested. We trim
# them to the fields that matter so responses stay token-efficient.
# ----------------------------------------------------------------------------
def _fmt_account(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "name": a.get("displayName"),
        "balance": a.get("displayBalance", a.get("currentBalance")),
        "type": (a.get("type") or {}).get("display") or (a.get("type") or {}).get("name"),
        "subtype": (a.get("subtype") or {}).get("display"),
        "institution": (a.get("institution") or {}).get("name"),
        "is_asset": a.get("isAsset"),
        "updated_at": a.get("displayLastUpdatedAt") or a.get("updatedAt"),
    }


def _fmt_txn(t: dict) -> dict:
    return {
        "id": t.get("id"),
        "date": t.get("date"),
        "amount": t.get("amount"),
        "merchant": (t.get("merchant") or {}).get("name") or t.get("plaidName"),
        "category": (t.get("category") or {}).get("name"),
        "category_id": (t.get("category") or {}).get("id"),
        "account": (t.get("account") or {}).get("displayName"),
        "tags": [tag.get("name") for tag in (t.get("tags") or [])],
        "notes": t.get("notes"),
        "pending": t.get("pending"),
        "needs_review": t.get("needsReview"),
    }


def _default_range(start_date: Optional[str], end_date: Optional[str], days: int = 30):
    if not end_date:
        end_date = date.today().isoformat()
    if not start_date:
        start_date = (date.today() - timedelta(days=days)).isoformat()
    return start_date, end_date


# ----------------------------------------------------------------------------
# READ tools
# ----------------------------------------------------------------------------
@mcp.tool()
async def list_accounts() -> str:
    """List all financial accounts with their current balances, types, and institutions."""
    data = await _client().get_accounts()
    accounts = [_fmt_account(a) for a in data.get("accounts", [])]
    net_worth = sum(
        (a["balance"] or 0) if a["is_asset"] else -(a["balance"] or 0)
        for a in accounts
        if isinstance(a["balance"], (int, float))
    )
    return _dumps({"net_worth_estimate": net_worth, "count": len(accounts), "accounts": accounts})


@mcp.tool()
async def get_transactions(
    limit: int = 50,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: str = "",
    category_ids: Optional[list[str]] = None,
    account_ids: Optional[list[str]] = None,
    tag_ids: Optional[list[str]] = None,
) -> str:
    """Get transactions, newest first. Dates are 'YYYY-MM-DD'. Optionally filter by
    free-text search, category IDs, account IDs, or tag IDs. Defaults to the last 50."""
    data = await _client().get_transactions(
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        search=search,
        category_ids=category_ids or [],
        account_ids=account_ids or [],
        tag_ids=tag_ids or [],
    )
    block = data.get("allTransactions", {})
    results = [_fmt_txn(t) for t in block.get("results", [])]
    return _dumps({"total_count": block.get("totalCount"), "returned": len(results), "transactions": results})


@mcp.tool()
async def get_spending_summary() -> str:
    """Get an aggregate summary of transactions (income, expense, savings totals)."""
    return _dumps(await _client().get_transactions_summary())


@mcp.tool()
async def get_budgets(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """Get budgeted vs. actual amounts by category. Dates are 'YYYY-MM-DD';
    defaults to the current budgeting window if omitted."""
    return _dumps(await _client().get_budgets(start_date=start_date, end_date=end_date))


@mcp.tool()
async def get_cashflow(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """Get cashflow grouped by category and category group over a date range.
    Dates are 'YYYY-MM-DD'; defaults to the last 30 days."""
    start_date, end_date = _default_range(start_date, end_date)
    return _dumps(await _client().get_cashflow(start_date=start_date, end_date=end_date))


@mcp.tool()
async def list_categories() -> str:
    """List all transaction categories with their IDs (needed to recategorize transactions or set budgets)."""
    data = await _client().get_transaction_categories()
    cats = [
        {
            "id": c.get("id"),
            "name": c.get("name"),
            "group": (c.get("group") or {}).get("name"),
        }
        for c in data.get("categories", [])
    ]
    return _dumps({"count": len(cats), "categories": cats})


@mcp.tool()
async def list_tags() -> str:
    """List all transaction tags with their IDs (needed to tag transactions)."""
    data = await _client().get_transaction_tags()
    tags = [
        {"id": t.get("id"), "name": t.get("name")}
        for t in data.get("householdTransactionTags", [])
    ]
    return _dumps({"count": len(tags), "tags": tags})


# ----------------------------------------------------------------------------
# CATEGORIZE / WRITE tools (no money movement)
# ----------------------------------------------------------------------------
@mcp.tool()
async def update_transaction(
    transaction_id: str,
    category_id: Optional[str] = None,
    notes: Optional[str] = None,
    hide_from_reports: Optional[bool] = None,
    needs_review: Optional[bool] = None,
) -> str:
    """Update a transaction: set its category (use list_categories for IDs), add notes,
    hide it from reports, or clear its needs-review flag. Only the fields you pass change.

    NOTE: This tool intentionally does NOT expose a transaction's amount or date. The
    underlying client can change them, but they are deliberately withheld here to keep the
    tool categorize-only. Do not add amount/date parameters without a deliberate review."""
    result = await _client().update_transaction(
        transaction_id=transaction_id,
        category_id=category_id,
        notes=notes,
        hide_from_reports=hide_from_reports,
        needs_review=needs_review,
    )
    return _dumps(result)


@mcp.tool()
async def set_transaction_tags(transaction_id: str, tag_ids: list[str]) -> str:
    """Set the tags on a transaction (use list_tags for IDs). This OVERWRITES existing
    tags; pass an empty list to remove all tags."""
    return _dumps(await _client().set_transaction_tags(transaction_id, tag_ids))


@mcp.tool()
async def set_budget_amount(
    amount: float,
    category_id: Optional[str] = None,
    category_group_id: Optional[str] = None,
    start_date: Optional[str] = None,
    apply_to_future: bool = False,
) -> str:
    """Set the monthly budget amount for a category (or category group). Provide exactly
    one of category_id / category_group_id. start_date ('YYYY-MM-DD') picks the month;
    set apply_to_future=True to roll the amount forward to later months too."""
    if bool(category_id) == bool(category_group_id):
        return _dumps({"error": "Provide exactly one of category_id or category_group_id."})
    return _dumps(
        await _client().set_budget_amount(
            amount=amount,
            category_id=category_id,
            category_group_id=category_group_id,
            start_date=start_date,
            apply_to_future=apply_to_future,
        )
    )


if __name__ == "__main__":
    mcp.run()
