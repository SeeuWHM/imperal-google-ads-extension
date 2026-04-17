"""Google Ads · Campaign management handlers.

Functions: list_campaigns, get_campaign, create_campaign,
           update_campaign, pause_campaign, resume_campaign.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app import chat, ActionResult, _get_ready_account
import gads_providers.gads_client as api


# ─── Models ───────────────────────────────────────────────────────────────── #

class ListCampaignsParams(BaseModel):
    """Filter campaigns by status."""
    status: Literal["ENABLED", "PAUSED", ""] = Field(
        default="",
        description="Filter by status: ENABLED, PAUSED, or empty for all non-removed.",
    )


class CampaignIdParams(BaseModel):
    """Identify a single campaign."""
    campaign_id: str = Field(description="Campaign ID (numeric string)")


class CreateCampaignParams(BaseModel):
    """Create a new Google Ads campaign."""
    name: str = Field(
        description="Campaign name (unique within account)"
    )
    channel_type: Literal[
        "SEARCH", "DISPLAY", "SHOPPING", "VIDEO", "PERFORMANCE_MAX", "DEMAND_GEN"
    ] = Field(
        default="SEARCH",
        description=(
            "Campaign type. SEARCH=text ads on Google Search. "
            "DISPLAY=image ads on Display Network. "
            "SHOPPING=product listing ads (requires Merchant Center). "
            "VIDEO=YouTube ads. PERFORMANCE_MAX=AI cross-channel. "
            "DEMAND_GEN=Discover/Gmail/YouTube Shorts."
        ),
    )
    budget_amount: float = Field(
        description="Daily budget in account currency (e.g. 30.0 = $30/day)"
    )
    bidding_strategy: Literal[
        "MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE",
        "TARGET_CPA", "TARGET_ROAS",
        "TARGET_IMPRESSION_SHARE", "TARGET_SPEND", "MANUAL_CPC"
    ] = Field(
        default="MAXIMIZE_CONVERSIONS",
        description=(
            "Bidding strategy. MAXIMIZE_CONVERSIONS=most conversions within budget. "
            "TARGET_CPA=target cost per acquisition (set target_cpa). "
            "TARGET_ROAS=target return on ad spend (set target_roas). "
            "MANUAL_CPC=manual cost per click bidding."
        ),
    )
    target_cpa: Optional[float] = Field(
        default=None,
        description="Target cost per acquisition in account currency. Required for TARGET_CPA.",
    )
    target_roas: Optional[float] = Field(
        default=None,
        description="Target return on ad spend as ratio (e.g. 3.5 = 350%). Required for TARGET_ROAS.",
    )
    network_search_partners: bool = Field(
        default=False,
        description="Include Google Search Partners network (SEARCH campaigns only).",
    )
    network_display: bool = Field(
        default=False,
        description="Include Google Display Network (SEARCH campaigns only, Search with Display Select).",
    )


class UpdateCampaignParams(BaseModel):
    """Update campaign — only provided fields are changed."""
    campaign_id:      str            = Field(description="Campaign ID to update")
    name:             Optional[str]  = Field(default=None, description="New campaign name")
    budget_amount:    Optional[float]= Field(default=None, description="New daily budget")
    bidding_strategy: Optional[Literal[
        "MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE",
        "TARGET_CPA", "TARGET_ROAS", "TARGET_SPEND", "MANUAL_CPC"
    ]] = Field(default=None, description="New bidding strategy")
    target_cpa:       Optional[float]= Field(default=None, description="New target CPA")
    target_roas:      Optional[float]= Field(default=None, description="New target ROAS")
    status:           Optional[Literal["ENABLED", "PAUSED"]] = Field(
        default=None, description="New status"
    )


# ─── list_campaigns ───────────────────────────────────────────────────────── #

@chat.function(
    "list_campaigns",
    action_type="read",
    description=(
        "List all Google Ads campaigns with budget, bidding strategy, "
        "and serving status. Optionally filter by status."
    ),
)
async def fn_list_campaigns(ctx, params: ListCampaignsParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        data = await api.get_campaigns(ctx, acc, status=params.status)
    except Exception as e:
        return ActionResult.error(f"Failed to fetch campaigns: {e}", retryable=True)

    campaigns = data.get("campaigns", [])
    return ActionResult.success(
        data={"campaigns": campaigns, "total": data.get("total", len(campaigns))},
        summary=f"{len(campaigns)} campaign(s) found.",
    )


# ─── get_campaign ─────────────────────────────────────────────────────────── #

@chat.function(
    "get_campaign",
    action_type="read",
    description=(
        "Get full details for a specific campaign including budget, bidding strategy, "
        "serving status, network settings, and its ad groups."
    ),
)
async def fn_get_campaign(ctx, params: CampaignIdParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        campaign = await api.get_campaign(ctx, acc, params.campaign_id)
        ad_groups = await api.get_ad_groups(ctx, acc, params.campaign_id)
    except Exception as e:
        return ActionResult.error(f"Failed to fetch campaign: {e}", retryable=True)

    return ActionResult.success(
        data={
            "campaign":  campaign.get("campaign", campaign),
            "ad_groups": ad_groups.get("ad_groups", []),
        },
        summary=f"Campaign '{campaign.get('campaign', {}).get('name', params.campaign_id)}' retrieved.",
    )


# ─── create_campaign ──────────────────────────────────────────────────────── #

@chat.function(
    "create_campaign",
    action_type="write",
    event="campaign.created",
    description=(
        "Create a new Google Ads campaign. "
        "The campaign is created PAUSED — enable it when ads and keywords are ready. "
        "A new dedicated CampaignBudget is created automatically from budget_amount."
    ),
)
async def fn_create_campaign(ctx, params: CreateCampaignParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    body = {
        "name":          params.name,
        "channel_type":  params.channel_type,
        "budget_amount": params.budget_amount,
        "bidding_strategy": params.bidding_strategy,
        "network_search":         True,
        "network_search_partners": params.network_search_partners,
        "network_display":         params.network_display,
    }
    if params.target_cpa is not None:
        body["target_cpa"] = params.target_cpa
    if params.target_roas is not None:
        body["target_roas"] = params.target_roas

    try:
        result = await api.create_campaign(ctx, acc, body)
    except Exception as e:
        return ActionResult.error(f"Failed to create campaign: {e}", retryable=False)

    campaign = result.get("campaign", result)
    return ActionResult.success(
        data={"campaign": campaign},
        summary=(
            f"Campaign '{params.name}' created (ID: {campaign.get('id', '?')}) — "
            f"currently PAUSED. Enable it when ads and keywords are ready."
        ),
    )


# ─── update_campaign ──────────────────────────────────────────────────────── #

@chat.function(
    "update_campaign",
    action_type="write",
    event="campaign.updated",
    description=(
        "Update campaign name, budget, bidding strategy, or status. "
        "Only provided fields are changed."
    ),
)
async def fn_update_campaign(ctx, params: UpdateCampaignParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    body = {}
    if params.name             is not None: body["name"]             = params.name
    if params.budget_amount    is not None: body["budget_amount"]    = params.budget_amount
    if params.bidding_strategy is not None: body["bidding_strategy"] = params.bidding_strategy
    if params.target_cpa       is not None: body["target_cpa"]       = params.target_cpa
    if params.target_roas      is not None: body["target_roas"]      = params.target_roas
    if params.status           is not None: body["status"]           = params.status

    if not body:
        return ActionResult.error("No fields to update provided.", retryable=False)

    try:
        result = await api.update_campaign(ctx, acc, params.campaign_id, body)
    except Exception as e:
        return ActionResult.error(f"Failed to update campaign: {e}", retryable=False)

    campaign = result.get("campaign", result)
    return ActionResult.success(
        data={"campaign": campaign},
        summary=f"Campaign {params.campaign_id} updated.",
    )


# ─── pause_campaign ───────────────────────────────────────────────────────── #

@chat.function(
    "pause_campaign",
    action_type="write",
    event="campaign.paused",
    description="Pause a campaign immediately. All ads stop serving. Bid history is preserved.",
)
async def fn_pause_campaign(ctx, params: CampaignIdParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        result = await api.pause_campaign(ctx, acc, params.campaign_id)
    except Exception as e:
        return ActionResult.error(f"Failed to pause campaign: {e}", retryable=False)

    campaign = result.get("campaign", result)
    return ActionResult.success(
        data={"campaign": campaign},
        summary=f"Campaign {params.campaign_id} paused.",
    )


# ─── resume_campaign ──────────────────────────────────────────────────────── #

@chat.function(
    "resume_campaign",
    action_type="write",
    event="campaign.enabled",
    description="Resume (enable) a paused campaign. Ads start serving immediately.",
)
async def fn_resume_campaign(ctx, params: CampaignIdParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        result = await api.enable_campaign(ctx, acc, params.campaign_id)
    except Exception as e:
        return ActionResult.error(f"Failed to enable campaign: {e}", retryable=False)

    campaign = result.get("campaign", result)
    return ActionResult.success(
        data={"campaign": campaign},
        summary=f"Campaign {params.campaign_id} enabled.",
    )
