"""
GeoDNS Explorer — IP Geolocation Module
=========================================
Provides IP-to-location resolution via ip-api.com (free tier)
and nearest-anchor selection using haversine distance.

Caching: /24 subnet cache with 60s in-memory TTL to stay within
ip-api.com's 45 req/min rate limit.
"""

import math
import time
from typing import Any, Dict, List, Optional

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon,isp,query"
CACHE_TTL_SECONDS = 60.0
EARTH_RADIUS_KM = 6371.0

# Geographic center of India — fallback for non-Indian or failed lookups
INDIA_CENTER = {"lat": 20.5937, "lon": 78.9629}

# ---------------------------------------------------------------------------
# /24 Subnet Cache
# ---------------------------------------------------------------------------

# Structure: { "subnet_prefix": (timestamp, result_dict) }
_subnet_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _cache_key(ip: str) -> str:
    """Derive /24 subnet prefix from an IP address.

    Example: "49.36.128.55" → "49.36.128"
    """
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3])
    # Non-IPv4 (e.g., IPv6) — use full address as key
    return ip


def _cache_get(ip: str) -> Optional[Dict[str, Any]]:
    """Retrieve a cached geolocation result for the IP's /24 subnet."""
    key = _cache_key(ip)
    entry = _subnet_cache.get(key)
    if entry is None:
        return None
    cached_time, result = entry
    if time.monotonic() - cached_time > CACHE_TTL_SECONDS:
        # Expired
        del _subnet_cache[key]
        return None
    return result


def _cache_set(ip: str, result: Dict[str, Any]) -> None:
    """Store a geolocation result keyed by /24 subnet."""
    key = _cache_key(ip)
    _subnet_cache[key] = (time.monotonic(), result)


# ---------------------------------------------------------------------------
# Haversine Distance
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km.

    Uses the haversine formula — accurate for all distances on Earth.
    No external library required.
    """
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_KM * c


def nearest_anchor(lat: float, lon: float, anchors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find the closest anchor to a given lat/lon using haversine distance.

    Args:
        lat: Client latitude
        lon: Client longitude
        anchors: List of anchor dicts with "lat" and "lon" fields

    Returns:
        The anchor dict that is geographically closest.
    """
    if not anchors:
        raise ValueError("No anchors available for selection")

    best_anchor = anchors[0]
    best_distance = float("inf")

    for anchor in anchors:
        dist = haversine(lat, lon, anchor["lat"], anchor["lon"])
        if dist < best_distance:
            best_distance = dist
            best_anchor = anchor

    return best_anchor


# ---------------------------------------------------------------------------
# IP Geolocation
# ---------------------------------------------------------------------------

def _build_fallback(ip: str) -> Dict[str, Any]:
    """Build a fallback response for failed or non-Indian lookups."""
    return {
        "ip": ip,
        "city": "Unknown",
        "region": "Unknown",
        "isp": "Unknown",
        "lat": INDIA_CENTER["lat"],
        "lon": INDIA_CENTER["lon"],
        "is_india": False,
        "source": "ip-api",
    }


async def locate_ip(ip: str) -> Dict[str, Any]:
    """Geolocate an IP address using ip-api.com.

    Returns a dict with ip, city, region, isp, lat, lon, is_india, source.
    Uses /24 subnet caching with 60s TTL to respect rate limits.

    If the lookup fails or the IP is not in India, returns a fallback
    dict centered on India's geographic center so nearest-anchor logic
    still works gracefully.
    """
    # Check cache first
    cached = _cache_get(ip)
    if cached is not None:
        # Return cached result but update the specific IP field
        return {**cached, "ip": ip}

    url = IP_API_URL.format(ip=ip)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            data = response.json()
    except (httpx.HTTPError, httpx.TimeoutException, Exception):
        fallback = _build_fallback(ip)
        _cache_set(ip, fallback)
        return fallback

    # Validate response
    if data.get("status") != "success" or data.get("country") != "India":
        fallback = _build_fallback(ip)
        # Still cache the result to avoid hammering the API
        if data.get("status") == "success":
            # Valid response but not India — cache with actual data
            fallback.update({
                "city": data.get("city", "Unknown"),
                "region": data.get("regionName", "Unknown"),
                "isp": data.get("isp", "Unknown"),
                "lat": data.get("lat", INDIA_CENTER["lat"]),
                "lon": data.get("lon", INDIA_CENTER["lon"]),
            })
        _cache_set(ip, fallback)
        return fallback

    result = {
        "ip": ip,
        "city": data.get("city", "Unknown"),
        "region": data.get("regionName", "Unknown"),
        "isp": data.get("isp", "Unknown"),
        "lat": data.get("lat", INDIA_CENTER["lat"]),
        "lon": data.get("lon", INDIA_CENTER["lon"]),
        "is_india": True,
        "source": "ip-api",
    }

    _cache_set(ip, result)
    return result
