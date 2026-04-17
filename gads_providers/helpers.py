"""Google Ads · Shared constants and account helpers."""
from __future__ import annotations

import base64
import json
import os
from typing import Optional

from imperal_sdk import Context

# ─── OAuth constants ──────────────────────────────────────────────────────── #

GADS_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GADS_TOKEN_URL = "https://oauth2.googleapis.com/token"
GADS_SCOPE     = "https://www.googleapis.com/auth/adwords"

GADS_CLIENT_ID     = os.getenv("GADS_CLIENT_ID",     "")
GADS_CLIENT_SECRET = os.getenv("GADS_CLIENT_SECRET", "")
GADS_REDIRECT_URI  = os.getenv(
    "GADS_REDIRECT_URI",
    "https://auth.imperal.io/v1/oauth/google-ads/callback",
)

# ─── Microservice ─────────────────────────────────────────────────────────── #

GADS_API_URL = os.getenv("GADS_API_URL", "https://api.webhostmost.com/google-ads")
GADS_JWT     = os.getenv("GADS_JWT", "")

# ─── Storage ──────────────────────────────────────────────────────────────── #

COLLECTION = "gads_accounts"  # ext_store collection name
SECTION    = "gads_account"   # skeleton section key


# ─── OAuth state ──────────────────────────────────────────────────────────── #

def _oauth_state(ctx: Context) -> str:
    """Encode user identity as base64url JSON for the OAuth state parameter.
    Auth Gateway decodes this in the /v1/oauth/google-ads/callback handler.
    """
    payload = {
        "user_id":   str(ctx.user.id),
        "tenant_id": getattr(ctx.user, "tenant_id", "default"),
        "provider":  "google-ads",
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


# ─── Account helpers ──────────────────────────────────────────────────────── #

async def _all_accounts(ctx: Context) -> list[dict]:
    """Return all gads_accounts documents for the current user."""
    page = await ctx.store.query(COLLECTION)
    return [{"doc_id": d.id, **d.data} for d in page.data]


async def _active_account(ctx: Context, account: str = "") -> Optional[dict]:
    """Return the active (or specified) account dict, or None if not found.

    Lookup order when account= is given: doc_id → customer_id → account_name.
    Falls back to the document marked is_active, then to the first document.
    """
    page = await ctx.store.query(COLLECTION)
    if not page.data:
        return None

    if account:
        for d in page.data:
            if (d.id == account
                    or d.data.get("customer_id") == account
                    or d.data.get("account_name") == account):
                return {"doc_id": d.id, **d.data}
        return None

    for d in page.data:
        if d.data.get("is_active"):
            return {"doc_id": d.id, **d.data}
    return {"doc_id": page.data[0].id, **page.data[0].data}
