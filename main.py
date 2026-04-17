"""Google Ads Extension v1.0.0 · Google Ads AI management."""
from __future__ import annotations

import sys
import os

# ─── Module isolation (mandatory — prevents cross-extension import cache) ─── #
_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)
for _m in [k for k in sys.modules if k in (
    "app", "handlers", "handlers_campaigns", "handlers_ads",
    "handlers_keywords", "handlers_reports", "skeleton",
    "panels", "panels_campaigns", "panels_reports", "panels_ui",
    "gads_providers",
)]:
    del sys.modules[_m]

# ─── Extension entry points ───────────────────────────────────────────────── #

from app import ext, chat          # noqa: F401 — registers Extension + ChatExtension
import handlers                    # noqa: F401 — account management
import handlers_campaigns          # noqa: F401 — campaign CRUD
import handlers_ads                # noqa: F401 — ad groups + ads
import handlers_keywords           # noqa: F401 — keywords + research
import handlers_reports            # noqa: F401 — performance + AI analysis
import skeleton                    # noqa: F401 — background refresh + alerts
import panels                      # noqa: F401 — panel router
import panels_campaigns            # noqa: F401 — right panel: campaign detail
import panels_reports              # noqa: F401 — right panel: reports + research
