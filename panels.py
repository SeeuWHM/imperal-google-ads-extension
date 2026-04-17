"""Google Ads · Panel router — account dashboard (left panel).

Left panel: account KPIs + campaigns list.
Right panels are registered in panels_campaigns.py and panels_reports.py.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
from gads_providers.helpers import _active_account, SECTION
from panels_ui import (
    fmt_currency, fmt_number, fmt_pct, fmt_budget_pct,
    campaign_badge, not_connected_view, needs_setup_view, error_view,
)


@ext.panel(
    "account_dashboard",
    slot="left",
    title="Google Ads",
    icon="TrendingUp",
)
async def panel_account_dashboard(ctx, **kwargs) -> ui.UINode:
    acc = await _active_account(ctx)

    if not acc:
        return not_connected_view()
    if acc.get("_needs_setup"):
        return needs_setup_view()
    if acc.get("_needs_reauth"):
        return error_view("Google Ads authorisation expired. Say 'reconnect Google Ads'.")

    # Read from skeleton (instant, no API call)
    data     = ctx.skeleton_data.get(SECTION) or {}
    today    = data.get("today", {})
    campaigns = data.get("campaigns", [])
    alerts   = data.get("alerts", [])
    currency = acc.get("currency", "USD")

    # ── Budget alerts ──────────────────────────────────────────────────────── #
    alert_nodes = []
    for alert in alerts[:2]:
        alert_nodes.append(ui.Alert(
            type="warning",
            message=f"{alert['campaign_name']}: {alert['pct']}% budget used today",
        ))

    # ── Today's KPIs ──────────────────────────────────────────────────────── #
    kpi_stats = ui.Stats(columns=2, children=[
        ui.Stat(
            label="Spend Today",
            value=fmt_currency(today.get("spend", 0), currency),
            icon="DollarSign",
            color="blue",
        ),
        ui.Stat(
            label="Clicks",
            value=fmt_number(today.get("clicks", 0)),
            icon="MousePointer",
            color="green",
        ),
        ui.Stat(
            label="Impressions",
            value=fmt_number(today.get("impressions", 0)),
            icon="Eye",
        ),
        ui.Stat(
            label="Conversions",
            value=str(round(today.get("conversions", 0), 1)),
            icon="Target",
            color="purple",
        ),
    ])

    # ── Campaigns list ────────────────────────────────────────────────────── #
    campaign_items = []
    for camp in campaigns[:20]:
        pct        = camp.get("budget_pct", 0)
        spend      = camp.get("spend_today", 0)
        budget     = camp.get("budget", 0)
        budget_str = f"{fmt_currency(spend, currency)} / {fmt_currency(budget, currency)}"

        campaign_items.append(ui.ListItem(
            id=camp["id"],
            title=camp["name"],
            subtitle=f"{budget_str} · {fmt_budget_pct(pct)} budget",
            badge=campaign_badge(camp.get("status", "")),
            actions=[
                {
                    "icon":     "Pause" if camp.get("status") == "ENABLED" else "Play",
                    "label":    "Pause" if camp.get("status") == "ENABLED" else "Resume",
                    "on_click": (
                        ui.Call("pause_campaign",  campaign_id=camp["id"])
                        if camp.get("status") == "ENABLED"
                        else ui.Call("resume_campaign", campaign_id=camp["id"])
                    ),
                },
                {
                    "icon":     "BarChart2",
                    "label":    "Reports",
                    "on_click": ui.Call("__panel__reports",
                                        campaign_id=camp["id"], report_type="performance"),
                },
            ],
            on_click=ui.Call("__panel__campaign_detail", campaign_id=camp["id"]),
        ))

    campaigns_section = ui.Stack([
        ui.Divider(label=f"CAMPAIGNS ({len(campaigns)})"),
        ui.List(items=campaign_items) if campaign_items else ui.Empty(
            message="No active campaigns",
            action=ui.Send("Create a Google Ads campaign"),
        ),
    ])

    # ── Footer actions ────────────────────────────────────────────────────── #
    footer = ui.Stack([
        ui.Button(
            label="+ Campaign",
            variant="primary",
            icon="Plus",
            on_click=ui.Send("Create a new Google Ads campaign"),
        ),
        ui.Button(
            label="Reports",
            variant="ghost",
            icon="BarChart2",
            on_click=ui.Call("__panel__reports"),
        ),
    ], direction="horizontal", gap=2, sticky=True)

    nodes = [
        ui.Header(
            title=acc.get("account_name", "Google Ads"),
            subtitle=f"ID: {acc.get('customer_id', '')} · {currency}",
        ),
        *alert_nodes,
        kpi_stats,
        campaigns_section,
        footer,
    ]

    return ui.Stack(nodes)
