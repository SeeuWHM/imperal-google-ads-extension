# Changelog

## [1.0.0] — 2026-04-17

### Added
- OAuth2 account connection via Google (Authorization Code Flow, offline access)
- MCC manager account support — detects manager accounts and prompts sub-account selection
- 20 chat functions: account management (5), campaigns (6), ad groups + ads (5), keywords (4), reports (4)
- Campaign types: Search, Shopping, Display, Video, Performance Max, Demand Gen
- Bidding strategies: MAXIMIZE_CONVERSIONS, MAXIMIZE_CONVERSION_VALUE, TARGET_CPA, TARGET_ROAS, TARGET_IMPRESSION_SHARE, TARGET_SPEND, MANUAL_CPC
- RSA ad creation with client-side validation (headline max 30 chars, description max 90 chars)
- Bulk keyword add (up to 1000 per request, BROAD/PHRASE/EXACT match types)
- Google Keyword Planner integration with graceful 429 handling (Basic Access limitation)
- Performance reports at all levels: ACCOUNT, CAMPAIGN, AD_GROUP, KEYWORD, SEARCH_TERM
- Budget status monitoring: today's spend vs daily budget with utilisation %
- AI performance analysis via `ctx.ai` — trends, issue diagnosis, 3 actionable recommendations
- Budget alert skeleton: proactive `notify()` when campaign reaches ≥90% daily budget
- 3 panels: account dashboard (left), campaign detail with tabs (right), reports + AI analysis (right)
- Health check endpoint: verifies microservice connectivity + OAuth config
- `gads_providers/` package — internal OAuth helpers, auto token refresh, HTTP client
