"""Google Ads · Skeleton tools — background refresh and budget alerts.

skeleton_refresh_gads: refreshes today's KPIs + campaign list every ~2 min.
skeleton_alert_gads:   sends proactive notify when budget ≥90% depleted.
"""
from __future__ import annotations

import logging

from app import ext
from gads_providers.helpers import _active_account, SECTION
import gads_providers.gads_client as api

log = logging.getLogger("google-ads.skeleton")

_BUDGET_ALERT_THRESHOLD = 0.90  # 90% of daily budget used


@ext.tool(
    "skeleton_refresh_gads",
    description="Background refresh: today's Google Ads KPIs, campaign list, budget alerts.",
)
async def skeleton_refresh(ctx, **kwargs) -> dict:
    acc = await _active_account(ctx)
    if not acc or not acc.get("customer_id") or acc.get("_needs_setup") or acc.get("_needs_reauth"):
        return {"response": {"connected": False}}

    try:
        campaigns_data = await api.get_campaigns(ctx, acc, status="ENABLED")
        today_data     = await api.get_performance(ctx, acc, level="CAMPAIGN", date_preset="TODAY")
        budgets_data   = await api.get_budgets(ctx, acc)
    except Exception as e:
        log.warning("skeleton_refresh failed: %s", e)
        return {"response": {"connected": True, "error": str(e)}}

    campaigns = campaigns_data.get("campaigns", [])
    today_rows = {r["campaign_id"]: r for r in today_data.get("rows", []) if r.get("campaign_id")}
    budgets    = {b["id"]: b for b in budgets_data.get("budgets", [])}

    # Build per-campaign summary with today's spend
    campaign_summaries = []
    alerts             = []

    for camp in campaigns:
        camp_id  = camp.get("id", "")
        perf     = today_rows.get(camp_id, {})
        spend    = perf.get("cost") or 0.0
        clicks   = perf.get("clicks") or 0
        budget_amount = camp.get("budget_amount") or 0.0
        budget_pct    = round(spend / budget_amount, 3) if budget_amount > 0 else 0.0

        if budget_pct >= _BUDGET_ALERT_THRESHOLD and budget_amount > 0:
            alerts.append({
                "type":          "budget_critical",
                "campaign_id":   camp_id,
                "campaign_name": camp.get("name", camp_id),
                "spend":         spend,
                "budget":        budget_amount,
                "pct":           round(budget_pct * 100, 1),
            })

        campaign_summaries.append({
            "id":            camp_id,
            "name":          camp.get("name", ""),
            "status":        camp.get("status", ""),
            "bidding":       camp.get("bidding_strategy_type", ""),
            "budget":        budget_amount,
            "spend_today":   spend,
            "clicks_today":  clicks,
            "budget_pct":    round(budget_pct * 100, 1),
        })

    # Aggregate account-level today's totals
    total_spend       = sum(r.get("cost") or 0 for r in today_rows.values())
    total_clicks      = sum(r.get("clicks") or 0 for r in today_rows.values())
    total_impressions = sum(r.get("impressions") or 0 for r in today_rows.values())
    total_conversions = sum(r.get("conversions") or 0 for r in today_rows.values())
    avg_ctr = round(total_clicks / total_impressions, 4) if total_impressions > 0 else 0.0

    return {"response": {
        "connected":    True,
        "account_name": acc.get("account_name", ""),
        "customer_id":  acc.get("customer_id", ""),
        "currency":     acc.get("currency", "USD"),
        "today": {
            "spend":       round(total_spend, 2),
            "clicks":      total_clicks,
            "impressions": total_impressions,
            "conversions": round(total_conversions, 2),
            "ctr":         avg_ctr,
        },
        "campaigns": campaign_summaries,
        "alerts":    alerts,
    }}


@ext.tool(
    "skeleton_alert_gads",
    description="Proactive alert: notify user when any campaign budget is ≥90% depleted today.",
)
async def skeleton_alert(ctx, **kwargs) -> dict:
    data = await ctx.skeleton.get(SECTION) or {}
    if not data.get("connected"):
        return {"response": {}}

    critical = [a for a in data.get("alerts", []) if a.get("type") == "budget_critical"]
    if not critical:
        return {"response": {"alerts_sent": 0}}

    if len(critical) == 1:
        a = critical[0]
        msg = (
            f"⚠️ Google Ads budget alert: '{a['campaign_name']}' "
            f"has used {a['pct']}% of its daily budget (${a['spend']:.2f} / ${a['budget']:.2f})."
        )
    else:
        names = ", ".join(f"'{a['campaign_name']}'" for a in critical[:3])
        msg = f"⚠️ Google Ads: {len(critical)} campaigns near daily budget limit: {names}."

    await ctx.notify(msg)
    return {"response": {"alerts_sent": len(critical)}}
