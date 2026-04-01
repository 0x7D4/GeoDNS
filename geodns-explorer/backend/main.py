"""
GeoDNS Explorer — Backend API
==============================
FastAPI backend that orchestrates DNS queries across anchor nodes.
Runs on the cloud VM (10.8.0.1), serves the frontend via nginx.

Endpoints:
  GET  /api/health   — Health check
  GET  /api/anchors  — List anchors (without internal WG IPs)
  GET  /api/locate   — Geolocate client IP, return nearest anchor
  POST /api/query    — Resolve a domain via an anchor
"""

import ipaddress
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from geoip import locate_ip, nearest_anchor
from dns_proxy import query_anchor

# ---------------------------------------------------------------------------
# Load anchor registry
# ---------------------------------------------------------------------------

ANCHORS_PATH = Path(__file__).parent / "anchors.json"


def load_anchors() -> List[Dict[str, Any]]:
    """Load the anchor registry from anchors.json."""
    with open(ANCHORS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


ANCHORS: List[Dict[str, Any]] = load_anchors()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GeoDNS Explorer API",
    description="Orchestrates GeoDNS measurements across Indian anchor nodes",
    version="1.0.0",
)

# CORS — allow all origins (tightened in nginx)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# RFC 1918 private ranges
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

# Mock location for local/private IPs — Kolkata
MOCK_LOCAL_LOCATION = {
    "ip": "127.0.0.1",
    "city": "Kolkata",
    "region": "West Bengal",
    "isp": "Local Development",
    "lat": 22.5726,
    "lon": 88.3639,
    "is_india": True,
    "source": "mock-local",
}


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private/loopback (RFC 1918 + loopback)."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def get_real_ip(request: Request) -> str:
    """Extract real client IP, rejecting private/loopback spoofing."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        if not ip.startswith(("127.", "10.", "192.168.", "172.")):
            return ip
            
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        ip = real_ip.strip()
        if not ip.startswith(("127.", "10.", "192.168.", "172.")):
            return ip
            
    return request.client.host if request.client else "127.0.0.1"


def _find_anchor_by_id(anchor_id: str) -> Optional[Dict[str, Any]]:
    """Find an anchor by its ID."""
    for anchor in ANCHORS:
        if anchor["id"] == anchor_id:
            return anchor
    return None


def _strip_wg_ip(anchor: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the anchor dict without the internal wg_ip field."""
    return {k: v for k, v in anchor.items() if k != "wg_ip"}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Request body for the /api/query endpoint."""
    domain: str = Field(..., min_length=1, max_length=253, examples=["example.com"])
    record_type: str = Field(default="A", examples=["A", "AAAA", "MX"])
    anchor_id: Optional[str] = Field(default=None, examples=["mumbai-01"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check — returns status and number of registered anchors."""
    return {"status": "ok", "anchor_count": len(ANCHORS)}


@app.get("/api/anchors")
async def list_anchors():
    """List all registered anchors (without internal WG IPs for security)."""
    return [_strip_wg_ip(a) for a in ANCHORS]


@app.get("/api/locate")
async def locate(request: Request, ip: Optional[str] = None):
    """Geolocate a client IP and find the nearest anchor.

    Query params:
        ip: (optional) IP to locate. If not provided, uses the
            requester's IP (with X-Forwarded-For support for nginx).

    For private/loopback IPs (local dev), returns a mock Kolkata
    location so the nearest-anchor logic still works.
    """
    target_ip = ip or get_real_ip(request)

    # Private/loopback IP → mock location for local dev
    if _is_private_ip(target_ip):
        location = {**MOCK_LOCAL_LOCATION, "ip": target_ip}
    else:
        location = await locate_ip(target_ip)

    # Find nearest anchor
    closest = nearest_anchor(location["lat"], location["lon"], ANCHORS)

    return {
        "location": location,
        "nearest_anchor": _strip_wg_ip(closest),
    }


@app.post("/api/query")
async def query_dns(request: Request, body: QueryRequest):
    """Resolve a domain via an anchor node.

    If anchor_id is provided, uses that anchor directly (manual mode).
    Otherwise, auto-selects the nearest anchor based on client IP geolocation.

    Returns the anchor's DNS response plus metadata about which anchor
    was used and how it was selected.
    """
    selection_method = "manual"

    if body.anchor_id:
        # Manual anchor selection
        anchor = _find_anchor_by_id(body.anchor_id)
        if anchor is None:
            return {
                "error": "unknown_anchor",
                "detail": f"No anchor found with id '{body.anchor_id}'",
                "available_anchors": [a["id"] for a in ANCHORS],
            }
    else:
        # Auto-select nearest anchor
        selection_method = "auto"
        target_ip = get_real_ip(request)

        if _is_private_ip(target_ip):
            location = {**MOCK_LOCAL_LOCATION, "ip": target_ip}
        else:
            location = await locate_ip(target_ip)

        anchor = nearest_anchor(location["lat"], location["lon"], ANCHORS)

    # Forward query to the selected anchor
    result = await query_anchor(anchor, body.domain, body.record_type)

    return {
        **result,
        "anchor_used": _strip_wg_ip(anchor),
        "selection_method": selection_method,
    }
