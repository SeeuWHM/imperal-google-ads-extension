"""Google Ads · HTTP client for whm-google-ads-control microservice.

All API calls go through this module. The microservice handles Google Ads API
gRPC complexity; this module is a thin async HTTP layer on top.

Multi-tenant: X-Gads-Access-Token + X-Gads-Customer-Id drive per-request
GoogleAdsClient creation inside the microservice. X-Gads-Login-Customer-Id
is required when the customer is a sub-account of an MCC manager.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from imperal_sdk import Context

from .helpers import GADS_API_URL, GADS_JWT
from .token_refresh import _refresh_token_if_needed

log = logging.getLogger("google-ads.client")


# ─── Request headers ──────────────────────────────────────────────────────── #

def _headers(acc: dict) -> dict:
    """Build request headers for a fully-configured account."""
    h = {
        "Authorization":      f"Bearer {GADS_JWT}",
        "X-Gads-Access-Token": acc["access_token"],
        "X-Gads-Customer-Id":  str(acc["customer_id"]),
    }
    # Include MCC login header only when present — standalone accounts don't need it
    if acc.get("manager_customer_id"):
        h["X-Gads-Login-Customer-Id"] = str(acc["manager_customer_id"])
    return h


def _discovery_headers(access_token: str) -> dict:
    """Headers for account discovery — no customer_id yet."""
    return {
        "Authorization":      f"Bearer {GADS_JWT}",
        "X-Gads-Access-Token": access_token,
        # CustomerService.list_accessible_customers uses customer_id from token itself
        "X-Gads-Customer-Id":  "0",  # placeholder; microservice overrides for list_customers
    }


# ─── Internal HTTP helpers ────────────────────────────────────────────────── #

async def _get(ctx: Context, acc: dict, path: str, **params) -> Any:
    acc = await _refresh_token_if_needed(ctx, acc)
    r = await ctx.http.get(
        f"{GADS_API_URL}{path}",
        headers=_headers(acc),
        params={k: v for k, v in params.items() if v is not None},
    )
    r.raise_for_status()
    return r.json()


async def _post(ctx: Context, acc: dict, path: str, body: dict) -> Any:
    acc = await _refresh_token_if_needed(ctx, acc)
    r = await ctx.http.post(
        f"{GADS_API_URL}{path}",
        headers=_headers(acc),
        json=body,
    )
    r.raise_for_status()
    return r.json()


async def _patch(ctx: Context, acc: dict, path: str, body: dict) -> Any:
    acc = await _refresh_token_if_needed(ctx, acc)
    r = await ctx.http.patch(
        f"{GADS_API_URL}{path}",
        headers=_headers(acc),
        json=body,
    )
    r.raise_for_status()
    return r.json()


async def _delete(ctx: Context, acc: dict, path: str, body: Optional[dict] = None) -> Any:
    acc = await _refresh_token_if_needed(ctx, acc)
    kwargs: dict = {"headers": _headers(acc)}
    if body is not None:
        kwargs["json"] = body
    r = await ctx.http.delete(f"{GADS_API_URL}{path}", **kwargs)
    r.raise_for_status()
    # DELETE endpoints may return empty body
    try:
        return r.json()
    except Exception:
        return {}


# ─── Auth / discovery ─────────────────────────────────────────────────────── #

async def list_customers(ctx: Context, access_token: str) -> list[dict]:
    """Discover all Google Ads accounts accessible with this access_token.
    Called by setup_account() before customer_id is known.
    Returns list of {customer_id, customer_id_formatted, descriptive_name,
                      currency_code, time_zone, is_manager}.
    """
    r = await ctx.http.get(
        f"{GADS_API_URL}/v1/auth/customers",
        headers=_discovery_headers(access_token),
    )
    if r.status_code == 200:
        return r.json().get("customers", [])
    log.warning("list_customers: %s %s", r.status_code, r.text[:200])
    return []


# ─── Account ──────────────────────────────────────────────────────────────── #

async def get_account_info(ctx: Context, acc: dict) -> dict:
    return await _get(ctx, acc, "/v1/account")


# ─── Campaigns ────────────────────────────────────────────────────────────── #

async def get_campaigns(ctx: Context, acc: dict, status: str = "") -> dict:
    return await _get(ctx, acc, "/v1/campaigns",
                      **{"status": status} if status else {})


async def get_campaign(ctx: Context, acc: dict, campaign_id: str) -> dict:
    return await _get(ctx, acc, f"/v1/campaigns/{campaign_id}")


async def create_campaign(ctx: Context, acc: dict, data: dict) -> dict:
    return await _post(ctx, acc, "/v1/campaigns", data)


async def update_campaign(ctx: Context, acc: dict, campaign_id: str, data: dict) -> dict:
    return await _patch(ctx, acc, f"/v1/campaigns/{campaign_id}", data)


async def pause_campaign(ctx: Context, acc: dict, campaign_id: str) -> dict:
    return await _post(ctx, acc, f"/v1/campaigns/{campaign_id}/pause", {})


async def enable_campaign(ctx: Context, acc: dict, campaign_id: str) -> dict:
    return await _post(ctx, acc, f"/v1/campaigns/{campaign_id}/enable", {})


# ─── Budgets ──────────────────────────────────────────────────────────────── #

async def get_budgets(ctx: Context, acc: dict) -> dict:
    return await _get(ctx, acc, "/v1/budgets")


async def create_budget(ctx: Context, acc: dict, data: dict) -> dict:
    return await _post(ctx, acc, "/v1/budgets", data)


# ─── Ad Groups ────────────────────────────────────────────────────────────── #

async def get_ad_groups(ctx: Context, acc: dict, campaign_id: str) -> dict:
    return await _get(ctx, acc, "/v1/ad-groups", campaign_id=campaign_id)


async def create_ad_group(ctx: Context, acc: dict, data: dict) -> dict:
    return await _post(ctx, acc, "/v1/ad-groups", data)


# ─── Ads ──────────────────────────────────────────────────────────────────── #

async def get_ads(ctx: Context, acc: dict, ad_group_id: str) -> dict:
    return await _get(ctx, acc, "/v1/ads", ad_group_id=ad_group_id)


async def create_ad(ctx: Context, acc: dict, data: dict) -> dict:
    return await _post(ctx, acc, "/v1/ads", data)


async def update_ad(ctx: Context, acc: dict, ad_id: str, ad_group_id: str, data: dict) -> dict:
    return await _patch(ctx, acc, f"/v1/ads/{ad_id}",
                        {**data, "ad_group_id": ad_group_id})


# ─── Keywords ─────────────────────────────────────────────────────────────── #

async def get_keywords(ctx: Context, acc: dict, ad_group_id: str) -> dict:
    return await _get(ctx, acc, "/v1/keywords", ad_group_id=ad_group_id)


async def add_keywords(ctx: Context, acc: dict, data: dict) -> dict:
    return await _post(ctx, acc, "/v1/keywords", data)


# ─── Reports ──────────────────────────────────────────────────────────────── #

async def get_performance(
    ctx: Context,
    acc: dict,
    level: str,
    date_preset: str = "LAST_30_DAYS",
    campaign_ids: Optional[str] = None,
) -> dict:
    return await _get(
        ctx, acc,
        "/v1/reports/performance",
        level=level,
        date_preset=date_preset,
        campaign_ids=campaign_ids,
    )


async def get_search_terms(
    ctx: Context,
    acc: dict,
    date_preset: str = "LAST_30_DAYS",
    campaign_ids: Optional[str] = None,
) -> dict:
    return await _get(
        ctx, acc,
        "/v1/reports/search-terms",
        date_preset=date_preset,
        campaign_ids=campaign_ids,
    )


# ─── Keyword Planner (Basic Access returns 429) ───────────────────────────── #

async def _planner_post(ctx: Context, acc: dict, endpoint: str, data: dict) -> dict:
    """POST to keyword planner endpoints with graceful 429 handling."""
    acc = await _refresh_token_if_needed(ctx, acc)
    r = await ctx.http.post(
        f"{GADS_API_URL}{endpoint}",
        headers=_headers(acc),
        json=data,
    )
    if r.status_code == 429:
        return {"error": "429_standard_access_required"}
    r.raise_for_status()
    return r.json()


async def keyword_ideas(ctx: Context, acc: dict, data: dict) -> dict:
    """Returns dict with 'ideas' list OR {'error': '429_standard_access_required'}."""
    return await _planner_post(ctx, acc, "/v1/keyword-planner/ideas", data)


async def keyword_metrics(ctx: Context, acc: dict, data: dict) -> dict:
    """Historical metrics for specific keywords. Returns {'metrics': [...]} or 429 error."""
    return await _planner_post(ctx, acc, "/v1/keyword-planner/metrics", data)
