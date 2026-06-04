"""Self-contained Monarch client (browser-cookie auth, hand-written queries).

Why this exists instead of the `monarchmoney` library:
  - hammem/monarchmoney 0.1.15 is abandoned; its queries are stale and Monarch
    rejects them (HTTP 400).
  - We deliberately avoid third-party forks: this client runs with full access to
    your Monarch session, so we keep it to code in THIS repo that you can read.

It talks to api.monarch.com/graphql directly with aiohttp, authenticating via the
browser session cookie (through aiohttp's cookie jar) plus the replayed browser
headers. Queries request only the fields our MCP tools actually use, which keeps
them resilient to unrelated schema churn. Returns the same dict shapes the old
library did, so server.py's formatters are unchanged.
"""
import json
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

GRAPHQL_URL = "https://api.monarch.com/graphql"

# Headers aiohttp/the request layer must set itself; cookie goes via the jar.
_DROP = {"host", "content-length", "connection", "accept-encoding", "content-type", "cookie"}

# --- Queries (minimal field sets) -------------------------------------------
Q_ACCOUNTS = """
query GetAccounts {
  accounts {
    id displayName currentBalance displayBalance isAsset
    updatedAt displayLastUpdatedAt
    type { name display }
    subtype { name display }
    institution { name }
  }
}
"""

Q_TRANSACTIONS = """
query GetTransactionsList($offset: Int, $limit: Int, $filters: TransactionFilterInput) {
  allTransactions(filters: $filters) {
    totalCount
    results(offset: $offset, limit: $limit) {
      id amount pending date hideFromReports notes needsReview plaidName
      category { id name }
      merchant { id name }
      account { id displayName }
      tags { id name }
    }
  }
}
"""

Q_CATEGORIES = """
query GetCategories {
  categories { id name group { id name } }
}
"""

Q_TAGS = """
query GetHouseholdTransactionTags {
  householdTransactionTags { id name }
}
"""

Q_SUMMARY = """
query GetTransactionsPage($filters: TransactionFilterInput) {
  aggregates(filters: $filters) {
    summary { count sumIncome sumExpense first last }
  }
}
"""

Q_CASHFLOW = """
query Web_GetCashFlowPage($filters: TransactionFilterInput) {
  byCategory: aggregates(filters: $filters, groupBy: ["category"]) {
    groupBy { category { id name } }
    summary { sumIncome sumExpense }
  }
  byCategoryGroup: aggregates(filters: $filters, groupBy: ["categoryGroup"]) {
    groupBy { categoryGroup { id name } }
    summary { sumIncome sumExpense }
  }
}
"""

Q_BUDGETS = """
query GetJointPlanningData($startDate: Date!, $endDate: Date!) {
  budgetData(startMonth: $startDate, endMonth: $endDate) {
    monthlyAmountsByCategory {
      category { id name }
      monthlyAmounts { month plannedCashFlowAmount actualAmount remainingAmount }
    }
  }
}
"""

M_UPDATE_TXN = """
mutation Web_TransactionDrawerUpdateTransaction($input: UpdateTransactionMutationInput!) {
  updateTransaction(input: $input) {
    transaction { id category { id name } notes hideFromReports needsReview }
    errors { message }
  }
}
"""

M_SET_TAGS = """
mutation Web_SetTransactionTags($input: SetTransactionTagsInput!) {
  setTransactionTags(input: $input) {
    transaction { id tags { id name } }
    errors { message }
  }
}
"""

M_SET_BUDGET = """
mutation Common_UpdateBudgetItem($input: UpdateOrCreateBudgetItemMutationInput!) {
  updateOrCreateBudgetItem(input: $input) {
    budgetItem { id budgetAmount }
  }
}
"""


def _split_cookie(cookie_str: str) -> Dict[str, str]:
    jar: Dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            jar[k.strip()] = v.strip()
    return jar


class CookieClient:
    """Monarch API client authed by a captured browser session."""

    def __init__(self, headers: Dict[str, str], timeout: int = 30):
        cookie_str = next((v for k, v in headers.items() if k.lower() == "cookie"), "")
        self._cookies = _split_cookie(cookie_str)
        self._headers = {k: v for k, v in headers.items() if k.lower() not in _DROP}
        self._timeout = timeout

    async def _call(self, operation: str, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = {"operationName": operation, "variables": variables or {}, "query": query}
        async with aiohttp.ClientSession(cookies=self._cookies) as session:
            async with session.post(
                GRAPHQL_URL, json=body, headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"Monarch HTTP {resp.status}: {text[:300]}")
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Monarch returned non-JSON response: {text[:300]}") from e
                if payload.get("errors"):
                    raise RuntimeError(f"Monarch GraphQL error: {payload['errors']}")
                return payload.get("data", {})

    # --- Reads --------------------------------------------------------------
    async def get_accounts(self) -> Dict[str, Any]:
        return await self._call("GetAccounts", Q_ACCOUNTS)

    async def get_transactions(
        self, limit: int = 100, offset: int = 0,
        start_date: Optional[str] = None, end_date: Optional[str] = None,
        search: str = "", category_ids: Optional[List[str]] = None,
        account_ids: Optional[List[str]] = None, tag_ids: Optional[List[str]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        if search:
            filters["search"] = search
        if category_ids:
            filters["categories"] = category_ids
        if account_ids:
            filters["accounts"] = account_ids
        if tag_ids:
            filters["tags"] = tag_ids
        if start_date:
            filters["startDate"] = start_date
        if end_date:
            filters["endDate"] = end_date
        return await self._call(
            "GetTransactionsList", Q_TRANSACTIONS,
            {"limit": limit, "offset": offset, "filters": filters},
        )

    async def get_transaction_categories(self) -> Dict[str, Any]:
        return await self._call("GetCategories", Q_CATEGORIES)

    async def get_transaction_tags(self) -> Dict[str, Any]:
        return await self._call("GetHouseholdTransactionTags", Q_TAGS)

    async def get_transactions_summary(self) -> Dict[str, Any]:
        return await self._call("GetTransactionsPage", Q_SUMMARY, {"filters": {}})

    async def get_cashflow(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None, **_: Any
    ) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        if start_date:
            filters["startDate"] = start_date
        if end_date:
            filters["endDate"] = end_date
        return await self._call("Web_GetCashFlowPage", Q_CASHFLOW, {"filters": filters})

    async def get_budgets(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None, **_: Any
    ) -> Dict[str, Any]:
        # Monarch's budgetData takes first-of-month dates. Default to the current month.
        first = date.today().replace(day=1)
        start_date = start_date or first.isoformat()
        end_date = end_date or (first + timedelta(days=32)).replace(day=1).isoformat()
        data = await self._call(
            "GetJointPlanningData", Q_BUDGETS,
            {"startDate": start_date, "endDate": end_date},
        )
        bd = data.get("budgetData") or {}
        out = []
        for row in bd.get("monthlyAmountsByCategory", []):
            cat = row.get("category") or {}
            out.append({
                "category_id": cat.get("id"),
                "category": cat.get("name"),
                "months": [
                    {
                        "month": m.get("month"),
                        "planned": m.get("plannedCashFlowAmount"),
                        "actual": m.get("actualAmount"),
                        "remaining": m.get("remainingAmount"),
                    }
                    for m in (row.get("monthlyAmounts") or [])
                ],
            })
        return {"start_date": start_date, "end_date": end_date, "budgets_by_category": out}

    # --- Writes (categorize only; no money movement) ------------------------
    async def update_transaction(
        self, transaction_id: str, category_id: Optional[str] = None,
        hide_from_reports: Optional[bool] = None, needs_review: Optional[bool] = None,
        notes: Optional[str] = None, **_: Any,
    ) -> Dict[str, Any]:
        # Categorize-only BY DESIGN: amount / date / merchant are intentionally not
        # accepted, so no code path through this client can alter a transaction's value.
        # Do not add them back without a deliberate scope review.
        inp: Dict[str, Any] = {"id": transaction_id}
        if category_id is not None:
            inp["category"] = category_id
        if hide_from_reports is not None:
            inp["hideFromReports"] = bool(hide_from_reports)
        if needs_review is not None:
            inp["needsReview"] = bool(needs_review)
        if notes is not None:
            inp["notes"] = notes
        return await self._call("Web_TransactionDrawerUpdateTransaction", M_UPDATE_TXN, {"input": inp})

    async def set_transaction_tags(self, transaction_id: str, tag_ids: List[str]) -> Dict[str, Any]:
        return await self._call(
            "Web_SetTransactionTags", M_SET_TAGS,
            {"input": {"transactionId": transaction_id, "tagIds": tag_ids}},
        )

    async def set_budget_amount(
        self, amount: float, category_id: Optional[str] = None,
        category_group_id: Optional[str] = None, timeframe: str = "month",
        start_date: Optional[str] = None, apply_to_future: bool = False, **_: Any,
    ) -> Dict[str, Any]:
        if start_date is None:
            start_date = date.today().replace(day=1).isoformat()
        inp = {
            "startDate": start_date,
            "timeframe": timeframe,
            "categoryId": category_id,
            "categoryGroupId": category_group_id,
            "amount": amount,
            "applyToFuture": apply_to_future,
        }
        return await self._call("Common_UpdateBudgetItem", M_SET_BUDGET, {"input": inp})
