"""
GeoDNS Explorer — DNS Proxy Module
=====================================
Forwards DNS resolution requests to anchor agents over WireGuard.
Each anchor runs a FastAPI service on port 8053.
"""

from typing import Any, Dict

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANCHOR_PORT = 8053
ANCHOR_TIMEOUT = 10.0  # seconds

# ---------------------------------------------------------------------------
# Query Function
# ---------------------------------------------------------------------------


async def query_anchor(
    anchor: Dict[str, Any],
    domain: str,
    record_type: str = "A",
) -> Dict[str, Any]:
    """Forward a DNS query to an anchor agent via HTTP POST.

    Args:
        anchor: Anchor dict with at least "id" and "wg_ip" fields.
        domain: Domain name to resolve (e.g., "google.com").
        record_type: DNS record type (e.g., "A", "AAAA", "MX").

    Returns:
        The anchor's JSON response on success, or an error dict on
        timeout / connection failure.
    """
    url = f"http://{anchor['wg_ip']}:{ANCHOR_PORT}/resolve"
    payload = {
        "domain": domain,
        "record_type": record_type,
    }

    try:
        async with httpx.AsyncClient(timeout=ANCHOR_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {
            "error": "anchor_unreachable",
            "error_detail": f"Timeout after {ANCHOR_TIMEOUT}s connecting to {anchor['id']}",
            "anchor_id": anchor["id"],
            "domain": domain,
            "record_type": record_type,
            "answers": [],
        }
    except (httpx.HTTPError, httpx.ConnectError, Exception) as exc:
        return {
            "error": "anchor_unreachable",
            "error_detail": str(exc),
            "anchor_id": anchor["id"],
            "domain": domain,
            "record_type": record_type,
            "answers": [],
        }
