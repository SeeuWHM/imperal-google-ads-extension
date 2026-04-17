# imperal-google-ads-extension

[![Imperal SDK](https://img.shields.io/badge/imperal--sdk-1.5.4-blue)](https://pypi.org/project/imperal-sdk/)
[![Version](https://img.shields.io/badge/version-1.0.0-green)](https://github.com/SeeuWHM/imperal-google-ads-extension/releases)
[![License](https://img.shields.io/badge/license-LGPL--2.1-orange)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Imperal%20Cloud-purple)](https://panel.imperal.io)

**Google Ads AI manager extension for [Imperal Cloud](https://panel.imperal.io).**

Connect your Google Ads account via OAuth and manage campaigns, ad groups, keywords, and performance reports through natural language.

---

## What It Does

Talk to it naturally:

```
"connect my Google Ads account"
"show me all campaigns"
"pause the WordPress Hosting campaign"
"create a Search campaign with $30 daily budget"
"add keywords: managed hosting, php hosting to ad group Main"
"what are people searching before clicking my ads?"
"analyse my performance for the last 30 days"
"which campaign has the best ROI?"
"check my budget status"
```

Or manage campaigns from the panel — left sidebar shows account KPIs and campaign list, right panel shows campaign detail, ad groups, keywords, and performance reports.

---

## Capabilities

### Account Management
| Action | Description |
|--------|-------------|
| **connect** | OAuth2 authorization via Google (access_type=offline, prompt=consent) |
| **status** | Current account, today's KPIs, budget alerts |
| **setup_account** | Post-OAuth: discover and activate a Google Ads customer account |
| **switch_account** | Switch between multiple connected accounts |
| **disconnect** | Remove account credentials |

### Campaigns
| Action | Description |
|--------|-------------|
| **list_campaigns** | All campaigns with budget, bidding strategy, serving status |
| **get_campaign** | Campaign detail + ad groups |
| **create_campaign** | Search / Shopping / Display / Video / PerformanceMax / DemandGen |
| **update_campaign** | Budget, bidding strategy, status, name |
| **pause_campaign** | One-click pause |
| **resume_campaign** | One-click enable |

### Ad Groups & Ads
| Action | Description |
|--------|-------------|
| **list_ad_groups** | Ad groups by campaign with bids |
| **create_ad_group** | With CPC bid and initial status |
| **list_ads** | Ads by ad group with strength rating |
| **create_ad** | RSA: 3–15 headlines (max 30 chars), 2–4 descriptions (max 90 chars) |
| **update_ad** | Status and final URLs |

### Keywords
| Action | Description |
|--------|-------------|
| **list_keywords** | By ad group — match type, quality score, CTR/relevance/landing page |
| **add_keywords** | Bulk: text + match_type (BROAD/PHRASE/EXACT) + optional CPC bid |
| **research_keywords** | Google Keyword Planner: ideas from seed keywords or URL |
| **get_bid_estimates** | Historical metrics and CPC estimates for specific keywords |

### Reports & AI Analysis
| Action | Description |
|--------|-------------|
| **get_performance** | Account / campaign / ad group / keyword / search term level |
| **get_search_terms** | Actual user search queries triggering your ads |
| **get_budget_status** | Today: spend vs budget, budget utilisation % |
| **analyze_performance** | AI insights via `ctx.ai` — trends, CTR/CPC diagnostics, 3 recommendations |

---

## Panel UI

Built on [Imperal Declarative UI](https://github.com/imperalcloud/imperal-sdk) — zero custom React.

```
┌──── Left Panel (account_dashboard) ────────┐  ┌──── Right Panel ─────────────────────────────┐
│  Google Ads                                │  │  Campaign Detail / Reports                    │
│  ID: 263-131-7705 · USD                    │  │  ──────────────────────────────────────────   │
│  ──────────────────────────────────────    │  │                                               │
│  Spend    Clicks   Impressions  Convs      │  │  [Ad Groups] [Keywords] [Settings]            │
│  $18.40   142      4,230        3.0        │  │                                               │
│  ──────────────────────────────────────    │  │  Ad Groups (2)                               │
│  CAMPAIGNS (3)                             │  │    Main          · ENABLED · CPC $0.01        │
│    WH Evergreen    Active  $15/15 ⚠️100%   │  │    Brand         · ENABLED · CPC $0.50        │
│    WP Hosting      Active  $8/30  27%      │  │                                               │
│    PHP Hosting     Paused  —               │  │  ──────────────────────────────────────────   │
│                                            │  │  Keywords (19)                               │
│  [+ Campaign]  [Reports]                   │  │    wordpress hosting       · Broad  QS —      │
└────────────────────────────────────────────┘  │    managed wordpress       · Broad  QS —      │
                                                │    [+ Keywords]                               │
                                                └──────────────────────────────────────────────┘
```

---

## File Structure

```
imperal-google-ads-extension/
├── main.py                  # Entry point — sys.modules cleanup + imports
├── app.py                   # Extension setup, ChatExtension, helpers, health check
├── handlers.py              # connect, status, setup_account, switch_account, disconnect
├── handlers_campaigns.py    # list/get/create/update/pause/resume campaigns
├── handlers_ads.py          # list/create ad groups + list/create/update ads
├── handlers_keywords.py     # list/add keywords, research (Keyword Planner), bid estimates
├── handlers_reports.py      # performance, search terms, budget status, AI analysis
├── skeleton.py              # skeleton_refresh_gads + skeleton_alert_gads
├── panels.py                # Left panel: account dashboard + campaign list
├── panels_campaigns.py      # Right panel: campaign detail (ad groups / keywords / settings)
├── panels_reports.py        # Right panel: performance / search terms / AI analysis
├── panels_ui.py             # Shared formatters and UI helpers
├── system_prompt.txt        # LLM system prompt
├── imperal.json             # Extension manifest
└── gads_providers/          # Internal package — OAuth helpers, token refresh, HTTP client
    ├── __init__.py
    ├── helpers.py           # OAuth constants, COLLECTION, account helpers
    ├── token_refresh.py     # Google access token auto-refresh (120s buffer)
    └── gads_client.py       # HTTP client → whm-google-ads-control microservice
```

---

## Architecture

```
User (chat)
    ↓ OAuth2 Authorization Code Flow (access_type=offline, prompt=consent)
Google Accounts → callback → Auth Gateway /v1/oauth/google-ads/callback
    ↓ tokens stored in ctx.store["gads_accounts"]
Extension → HTTP → whm-google-ads-control (:8092 on api-server)
    X-Gads-Access-Token + X-Gads-Customer-Id + X-Gads-Login-Customer-Id headers
    ↓ microservice → per-request GoogleAdsClient → Google Ads API v23 (gRPC)
```

**OAuth flow:**
1. `connect()` → generates OAuth URL with `access_type=offline&prompt=consent`
2. Auth Gateway callback → tokens saved in `gads_accounts` store collection
3. `setup_account()` → discovers accessible customer accounts → user selects one
4. All subsequent calls go through the microservice with `X-Gads-*` headers

**MCC support:** When the user has a Manager account (MCC), `setup_account` detects it and prompts the user to select a sub-account. The `manager_customer_id` is stored separately and sent as `X-Gads-Login-Customer-Id`.

---

## Skeleton

| Tool | Description |
|------|-------------|
| `skeleton_refresh_gads` | Today's KPIs (spend/clicks/impressions/conversions), campaign list with budget %, alerts |
| `skeleton_alert_gads` | `notify()` when any campaign reaches ≥90% of daily budget |

Skeleton refreshes every ~2 minutes. Budget alerts trigger a push notification immediately.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GADS_CLIENT_ID` | — | Google OAuth2 client ID |
| `GADS_CLIENT_SECRET` | — | Google OAuth2 client secret |
| `GADS_REDIRECT_URI` | `https://auth.imperal.io/v1/oauth/google-ads/callback` | OAuth callback URI |
| `GADS_API_URL` | `https://api.webhostmost.com/google-ads` | Microservice URL |
| `GADS_JWT` | — | Service JWT for microservice auth |

> **Note:** Google Ads Keyword Planner requires Standard Access developer token. With Basic Access, `research_keywords` and `get_bid_estimates` return a graceful message instead of 429.

---

## Built with

- [imperal-sdk](https://github.com/imperalcloud/imperal-sdk) 1.5.4
- [Imperal Cloud](https://panel.imperal.io)
- Google Ads API v23 via [google-ads-python](https://github.com/googleads/google-ads-python) (microservice layer)
