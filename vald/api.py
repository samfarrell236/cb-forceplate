"""VALD External ForceDecks API loader — STUB (not wired).

The goal: when credentials arrive, this module's `get_tests()` returns the SAME
tidy DataFrame as `vald.loader.get_tests()`, so swapping the source is a
one-line change in app.py:

    # from vald.loader import get_tests
    from vald.api import get_tests

Nothing here makes live calls yet. Credentials are read from the environment /
`.env` and are NEVER hard-coded.

References (confirm with VALD support):
- OAuth2 client-credentials token endpoint.
- Region-specific base URL (e.g. https://prd-{region}-api-extforcedecks.valdperformance.com).
- Tenants API -> tenantId.
- GET /tests?tenantId={tenantId}&modifiedFromUtc={iso8601}  (paged).
- Per-test trial/results endpoints -> metric values.
"""
from __future__ import annotations

import os

import pandas as pd

from . import schema

# --- Configuration (env only) ----------------------------------------------
VALD_CLIENT_ID = os.getenv("VALD_CLIENT_ID")
VALD_CLIENT_SECRET = os.getenv("VALD_CLIENT_SECRET")
VALD_TENANT_ID = os.getenv("VALD_TENANT_ID")  # optional; else resolve via Tenants API
VALD_REGION = os.getenv("VALD_REGION", "use")  # TODO: confirm region with VALD
TOKEN_URL = os.getenv("VALD_TOKEN_URL", "")    # TODO: confirm OAuth2 token endpoint
BASE_URL = os.getenv(
    "VALD_BASE_URL",
    f"https://prd-{VALD_REGION}-api-extforcedecks.valdperformance.com",  # TODO: confirm
)


# ---------------------------------------------------------------------------
def _get_token() -> str:
    """TODO: OAuth2 client-credentials exchange -> bearer token.

    import requests
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": VALD_CLIENT_ID,
        "client_secret": VALD_CLIENT_SECRET,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]
    """
    raise NotImplementedError("VALD OAuth2 token exchange not wired yet.")


def _resolve_tenant(token: str) -> str:
    """TODO: GET Tenants API -> tenantId (or use VALD_TENANT_ID)."""
    raise NotImplementedError("VALD Tenants API not wired yet.")


def get_tests(modified_from_utc: str = "2020-01-01T00:00:00Z") -> pd.DataFrame:
    """TODO: page /tests since `modified_from_utc`, fetch per-test results,
    and map into the canonical tidy DataFrame (schema.TIDY_COLUMNS).

    Until implemented this returns an empty canonical frame so callers don't
    break if the source is flipped prematurely.
    """
    if not (VALD_CLIENT_ID and VALD_CLIENT_SECRET):
        raise RuntimeError(
            "VALD API credentials missing. Set VALD_CLIENT_ID / VALD_CLIENT_SECRET "
            "in the environment or a .env file. (Still a stub — see vald/api.py.)"
        )
    raise NotImplementedError(
        "VALD External ForceDecks API loader is a documented stub. "
        "Implement _get_token, _resolve_tenant, and the /tests paging here, then "
        "map results into schema.TIDY_COLUMNS."
    )
