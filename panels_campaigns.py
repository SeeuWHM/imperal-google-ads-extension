"""Google Ads · Campaign detail panel (right slot).

Shows campaign header, ad groups, ads, and keywords.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
from gads_providers.helpers import _active_account
import gads_providers.gads_client as api
from panels_ui import (
    fmt_currency, fmt_number, fmt_pct, fmt_cpc,
    campaign_badge, serving_badge, strength_badge, error_view,
)


@ext.panel(
    "campaign_detail",
    slot="right",
    title="Campaign",
)
async def panel_campaign_detail(
    ctx,
    campaign_id: str = "",
    section: str = "ad_groups",
    **kwargs,
) -> ui.UINode:
    if not campaign_id:
        return ui.Stack([
            ui.Empty(
                message="Select a campaign from the left panel",
                icon="MousePointer",
            ),
        ])

    acc = await _active_account(ctx)
    if not acc:
        return error_view("No account connected.")

    currency = acc.get("currency", "USD")

    try:
        campaign_resp = await api.get_campaign(ctx, acc, campaign_id)
        campaign      = campaign_resp.get("campaign", campaign_resp)
    except Exception as e:
        return error_view(f"Failed to load campaign: {e}")

    # ── Campaign header ───────────────────────────────────────────────────── #
    header = ui.Stack([
        ui.Stack([
            ui.Text(content=campaign.get("name", campaign_id), variant="heading"),
            campaign_badge(campaign.get("status", "")),
        ], direction="horizontal", gap=2),
        ui.Stats(columns=3, children=[
            ui.Stat(
                label="Daily Budget",
                value=fmt_currency(campaign.get("budget_amount"), currency),
                icon="DollarSign",
            ),
            ui.Stat(
                label="Bidding",
                value=_short_bidding(campaign.get("bidding_strategy_type", "")),
                icon="TrendingUp",
            ),
            ui.Stat(
                label="Serving",
                value=campaign.get("serving_status", "—"),
                icon="Radio",
                color="green" if campaign.get("serving_status") == "SERVING" else "gray",
            ),
        ]),
    ])

    # ── Section tabs ──────────────────────────────────────────────────────── #
    tabs = ui.Stack([
        ui.Button(
            label="Ad Groups",
            variant="primary" if section == "ad_groups" else "ghost",
            size="sm",
            on_click=ui.Call("__panel__campaign_detail",
                             campaign_id=campaign_id, section="ad_groups"),
        ),
        ui.Button(
            label="Keywords",
            variant="primary" if section == "keywords" else "ghost",
            size="sm",
            on_click=ui.Call("__panel__campaign_detail",
                             campaign_id=campaign_id, section="keywords"),
        ),
        ui.Button(
            label="Settings",
            variant="primary" if section == "settings" else "ghost",
            size="sm",
            on_click=ui.Call("__panel__campaign_detail",
                             campaign_id=campaign_id, section="settings"),
        ),
    ], direction="horizontal", gap=1)

    # ── Section content ───────────────────────────────────────────────────── #
    if section == "ad_groups":
        content = await _ad_groups_section(ctx, acc, campaign_id, currency)
    elif section == "keywords":
        content = await _keywords_section(ctx, acc, campaign_id)
    else:
        content = _settings_section(campaign, currency)

    # ── Action footer ─────────────────────────────────────────────────────── #
    is_enabled = campaign.get("status") == "ENABLED"
    footer = ui.Stack([
        ui.Button(
            label="Pause" if is_enabled else "Enable",
            variant="ghost" if is_enabled else "primary",
            icon="Pause" if is_enabled else "Play",
            on_click=(
                ui.Call("pause_campaign",  campaign_id=campaign_id)
                if is_enabled
                else ui.Call("resume_campaign", campaign_id=campaign_id)
            ),
        ),
        ui.Button(
            label="Performance",
            variant="ghost",
            icon="BarChart2",
            on_click=ui.Call("__panel__reports",
                             campaign_id=campaign_id, report_type="performance"),
        ),
        ui.Button(
            label="AI Analysis",
            variant="ghost",
            icon="Sparkles",
            on_click=ui.Send(f"Analyse performance of campaign {campaign.get('name', campaign_id)}"),
        ),
    ], direction="horizontal", gap=2, sticky=True)

    return ui.Stack([header, ui.Divider(), tabs, content, footer])


# ─── Ad groups section ────────────────────────────────────────────────────── #

async def _ad_groups_section(ctx, acc, campaign_id, currency) -> ui.UINode:
    try:
        data      = await api.get_ad_groups(ctx, acc, campaign_id)
        ad_groups = data.get("ad_groups", [])
    except Exception as e:
        return error_view(f"Failed to load ad groups: {e}")

    if not ad_groups:
        return ui.Empty(
            message="No ad groups yet",
            action=ui.Send(f"Create an ad group in campaign {campaign_id}"),
        )

    items = []
    for ag in ad_groups:
        cpc = fmt_cpc(ag.get("cpc_bid"), currency)
        items.append(ui.ListItem(
            id=ag["id"],
            title=ag["name"],
            subtitle=f"CPC: {cpc} · {ag.get('type', '')}",
            badge=campaign_badge(ag.get("status", "")),
            on_click=ui.Send(f"List ads in ad group {ag['id']} ({ag['name']})"),
        ))

    return ui.Stack([
        ui.Divider(label=f"AD GROUPS ({len(ad_groups)})"),
        ui.List(items=items),
        ui.Button(
            label="+ Ad Group",
            variant="ghost",
            icon="Plus",
            on_click=ui.Send(f"Create an ad group in campaign {campaign_id}"),
        ),
    ])


# ─── Keywords section ─────────────────────────────────────────────────────── #

async def _keywords_section(ctx, acc, campaign_id) -> ui.UINode:
    try:
        ad_groups_data = await api.get_ad_groups(ctx, acc, campaign_id)
        ad_groups      = ad_groups_data.get("ad_groups", [])
        if not ad_groups:
            return ui.Empty(message="No ad groups — create one to add keywords.")

        # Fetch keywords for the first (main) ad group
        first_ag_id    = ad_groups[0]["id"]
        keywords_data  = await api.get_keywords(ctx, acc, first_ag_id)
        keywords       = keywords_data.get("keywords", [])
    except Exception as e:
        return error_view(f"Failed to load keywords: {e}")

    if not keywords:
        return ui.Empty(
            message="No keywords yet",
            action=ui.Send(f"Add keywords to campaign {campaign_id}"),
        )

    items = [
        ui.ListItem(
            id=kw["id"],
            title=kw.get("text", ""),
            subtitle=_match_label(kw.get("match_type", "BROAD")),
            badge=ui.Badge(
                label=f"QS: {kw['quality_score']}" if kw.get("quality_score") else "—",
                color="green" if (kw.get("quality_score") or 0) >= 7 else "yellow",
            ),
        )
        for kw in keywords[:30]
    ]

    return ui.Stack([
        ui.Divider(label=f"KEYWORDS ({len(keywords)})"),
        ui.List(items=items),
        ui.Button(
            label="+ Keywords",
            variant="ghost",
            icon="Plus",
            on_click=ui.Send(f"Add keywords to campaign {campaign_id}"),
        ),
    ])


# ─── Settings section ─────────────────────────────────────────────────────── #

def _settings_section(campaign, currency) -> ui.UINode:
    rows = [
        ("Campaign ID",       campaign.get("id", "—")),
        ("Channel Type",      campaign.get("channel_type", "—")),
        ("Bidding Strategy",  campaign.get("bidding_strategy_type", "—")),
        ("Daily Budget",      fmt_currency(campaign.get("budget_amount"), currency)),
        ("Budget Delivery",   campaign.get("budget_delivery", "—")),
        ("Tracking Template", campaign.get("tracking_url_template") or "—"),
        ("Final URL Suffix",  campaign.get("final_url_suffix") or "—"),
        ("Optimization Score",
            f"{round(campaign.get('optimization_score', 0) * 100)}%"
            if campaign.get("optimization_score") else "—"),
    ]
    return ui.Stack([
        ui.Divider(label="CAMPAIGN SETTINGS"),
        *[
            ui.Stack([
                ui.Text(content=label, variant="label"),
                ui.Text(content=value, variant="body"),
            ], direction="horizontal", gap=4)
            for label, value in rows
        ],
        ui.Button(
            label="Edit Budget",
            variant="ghost",
            icon="Edit",
            on_click=ui.Send(f"Update budget for campaign {campaign.get('id', '')}"),
        ),
    ])


# ─── Helpers ──────────────────────────────────────────────────────────────── #

def _short_bidding(strategy: str) -> str:
    return {
        "MAXIMIZE_CONVERSIONS":       "Max Conv.",
        "MAXIMIZE_CONVERSION_VALUE":  "Max Value",
        "TARGET_CPA":                 "Target CPA",
        "TARGET_ROAS":                "Target ROAS",
        "TARGET_IMPRESSION_SHARE":    "Target IS",
        "TARGET_SPEND":               "Target Spend",
        "MANUAL_CPC":                 "Manual CPC",
    }.get(strategy, strategy[:12] if strategy else "—")


def _match_label(match_type: str) -> str:
    return {"BROAD": "Broad", "PHRASE": "Phrase", "EXACT": "Exact"}.get(match_type, match_type)
