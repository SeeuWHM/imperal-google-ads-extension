"""Google Ads · Token refresh helpers.

Google OAuth2 access tokens expire in ~1 hour. Refresh via oauth2.googleapis.com.
Unlike Microsoft, Google does NOT rotate the refresh_token on each refresh.
Refresh tokens for Google Ads live indefinitely unless revoked — no 90-day expiry.
"""
from __future__ import annotations

import logging
import time

from imperal_sdk import Context

from .helpers import (
    COLLECTION,
    GADS_CLIENT_ID,
    GADS_CLIENT_SECRET,
    GADS_TOKEN_URL,
)

log = logging.getLogger("google-ads.token")

_REFRESH_BUFFER = 120  # refresh if token expires within 2 minutes


async def _refresh_gads_token(ctx: Context, acc: dict) -> dict:
    """Exchange the stored refresh_token for a new access_token.

    On success:  updates ctx.store and returns updated acc dict.
    On HTTP 400: sets _needs_reauth=True (refresh_token was revoked).
    Never raises — returns acc unchanged on transient errors.
    """
    resp = await ctx.http.post(GADS_TOKEN_URL, data={
        "grant_type":    "refresh_token",
        "client_id":     GADS_CLIENT_ID,
        "client_secret": GADS_CLIENT_SECRET,
        "refresh_token": acc["refresh_token"],
        # Google does NOT require scope on refresh
    })

    if resp.status_code != 200:
        log.warning(
            "Google Ads token refresh failed: %s — %s",
            resp.status_code,
            resp.text[:200],
        )
        if resp.status_code == 400:
            acc["_needs_reauth"] = True
            doc_id = acc.get("doc_id")
            if doc_id:
                try:
                    await ctx.store.update(COLLECTION, doc_id, {"_needs_reauth": True})
                except Exception:
                    pass
        return acc

    tokens = resp.json()
    acc["access_token"] = tokens["access_token"]
    acc["expires_at"]   = int(time.time()) + tokens.get("expires_in", 3600)
    # Google does not return a new refresh_token on refresh — keep existing
    acc.pop("_needs_reauth", None)

    doc_id = acc.pop("doc_id")
    await ctx.store.update(COLLECTION, doc_id, {k: v for k, v in acc.items()})
    acc["doc_id"] = doc_id
    return acc


async def _refresh_token_if_needed(ctx: Context, acc: dict) -> dict:
    """Refresh access_token if it expires within _REFRESH_BUFFER seconds."""
    if acc.get("expires_at", 0) > time.time() + _REFRESH_BUFFER:
        return acc
    return await _refresh_gads_token(ctx, acc)
