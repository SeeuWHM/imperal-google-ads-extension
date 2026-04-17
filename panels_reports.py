"""Google Ads · Reports panel (right slot).

Shows performance data, search terms, and keyword research.
"""
from __future__ import annotations

from typing import Literal, Optional

from imperal_sdk import ui

from app import ext
from gads_providers.helpers import _active_account
import gads_providers.gads_client as api
from panels_ui import fmt_currency, fmt_number, fmt_pct, fmt_cpc, error_view

_DATE_OPTIONS = [
    {"value": "TODAY",        "label": "Today"},
    {"value": "LAST_7_DAYS",  "label": "Last 7 days"},
    {"value": "LAST_30_DAYS", "label": "Last 30 days"},
    {"value": "THIS_MONTH",   "label": "This month"},
    {"value": "LAST_MONTH",   "label": "Last month"},
]


@ext.panel(
    "reports",
    slot="right",
    title="Reports & Research",
)
async def panel_reports(
    ctx,
    report_type: str = "performance",
    date_preset: str = "LAST_30_DAYS",
    campaign_id: Optional[str] = None,
    **kwargs,
) -> ui.UINode:
    acc = await _active_account(ctx)
    if not acc:
        return error_view("No account connected.")

    currency = acc.get("currency", "USD")

    # ── Header with date selector ─────────────────────────────────────────── #
    header = ui.Stack([
        ui.Header(
            title="Reports",
            subtitle=acc.get("account_name", "Google Ads"),
        ),
        ui.Select(
            options=_DATE_OPTIONS,
            value=date_preset,
            param_name="date_preset",
            on_change=ui.Call("__panel__reports",
                              report_type=report_type,
                              campaign_id=campaign_id),
        ),
    ])

    # ── Tab navigation ────────────────────────────────────────────────────── #
    tabs = ui.Stack([
        ui.Button(
            label="Performance",
            variant="primary" if report_type == "performance" else "ghost",
            size="sm",
            on_click=ui.Call("__panel__reports",
                             report_type="performance", date_preset=date_preset,
                             campaign_id=campaign_id),
        ),
        ui.Button(
            label="Search Terms",
            variant="primary" if report_type == "search_terms" else "ghost",
            size="sm",
            on_click=ui.Call("__panel__reports",
                             report_type="search_terms", date_preset=date_preset,
                             campaign_id=campaign_id),
        ),
        ui.Button(
            label="AI Analysis",
            variant="primary" if report_type == "analysis" else "ghost",
            size="sm",
            on_click=ui.Call("__panel__reports",
                             report_type="analysis", date_preset=date_preset,
                             campaign_id=campaign_id),
        ),
    ], direction="horizontal", gap=1)

    # ── Content ───────────────────────────────────────────────────────────── #
    if report_type == "performance":
        content = await _performance_section(ctx, acc, date_preset, campaign_id, currency)
    elif report_type == "search_terms":
        content = await _search_terms_section(ctx, acc, date_preset, campaign_id, currency)
    else:
        content = _analysis_section(date_preset)

    return ui.Stack([header, ui.Divider(), tabs, content])


# ─── Performance section ──────────────────────────────────────────────────── #

async def _performance_section(ctx, acc, date_preset, campaign_id, currency) -> ui.UINode:
    try:
        data = await api.get_performance(
            ctx, acc,
            level="CAMPAIGN",
            date_preset=date_preset,
            campaign_ids=campaign_id,
        )
    except Exception as e:
        return error_view(f"Failed to load performance: {e}")

    rows = data.get("rows", [])
    if not rows:
        return ui.Empty(message=f"No data for {date_preset}")

    # Account-level totals
    total_impressions = sum(r.get("impressions") or 0 for r in rows)
    total_clicks      = sum(r.get("clicks") or 0 for r in rows)
    total_cost        = sum(r.get("cost") or 0 for r in rows)
    total_conversions = sum(r.get("conversions") or 0 for r in rows)
    avg_ctr           = total_clicks / total_impressions if total_impressions > 0 else 0
    avg_cpc           = total_cost / total_clicks if total_clicks > 0 else 0

    summary_stats = ui.Stats(columns=3, children=[
        ui.Stat(label="Spend",       value=fmt_currency(total_cost, currency), icon="DollarSign", color="blue"),
        ui.Stat(label="Clicks",      value=fmt_number(total_clicks),           icon="MousePointer", color="green"),
        ui.Stat(label="Impressions", value=fmt_number(total_impressions),      icon="Eye"),
        ui.Stat(label="CTR",         value=fmt_pct(avg_ctr),                   icon="Percent"),
        ui.Stat(label="Avg CPC",     value=fmt_cpc(avg_cpc, currency),         icon="Tag"),
        ui.Stat(label="Conversions", value=str(round(total_conversions, 1)),   icon="Target", color="purple"),
    ])

    # Per-campaign rows
    table_items = []
    for r in sorted(rows, key=lambda x: x.get("cost") or 0, reverse=True):
        ctr  = fmt_pct(r.get("ctr"))
        cost = fmt_currency(r.get("cost"), currency)
        table_items.append(ui.ListItem(
            id=r.get("campaign_id", ""),
            title=r.get("campaign_name", r.get("campaign_id", "Unknown")),
            subtitle=f"{cost} · {fmt_number(r.get('clicks'))} clicks · CTR {ctr}",
            on_click=ui.Call("__panel__campaign_detail",
                             campaign_id=r.get("campaign_id", "")),
        ))

    return ui.Stack([
        summary_stats,
        ui.Divider(label="BY CAMPAIGN"),
        ui.List(items=table_items) if table_items else ui.Empty(message="No campaign data"),
    ])


# ─── Search terms section ─────────────────────────────────────────────────── #

async def _search_terms_section(ctx, acc, date_preset, campaign_id, currency) -> ui.UINode:
    try:
        data = await api.get_search_terms(
            ctx, acc,
            date_preset=date_preset,
            campaign_ids=campaign_id,
        )
    except Exception as e:
        return error_view(f"Failed to load search terms: {e}")

    rows = data.get("rows", [])
    if not rows:
        return ui.Stack([
            ui.Alert(
                type="info",
                message="No search term data yet. Search terms appear after your ads receive clicks.",
            ),
        ])

    items = [
        ui.ListItem(
            id=str(i),
            title=r.get("search_term", "—"),
            subtitle=(
                f"{fmt_number(r.get('impressions'))} impr · "
                f"{fmt_number(r.get('clicks'))} clicks · "
                f"{fmt_currency(r.get('cost'), currency)}"
            ),
            actions=[{
                "icon":     "Plus",
                "label":    "Add as keyword",
                "on_click": ui.Send(
                    f"Add keyword '{r.get('search_term', '')}' to my campaign"
                ),
            }, {
                "icon":     "Minus",
                "label":    "Add as negative",
                "on_click": ui.Send(
                    f"Add '{r.get('search_term', '')}' as a negative keyword"
                ),
            }],
        )
        for i, r in enumerate(rows[:50])
    ]

    return ui.Stack([
        ui.Alert(
            type="info",
            message=f"{len(rows)} search terms found. Click '+' to add as keyword or '−' to exclude.",
        ),
        ui.List(items=items, searchable=True),
    ])


# ─── AI analysis section ──────────────────────────────────────────────────── #

def _analysis_section(date_preset: str) -> ui.UINode:
    return ui.Stack([
        ui.Alert(
            type="info",
            message=(
                "AI performance analysis examines your campaigns, keywords, and trends, "
                "then provides specific recommendations."
            ),
        ),
        ui.Button(
            label="Run AI Analysis",
            variant="primary",
            icon="Sparkles",
            on_click=ui.Send(f"Analyse my Google Ads performance for {date_preset}"),
        ),
        ui.Button(
            label="Search Term Insights",
            variant="ghost",
            icon="Search",
            on_click=ui.Send("What search terms are driving the most value in my Google Ads?"),
        ),
        ui.Button(
            label="Budget Recommendations",
            variant="ghost",
            icon="DollarSign",
            on_click=ui.Send("Review my Google Ads budget allocation and suggest improvements"),
        ),
    ])
