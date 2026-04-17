"""Google Ads · Keyword handlers.

Functions: list_keywords, add_keywords, research_keywords, get_bid_estimates.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app import chat, ActionResult, _get_ready_account
import gads_providers.gads_client as api


# ─── Models ───────────────────────────────────────────────────────────────── #

class KeywordListParams(BaseModel):
    ad_group_id: str = Field(description="Ad group ID to list keywords for")
    match_type:  Optional[Literal["BROAD", "PHRASE", "EXACT"]] = Field(
        default=None,
        description="Filter by match type. Omit to return all.",
    )


class KeywordItem(BaseModel):
    text:       str = Field(description="Keyword text (without match type symbols)")
    match_type: Literal["BROAD", "PHRASE", "EXACT"] = Field(
        default="BROAD",
        description=(
            "Match type. BROAD=broad match (widest reach). "
            "PHRASE=phrase match (search must contain this phrase). "
            "EXACT=exact match (search must match exactly)."
        ),
    )
    cpc_bid: Optional[float] = Field(
        default=None,
        description="Keyword-level CPC bid override in account currency. Omit to use ad group bid.",
    )


class AddKeywordsParams(BaseModel):
    """Bulk add keywords to an ad group."""
    ad_group_id: str            = Field(description="Ad group ID to add keywords to")
    keywords:    list[KeywordItem] = Field(
        description="List of keywords to add. Max 1000 per request."
    )


class ResearchKeywordsParams(BaseModel):
    """Research keyword ideas via Google Keyword Planner."""
    seed_keywords: Optional[list[str]] = Field(
        default=None,
        description="Seed keywords to base ideas on (e.g. ['web hosting', 'php hosting']). Max 20.",
    )
    seed_url: Optional[str] = Field(
        default=None,
        description="URL to extract keyword ideas from (e.g. 'https://webhostmost.com'). Used if seed_keywords is empty.",
    )
    language_code: str = Field(
        default="1000",
        description="Language criterion ID. 1000=English, 1003=Spanish, 1031=German.",
    )
    location_ids: list[str] = Field(
        default=["2840"],
        description="Geo target constant IDs. Default: 2840 (United States).",
    )


class BidEstimatesParams(BaseModel):
    """Get historical metrics for specific keywords."""
    keywords:    list[str] = Field(description="Keyword texts to get metrics for. Max 1000.")
    match_types: list[Literal["BROAD", "PHRASE", "EXACT"]] = Field(
        default=["BROAD"],
        description="Match types to get estimates for.",
    )
    language_code: str  = Field(default="1000")
    location_ids:  list[str] = Field(default=["2840"])


# ─── list_keywords ────────────────────────────────────────────────────────── #

@chat.function(
    "list_keywords",
    action_type="read",
    description=(
        "List all keywords in an ad group with match type, bid, "
        "quality score, and expected CTR/ad relevance/landing page experience."
    ),
)
async def fn_list_keywords(ctx, params: KeywordListParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        data = await api.get_keywords(ctx, acc, params.ad_group_id)
    except Exception as e:
        return ActionResult.error(f"Failed to fetch keywords: {e}", retryable=True)

    keywords = data.get("keywords", [])
    if params.match_type:
        keywords = [k for k in keywords if k.get("match_type") == params.match_type]

    return ActionResult.success(
        data={"keywords": keywords, "total": len(keywords)},
        summary=f"{len(keywords)} keyword(s) in ad group {params.ad_group_id}.",
    )


# ─── add_keywords ─────────────────────────────────────────────────────────── #

@chat.function(
    "add_keywords",
    action_type="write",
    event="keywords.added",
    description=(
        "Bulk add keywords to an ad group. "
        "Default match type is BROAD. Use PHRASE for 'keyword' or EXACT for [keyword]. "
        "Duplicate keywords in the same ad group are rejected by Google."
    ),
)
async def fn_add_keywords(ctx, params: AddKeywordsParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    if not params.keywords:
        return ActionResult.error("No keywords provided.", retryable=False)
    if len(params.keywords) > 1000:
        return ActionResult.error(
            f"Maximum 1000 keywords per request, got {len(params.keywords)}.", retryable=False
        )

    body = {
        "ad_group_id": params.ad_group_id,
        "keywords": [
            {
                "text":       kw.text,
                "match_type": kw.match_type,
                **({"cpc_bid": kw.cpc_bid} if kw.cpc_bid is not None else {}),
            }
            for kw in params.keywords
        ],
    }

    try:
        result = await api.add_keywords(ctx, acc, body)
    except Exception as e:
        return ActionResult.error(f"Failed to add keywords: {e}", retryable=False)

    created = result.get("created", len(params.keywords))
    return ActionResult.success(
        data={
            "keywords": result.get("keywords", []),
            "created":  created,
        },
        summary=f"{created} keyword(s) added to ad group {params.ad_group_id}.",
    )


# ─── research_keywords ────────────────────────────────────────────────────── #

@chat.function(
    "research_keywords",
    action_type="read",
    description=(
        "Research keyword ideas using Google Keyword Planner. "
        "Provide seed keywords or a website URL. "
        "Returns average monthly searches, competition level, and CPC estimates. "
        "Note: requires Standard Access developer token — returns message if unavailable."
    ),
)
async def fn_research_keywords(ctx, params: ResearchKeywordsParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    if not params.seed_keywords and not params.seed_url:
        return ActionResult.error(
            "Provide either seed_keywords or seed_url for keyword research.", retryable=False
        )

    body: dict = {
        "language_code": params.language_code,
        "location_ids":  params.location_ids,
    }
    if params.seed_keywords:
        body["seed_keywords"] = params.seed_keywords[:20]
    if params.seed_url:
        body["seed_url"] = params.seed_url

    try:
        result = await api.keyword_ideas(ctx, acc, body)
    except Exception as e:
        return ActionResult.error(f"Failed to research keywords: {e}", retryable=True)

    # Graceful handling of 429 (Basic Access limitation)
    if result.get("error") == "429_standard_access_required":
        return ActionResult.success(
            data={"ideas": [], "standard_access_required": True},
            summary=(
                "Keyword Planner requires Standard Access developer token. "
                "Apply at ads.google.com/aw/apicenter. "
                "I can suggest keywords based on your business instead — just ask."
            ),
        )

    ideas = result.get("ideas", [])
    return ActionResult.success(
        data={"ideas": ideas, "total": len(ideas)},
        summary=f"Found {len(ideas)} keyword idea(s).",
    )


# ─── get_bid_estimates ────────────────────────────────────────────────────── #

@chat.function(
    "get_bid_estimates",
    action_type="read",
    description=(
        "Get historical monthly search volume and CPC estimates for specific keywords. "
        "Useful for budget planning before adding keywords to a campaign. "
        "Note: requires Standard Access developer token."
    ),
)
async def fn_get_bid_estimates(ctx, params: BidEstimatesParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    body = {
        "keywords":      params.keywords[:1000],
        "match_types":   params.match_types,
        "language_code": params.language_code,
        "location_ids":  params.location_ids,
    }

    try:
        result = await api.keyword_metrics(ctx, acc, body)
    except Exception as e:
        return ActionResult.error(f"Failed to get bid estimates: {e}", retryable=True)

    if result.get("error") == "429_standard_access_required":
        return ActionResult.success(
            data={"metrics": [], "standard_access_required": True},
            summary="Keyword Planner requires Standard Access developer token.",
        )

    metrics = result.get("metrics", [])
    return ActionResult.success(
        data={"metrics": metrics, "total": len(metrics)},
        summary=f"Got metrics for {len(metrics)} keyword(s).",
    )
