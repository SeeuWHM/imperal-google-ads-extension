"""Google Ads · Shared panel UI utilities and formatters."""
from __future__ import annotations

from imperal_sdk import ui


# ─── Formatters ───────────────────────────────────────────────────────────── #

def fmt_currency(amount, currency: str = "USD") -> str:
    """Format a monetary amount. 1500.5 → '$1,500.50'"""
    if amount is None:
        return "—"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$"}.get(currency, "$")
    return f"{symbol}{amount:,.2f}"


def fmt_number(n) -> str:
    """Format an integer with thousands separator. 1500000 → '1,500,000'"""
    if n is None:
        return "—"
    return f"{int(n):,}"


def fmt_pct(value, decimals: int = 1) -> str:
    """Format a ratio as percentage. 0.0347 → '3.5%'"""
    if value is None:
        return "—"
    return f"{float(value) * 100:.{decimals}f}%"


def fmt_cpc(amount, currency: str = "USD") -> str:
    """Format CPC in micros or float. Always 2 decimal places."""
    if amount is None:
        return "—"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency, "$")
    return f"{symbol}{float(amount):.2f}"


def fmt_budget_pct(pct: float) -> str:
    """Format budget usage percentage with warning emoji."""
    if pct >= 90:
        return f"⚠️ {pct:.0f}%"
    if pct >= 70:
        return f"⚡ {pct:.0f}%"
    return f"{pct:.0f}%"


# ─── Status badges ────────────────────────────────────────────────────────── #

def campaign_badge(status: str) -> ui.UINode:
    color = {"ENABLED": "green", "PAUSED": "yellow", "REMOVED": "red"}.get(status, "gray")
    label = {"ENABLED": "Active", "PAUSED": "Paused", "REMOVED": "Removed"}.get(status, status)
    return ui.Badge(label=label, color=color)


def serving_badge(serving_status: str) -> ui.UINode:
    color = {
        "SERVING":   "green",
        "NONE":      "gray",
        "ENDED":     "gray",
        "PENDING":   "yellow",
        "SUSPENDED": "red",
    }.get(serving_status, "gray")
    return ui.Badge(label=serving_status.capitalize(), color=color)


def strength_badge(strength: str) -> ui.UINode:
    color = {
        "EXCELLENT": "green",
        "GOOD":      "blue",
        "AVERAGE":   "yellow",
        "POOR":      "red",
    }.get(strength, "gray")
    return ui.Badge(label=strength.capitalize(), color=color)


# ─── Common UI blocks ─────────────────────────────────────────────────────── #

def not_connected_view() -> ui.UINode:
    return ui.Stack([
        ui.Empty(
            message="No Google Ads account connected",
            icon="TrendingUp",
            action=ui.Send("Connect my Google Ads account"),
        ),
    ])


def needs_setup_view() -> ui.UINode:
    return ui.Stack([
        ui.Empty(
            message="Google Ads authorised — select your ad account",
            icon="Settings",
            action=ui.Send("Setup Google Ads account"),
        ),
    ])


def error_view(message: str) -> ui.UINode:
    return ui.Stack([
        ui.Alert(type="error", message=message),
    ])
