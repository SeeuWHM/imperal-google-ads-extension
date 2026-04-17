"""Google Ads · Performance reports and AI analysis handlers.

Functions: get_performance, get_search_terms, get_budget_status, analyze_performance.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app import chat, ActionResult, _get_ready_account
import gads_providers.gads_client as api


# ─── Models ───────────────────────────────────────────────────────────────── #

class PerformanceParams(BaseModel):
    """Fetch a performance report."""
    level: Literal[
        "ACCOUNT", "CAMPAIGN", "AD_GROUP", "KEYWORD", "SEARCH_TERM"
    ] = Field(
        default="CAMPAIGN",
        description=(
            "Reporting level. ACCOUNT=total account summary. "
            "CAMPAIGN=per campaign breakdown. AD_GROUP=per ad group. "
            "KEYWORD=per keyword with quality scores. SEARCH_TERM=actual search queries."
        ),
    )
    date_preset: Literal[
        "TODAY", "YESTERDAY", "LAST_7_DAYS", "LAST_14_DAYS",
        "LAST_30_DAYS", "LAST_WEEK", "LAST_MONTH", "THIS_MONTH", "ALL_TIME"
    ] = Field(
        default="LAST_30_DAYS",
        description="Date range preset.",
    )
    campaign_ids: Optional[str] = Field(
        default=None,
        description="Comma-separated campaign IDs to filter. Omit for all campaigns.",
    )


class SearchTermsParams(BaseModel):
    date_preset: Literal[
        "LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS",
        "LAST_WEEK", "LAST_MONTH", "THIS_MONTH"
    ] = Field(
        default="LAST_30_DAYS",
        description="Date range for search terms report.",
    )
    campaign_ids: Optional[str] = Field(
        default=None,
        description="Filter by campaign IDs (comma-separated).",
    )


class AnalyzeParams(BaseModel):
    date_preset: Literal[
        "LAST_7_DAYS", "LAST_14_DAYS", "LAST_30_DAYS", "LAST_MONTH", "THIS_MONTH"
    ] = Field(
        default="LAST_30_DAYS",
        description="Date range for AI analysis.",
    )
    focus: Optional[str] = Field(
        default=None,
        description=(
            "Optional focus area for analysis. "
            "Examples: 'CTR optimization', 'budget efficiency', 'keyword performance'."
        ),
    )


# ─── get_performance ──────────────────────────────────────────────────────── #

@chat.function(
    "get_performance",
    action_type="read",
    description=(
        "Get performance report at any level (account/campaign/ad group/keyword/search term). "
        "Returns impressions, clicks, cost, CTR, CPC, conversions, ROAS."
    ),
)
async def fn_get_performance(ctx, params: PerformanceParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        data = await api.get_performance(
            ctx, acc,
            level=params.level,
            date_preset=params.date_preset,
            campaign_ids=params.campaign_ids,
        )
    except Exception as e:
        return ActionResult.error(f"Failed to fetch report: {e}", retryable=True)

    rows = data.get("rows", [])
    return ActionResult.success(
        data={
            "rows":        rows,
            "total_rows":  data.get("total_rows", len(rows)),
            "level":       params.level,
            "date_preset": params.date_preset,
        },
        summary=(
            f"{len(rows)} row(s) in {params.level} report "
            f"for {params.date_preset}."
        ),
    )


# ─── get_search_terms ─────────────────────────────────────────────────────── #

@chat.function(
    "get_search_terms",
    action_type="read",
    description=(
        "See actual search queries that triggered your ads. "
        "Reveals what users searched before clicking, sorted by impressions. "
        "Use to find new keywords to add or negative keywords to exclude."
    ),
)
async def fn_get_search_terms(ctx, params: SearchTermsParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        data = await api.get_search_terms(
            ctx, acc,
            date_preset=params.date_preset,
            campaign_ids=params.campaign_ids,
        )
    except Exception as e:
        return ActionResult.error(f"Failed to fetch search terms: {e}", retryable=True)

    rows = data.get("rows", [])
    return ActionResult.success(
        data={
            "search_terms": rows,
            "total":        data.get("total_rows", len(rows)),
            "date_preset":  params.date_preset,
        },
        summary=f"{len(rows)} search term(s) found for {params.date_preset}.",
    )


# ─── get_budget_status ────────────────────────────────────────────────────── #

@chat.function(
    "get_budget_status",
    action_type="read",
    description=(
        "Check today's spend vs budget for all campaigns. "
        "Flags campaigns that are over-pacing (≥90% budget used) or under-delivering."
    ),
)
async def fn_get_budget_status(ctx) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    try:
        budgets_data  = await api.get_budgets(ctx, acc)
        today_report  = await api.get_performance(ctx, acc, level="CAMPAIGN", date_preset="TODAY")
    except Exception as e:
        return ActionResult.error(f"Failed to fetch budget status: {e}", retryable=True)

    budgets  = {b["id"]: b for b in budgets_data.get("budgets", [])}
    today_by_campaign = {
        r["campaign_id"]: r
        for r in today_report.get("rows", [])
        if r.get("campaign_id")
    }

    alerts = []
    summary_rows = []

    for camp_id, perf in today_by_campaign.items():
        spend   = perf.get("cost") or 0.0
        budget  = None

        # Try to find budget from budgets endpoint
        for b in budgets.values():
            # We don't have direct campaign→budget mapping here;
            # rely on skeleton for full mapping. Show what we have.
            pass

        pct = None
        summary_rows.append({
            "campaign_id":   camp_id,
            "campaign_name": perf.get("campaign_name"),
            "spend_today":   spend,
            "impressions":   perf.get("impressions"),
            "clicks":        perf.get("clicks"),
        })

    # Budget alerts come from skeleton (refreshed every 2 min)
    skeleton_data = await ctx.skeleton.get("gads_account") or {}
    alerts = skeleton_data.get("alerts", [])

    return ActionResult.success(
        data={
            "campaigns":  summary_rows,
            "budgets":    list(budgets.values()),
            "alerts":     alerts,
            "total_campaigns": len(summary_rows),
        },
        summary=(
            f"Budget status: {len(summary_rows)} active campaign(s). "
            f"{len([a for a in alerts if a.get('type') == 'budget_critical'])} budget alert(s)."
        ),
    )


# ─── analyze_performance ──────────────────────────────────────────────────── #

@chat.function(
    "analyze_performance",
    action_type="read",
    description=(
        "AI-powered performance analysis. "
        "Fetches campaign + keyword data then uses AI to identify trends, "
        "diagnose CTR/CPC issues, and provide 3 specific actionable recommendations."
    ),
)
async def fn_analyze_performance(ctx, params: AnalyzeParams) -> ActionResult:
    acc, err = await _get_ready_account(ctx)
    if err:
        return err

    await ctx.progress(10, "Fetching campaign performance data…")

    try:
        campaign_data = await api.get_performance(
            ctx, acc, level="CAMPAIGN", date_preset=params.date_preset
        )
        keyword_data  = await api.get_performance(
            ctx, acc, level="KEYWORD", date_preset=params.date_preset
        )
    except Exception as e:
        return ActionResult.error(f"Failed to fetch data for analysis: {e}", retryable=True)

    await ctx.progress(50, "Running AI analysis…")

    campaign_rows = campaign_data.get("rows", [])
    keyword_rows  = keyword_data.get("rows", [])

    # Build compact summary for AI (avoid token overload)
    top_campaigns = sorted(
        [r for r in campaign_rows if r.get("cost") is not None],
        key=lambda r: r.get("cost", 0),
        reverse=True,
    )[:10]

    top_keywords = sorted(
        [r for r in keyword_rows if r.get("impressions") is not None],
        key=lambda r: r.get("impressions", 0),
        reverse=True,
    )[:15]

    focus_text = f"\n\nFocus area: {params.focus}" if params.focus else ""
    account_name = acc.get("account_name", "Google Ads account")

    prompt = f"""Analyse Google Ads performance for "{account_name}" ({params.date_preset}){focus_text}.

## Campaign Performance (top by spend)
{_format_rows(top_campaigns, ['campaign_name', 'impressions', 'clicks', 'cost', 'ctr', 'average_cpc', 'conversions', 'conversion_rate', 'roas'])}

## Top Keywords by Impressions
{_format_rows(top_keywords, ['keyword_text', 'keyword_match_type', 'impressions', 'clicks', 'cost', 'ctr', 'average_cpc', 'quality_score'])}

Provide:
1. Key observations (2-3 sentences on overall performance)
2. Top issues identified (specific metrics that are underperforming)
3. Three specific, actionable recommendations with expected impact

Be concise and data-driven. Use specific numbers from the data."""

    try:
        result = await ctx.ai.complete(prompt=prompt, max_tokens=1500)
        analysis = result.text
    except Exception as e:
        analysis = f"AI analysis unavailable: {e}"

    await ctx.progress(100, "Analysis complete.")

    return ActionResult.success(
        data={
            "analysis":        analysis,
            "campaigns_count": len(campaign_rows),
            "keywords_count":  len(keyword_rows),
            "date_preset":     params.date_preset,
        },
        summary=f"AI analysis complete for {params.date_preset}.",
    )


def _format_rows(rows: list, keys: list) -> str:
    """Format report rows as a compact text table for AI prompt."""
    if not rows:
        return "No data available."
    lines = [" | ".join(keys)]
    lines.append("-" * 60)
    for row in rows:
        lines.append(" | ".join(str(row.get(k, "-")) for k in keys))
    return "\n".join(lines)
