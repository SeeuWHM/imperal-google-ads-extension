"""Google Ads · Ad group and ad handlers.

Functions: list_ad_groups, create_ad_group, list_ads, create_ad, update_ad.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app import chat, ActionResult, _get_ready_account
import gads_providers.gads_client as api


# ─── Models ───────────────────────────────────────────────────────────────── #

class AdGroupListParams(BaseModel):
    campaign_id: str = Field(description="Campaign ID to list ad groups for")


class CreateAdGroupParams(BaseModel):
    """Create a new ad group within a campaign."""
    campaign_id: str = Field(description="Parent campaign ID")
    name:        str = Field(description="Ad group name")
    cpc_bid:     Optional[float] = Field(
        default=None,
        description=(
            "Max CPC bid in account currency. "
            "Used for MANUAL_CPC campaigns. For Smart Bidding campaigns, "
            "this is the ad group default bid (may be ignored by Google's bidding algorithm)."
        ),
    )
    status: Literal["ENABLED", "PAUSED"] = Field(
        default="PAUSED",
        description="Initial status. Start PAUSED to review ads before activating.",
    )


class AdGroupIdParams(BaseModel):
    ad_group_id: str = Field(description="Ad group ID")


class CreateAdParams(BaseModel):
    """Create a Responsive Search Ad (RSA) in an ad group."""
    ad_group_id: str = Field(description="Ad group ID to create the ad in")
    final_urls:  list[str] = Field(
        description="Landing page URL(s). First URL is the primary destination."
    )
    headlines: list[str] = Field(
        description=(
            "3–15 headlines. Each headline max 30 characters. "
            "Google automatically tests combinations to find best-performing variants. "
            "Example: ['Managed Web Hosting', 'Fast PHP Hosting', 'WordPress Hosting']"
        )
    )
    descriptions: list[str] = Field(
        description=(
            "2–4 descriptions. Each description max 90 characters. "
            "Provide diverse messages covering different benefits. "
            "Example: ['NVMe + LiteSpeed. 14-day free trial.', 'Fast, secure, managed hosting.']"
        )
    )
    path1: Optional[str] = Field(
        default=None,
        description="Display URL path 1 (max 15 chars, e.g. 'managed'). Shown as site.com/path1/path2",
    )
    path2: Optional[str] = Field(
        default=None,
        description="Display URL path 2 (max 15 chars, e.g. 'hosting'). Shown as site.com/path1/path2",
    )
    status: Literal["ENABLED", "PAUSED"] = Field(
        default="PAUSED",
        description="Initial ad status.",
    )


class UpdateAdParams(BaseModel):
    """Update ad status or final URLs."""
    ad_id:       str                                  = Field(description="Ad ID")
    ad_group_id: str                                  = Field(description="Parent ad group ID")
    status:      Optional[Literal["ENABLED", "PAUSED"]] = Field(default=None)
    final_urls:  Optional[list[str]]                  = Field(
        default=None,
        description="New landing page URL(s). Replaces existing URLs.",
    )


# ─── list_ad_groups ───────────────────────────────────────────────────────── #

@chat.function(
    "list_ad_groups",
    action_type="read",
    description="List all ad groups in a campaign with their bids and status.",
)
async def fn_list_ad_groups(ctx, params: AdGroupListParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        data = await api.get_ad_groups(ctx, acc, params.campaign_id)
    except Exception as e:
        return ActionResult.error(f"Failed to fetch ad groups: {e}", retryable=True)

    groups = data.get("ad_groups", [])
    return ActionResult.success(
        data={"ad_groups": groups, "total": data.get("total", len(groups))},
        summary=f"{len(groups)} ad group(s) in campaign {params.campaign_id}.",
    )


# ─── create_ad_group ──────────────────────────────────────────────────────── #

@chat.function(
    "create_ad_group",
    action_type="write",
    event="ad_group.created",
    description=(
        "Create a new ad group within a campaign. "
        "Ad groups organise ads and keywords that share a theme and bid settings."
    ),
)
async def fn_create_ad_group(ctx, params: CreateAdGroupParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    body: dict = {
        "campaign_id": params.campaign_id,
        "name":        params.name,
        "status":      params.status,
    }
    if params.cpc_bid is not None:
        body["cpc_bid"] = params.cpc_bid

    try:
        result = await api.create_ad_group(ctx, acc, body)
    except Exception as e:
        return ActionResult.error(f"Failed to create ad group: {e}", retryable=False)

    group = result.get("ad_group", result)
    return ActionResult.success(
        data={"ad_group": group},
        summary=f"Ad group '{params.name}' created (ID: {group.get('id', '?')}).",
    )


# ─── list_ads ─────────────────────────────────────────────────────────────── #

@chat.function(
    "list_ads",
    action_type="read",
    description="List all ads in an ad group with headlines, descriptions, and ad strength.",
)
async def fn_list_ads(ctx, params: AdGroupIdParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        data = await api.get_ads(ctx, acc, params.ad_group_id)
    except Exception as e:
        return ActionResult.error(f"Failed to fetch ads: {e}", retryable=True)

    ads = data.get("ads", [])
    return ActionResult.success(
        data={"ads": ads, "total": data.get("total", len(ads))},
        summary=f"{len(ads)} ad(s) in ad group {params.ad_group_id}.",
    )


# ─── create_ad ────────────────────────────────────────────────────────────── #

@chat.function(
    "create_ad",
    action_type="write",
    event="ad.created",
    description=(
        "Create a Responsive Search Ad (RSA) in an ad group. "
        "Provide 3–15 headlines (max 30 chars each) and 2–4 descriptions (max 90 chars each). "
        "Google automatically tests combinations to maximise performance."
    ),
)
async def fn_create_ad(ctx, params: CreateAdParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    # Validate lengths
    if len(params.headlines) < 3:
        return ActionResult.error(
            f"RSA requires at least 3 headlines, got {len(params.headlines)}.", retryable=False
        )
    if len(params.descriptions) < 2:
        return ActionResult.error(
            f"RSA requires at least 2 descriptions, got {len(params.descriptions)}.", retryable=False
        )
    long_headlines = [h for h in params.headlines if len(h) > 30]
    if long_headlines:
        return ActionResult.error(
            f"Headlines exceed 30 chars: {long_headlines}. Shorten them.", retryable=False
        )
    long_descs = [d for d in params.descriptions if len(d) > 90]
    if long_descs:
        return ActionResult.error(
            f"Descriptions exceed 90 chars: {long_descs}. Shorten them.", retryable=False
        )

    body = {
        "ad_group_id": params.ad_group_id,
        "ad_type":     "RESPONSIVE_SEARCH_AD",
        "final_urls":  params.final_urls,
        "headlines":   [{"text": h} for h in params.headlines],
        "descriptions":[{"text": d} for d in params.descriptions],
        "status":      params.status,
    }
    if params.path1: body["path1"] = params.path1
    if params.path2: body["path2"] = params.path2

    try:
        result = await api.create_ad(ctx, acc, body)
    except Exception as e:
        return ActionResult.error(f"Failed to create ad: {e}", retryable=False)

    ad = result.get("ad", result)
    return ActionResult.success(
        data={"ad": ad},
        summary=f"RSA ad created (ID: {ad.get('id', '?')}, strength: {ad.get('strength', 'N/A')}).",
    )


# ─── update_ad ────────────────────────────────────────────────────────────── #

@chat.function(
    "update_ad",
    action_type="write",
    event="ad.updated",
    description=(
        "Update an ad's status (ENABLED/PAUSED) or final URLs. "
        "Note: headlines and descriptions cannot be changed after creation — "
        "delete and recreate the ad if copy changes are needed."
    ),
)
async def fn_update_ad(ctx, params: UpdateAdParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    body = {}
    if params.status     is not None: body["status"]     = params.status
    if params.final_urls is not None: body["final_urls"]  = params.final_urls
    if not body:
        return ActionResult.error("No fields to update provided.", retryable=False)

    try:
        result = await api.update_ad(ctx, acc, params.ad_id, params.ad_group_id, body)
    except Exception as e:
        return ActionResult.error(f"Failed to update ad: {e}", retryable=False)

    ad = result.get("ad", result)
    return ActionResult.success(
        data={"ad": ad},
        summary=f"Ad {params.ad_id} updated.",
    )
