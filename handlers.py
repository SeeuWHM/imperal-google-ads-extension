"""Google Ads · Account management handlers.

Functions: connect, status, setup_account, switch_account, disconnect.
"""
from __future__ import annotations

from urllib.parse import urlencode

from pydantic import BaseModel, Field
from typing import Optional

from app import chat, ActionResult, _get_ready_account, _no_account_error
from gads_providers.helpers import (
    _all_accounts,
    _active_account,
    COLLECTION,
    GADS_AUTH_URL,
    GADS_CLIENT_ID,
    GADS_REDIRECT_URI,
    GADS_SCOPE,
    _oauth_state,
)
from gads_providers.gads_client import list_customers, get_account_info


# ─── Models ───────────────────────────────────────────────────────────────── #

class SetupAccountParams(BaseModel):
    """Select a Google Ads account after OAuth authorisation."""
    customer_id: str = Field(
        default="",
        description=(
            "Google Ads customer ID to activate (10-digit numeric, e.g. 2631317705). "
            "Omit to list all available accounts."
        ),
    )


class AccountParams(BaseModel):
    """Target a specific account by ID or name."""
    account: str = Field(
        description="Customer ID (numeric) or account name."
    )


# ─── connect ──────────────────────────────────────────────────────────────── #

@chat.function(
    "connect",
    action_type="write",
    description=(
        "Connect a Google Ads account via OAuth. "
        "Checks if already connected first. Returns an authorisation URL."
    ),
)
async def fn_connect(ctx) -> ActionResult:
    accounts = await _all_accounts(ctx)

    # Already fully connected
    ready = [a for a in accounts if a.get("customer_id") and not a.get("_needs_reauth")]
    if ready:
        active = next((a for a in ready if a.get("is_active")), ready[0])
        return ActionResult.success(
            data={
                "already_connected": True,
                "account_name":      active.get("account_name", ""),
                "customer_id":       active.get("customer_id",  ""),
                "total_accounts":    len(ready),
            },
            summary=f"Already connected: {active.get('account_name', active.get('customer_id'))}",
        )

    # Tokens stored but account not selected yet
    pending = [a for a in accounts if a.get("_needs_setup")]
    if pending:
        return ActionResult.success(
            data={"needs_setup": True},
            summary="Authorised — say 'setup Google Ads account' to select your ad account.",
        )

    if not GADS_CLIENT_ID:
        return ActionResult.error(
            "Google Ads OAuth is not configured on this platform. "
            "Contact your administrator.",
            retryable=False,
        )

    url = GADS_AUTH_URL + "?" + urlencode({
        "client_id":     GADS_CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  GADS_REDIRECT_URI,
        "scope":         GADS_SCOPE,
        "access_type":   "offline",   # required for refresh_token
        "prompt":        "consent",   # force refresh_token even on re-auth
        "state":         _oauth_state(ctx),
    })
    return ActionResult.success(
        data={
            "auth_url":    url,
            "instruction": "Open the link and sign in with your Google account to grant access.",
        },
        summary="Google Ads OAuth URL ready — open it to authorise access.",
    )


# ─── status ───────────────────────────────────────────────────────────────── #

@chat.function(
    "status",
    action_type="read",
    description="Show all connected Google Ads accounts and today's summary stats.",
)
async def fn_status(ctx) -> ActionResult:
    accounts = await _all_accounts(ctx)
    if not accounts:
        return ActionResult.success(
            data={"connected": False, "accounts": [], "total": 0},
            summary="No Google Ads account connected.",
        )

    skeleton_data = await ctx.skeleton.get("gads_account") or {}
    today = skeleton_data.get("today", {})

    result = [
        {
            "customer_id":        a.get("customer_id",        ""),
            "account_name":       a.get("account_name",       ""),
            "currency":           a.get("currency",           ""),
            "is_active":          a.get("is_active",          False),
            "_needs_setup":       a.get("_needs_setup",       False),
            "_needs_reauth":      a.get("_needs_reauth",      False),
        }
        for a in accounts
    ]
    return ActionResult.success(
        data={
            "connected": True,
            "accounts":  result,
            "total":     len(result),
            "today":     today,
        },
        summary=f"{len(result)} Google Ads account(s) connected.",
    )


# ─── setup_account ────────────────────────────────────────────────────────── #

@chat.function(
    "setup_account",
    action_type="write",
    event="account_connected",
    description=(
        "After OAuth, discover accessible Google Ads accounts and activate one. "
        "Call this after 'connect' to complete setup. "
        "If customer_id is unknown, call without it to list all available accounts."
    ),
)
async def fn_setup_account(ctx, params: SetupAccountParams) -> ActionResult:
    accounts = await _all_accounts(ctx)
    pending  = next((a for a in accounts if a.get("_needs_setup")), None)
    if not pending:
        return ActionResult.error(
            "No pending authorisation found. "
            "Say 'connect Google Ads' first.",
            retryable=False,
        )

    access_token = pending.get("access_token", "")
    customers    = await list_customers(ctx, access_token)

    if not customers:
        return ActionResult.error(
            "No Google Ads accounts found for this Google account. "
            "Ensure you have access to at least one Google Ads account.",
            retryable=False,
        )

    # No customer_id given — list all and ask user to specify
    if not params.customer_id:
        return ActionResult.success(
            data={"available_accounts": customers, "needs_selection": True},
            summary=f"Found {len(customers)} account(s). Specify customer_id to activate.",
        )

    # Find the target account in the discovered list
    target = next(
        (c for c in customers
         if str(c.get("customer_id", "")).replace("-", "") == params.customer_id.replace("-", "")),
        None,
    )
    if not target:
        available = [f"{c.get('descriptive_name', 'Unknown')} ({c['customer_id']})" for c in customers]
        return ActionResult.error(
            f"Account {params.customer_id!r} not found. "
            f"Available: {', '.join(available)}",
            retryable=False,
        )

    # Check if the account is a manager (MCC) — if so, need sub-account selection
    if target.get("is_manager"):
        # For MCC accounts, list their sub-accounts
        # The user should pick a sub-account, not the MCC itself
        non_manager = [c for c in customers if not c.get("is_manager")]
        if non_manager:
            return ActionResult.success(
                data={
                    "mcc_selected": True,
                    "mcc_id": target["customer_id"],
                    "available_accounts": non_manager,
                    "needs_selection": True,
                },
                summary=(
                    f"'{target.get('descriptive_name', target['customer_id'])}' is a manager account. "
                    f"Please select one of the {len(non_manager)} sub-account(s) to activate."
                ),
            )

    # Determine manager_customer_id — if target is not a manager, find the MCC
    manager_customer_id = None
    for c in customers:
        if c.get("is_manager") and c["customer_id"] != target["customer_id"]:
            manager_customer_id = c["customer_id"]
            break

    await ctx.store.update(COLLECTION, pending["doc_id"], {
        **{k: v for k, v in pending.items() if k != "doc_id"},
        "customer_id":         str(target["customer_id"]).replace("-", ""),
        "manager_customer_id": str(manager_customer_id).replace("-", "") if manager_customer_id else None,
        "account_name":        target.get("descriptive_name") or target["customer_id"],
        "currency":            target.get("currency_code", "USD"),
        "is_active":           True,
        "_needs_setup":        False,
    })
    return ActionResult.success(
        data={
            "customer_id":          target["customer_id"],
            "account_name":         target.get("descriptive_name", ""),
            "currency":             target.get("currency_code", "USD"),
            "manager_customer_id":  manager_customer_id,
            "available_accounts":   customers,
        },
        summary=f"Google Ads account '{target.get('descriptive_name', target['customer_id'])}' activated.",
    )


# ─── switch_account ───────────────────────────────────────────────────────── #

@chat.function(
    "switch_account",
    action_type="write",
    event="account_switched",
    description="Switch the active Google Ads account.",
)
async def fn_switch_account(ctx, params: AccountParams) -> ActionResult:
    page = await ctx.store.query(COLLECTION)
    if not page.data:
        return _no_account_error()

    target = next(
        (d for d in page.data
         if d.id == params.account
         or d.data.get("customer_id") == params.account
         or d.data.get("account_name") == params.account),
        None,
    )
    if not target:
        available = [d.data.get("account_name", d.data.get("customer_id")) for d in page.data]
        return ActionResult.error(
            f"Account not found. Available: {available}", retryable=False
        )

    for d in page.data:
        is_target = d.id == target.id
        if d.data.get("is_active") != is_target:
            await ctx.store.update(
                COLLECTION, d.id,
                {**d.data, "is_active": is_target},
            )

    return ActionResult.success(
        data={
            "switched":     True,
            "customer_id":  target.data.get("customer_id"),
            "account_name": target.data.get("account_name"),
        },
        summary=f"Switched to {target.data.get('account_name', target.data.get('customer_id'))}.",
    )


# ─── disconnect ───────────────────────────────────────────────────────────── #

@chat.function(
    "disconnect",
    action_type="destructive",
    event="account_disconnected",
    description="Remove a connected Google Ads account and revoke its tokens.",
)
async def fn_disconnect(ctx, params: AccountParams) -> ActionResult:
    page = await ctx.store.query(COLLECTION)
    target = next(
        (d for d in page.data
         if d.id == params.account
         or d.data.get("customer_id") == params.account
         or d.data.get("account_name") == params.account),
        None,
    )
    if not target:
        return ActionResult.error("Account not found.", retryable=False)

    await ctx.store.delete(COLLECTION, target.id)
    return ActionResult.success(
        data={
            "disconnected": True,
            "customer_id":  target.data.get("customer_id", ""),
            "account_name": target.data.get("account_name", ""),
            "remaining":    len(page.data) - 1,
        },
        summary=f"Disconnected {target.data.get('account_name', target.data.get('customer_id'))}.",
    )
