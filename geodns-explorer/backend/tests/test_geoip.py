"""
Tests for geoip module — IP geolocation and nearest anchor selection.
"""

import json
import math
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

# Import modules under test
from geoip import locate_ip, nearest_anchor, haversine, _subnet_cache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def anchors():
    """Load the real anchors.json for testing."""
    anchors_path = Path(__file__).parent.parent / "anchors.json"
    with open(anchors_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the subnet cache before each test."""
    _subnet_cache.clear()
    yield
    _subnet_cache.clear()


# ---------------------------------------------------------------------------
# Haversine Tests
# ---------------------------------------------------------------------------

class TestHaversine:
    """Test the haversine distance function."""

    def test_same_point_zero_distance(self):
        """Same point should have zero distance."""
        dist = haversine(19.0760, 72.8777, 19.0760, 72.8777)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_mumbai_to_delhi(self):
        """Mumbai to Delhi is approximately 1,150 km."""
        dist = haversine(19.0760, 72.8777, 28.6139, 77.2090)
        assert 1100 < dist < 1200

    def test_kolkata_to_chennai(self):
        """Kolkata to Chennai is approximately 1,350 km."""
        dist = haversine(22.5726, 88.3639, 13.0827, 80.2707)
        assert 1300 < dist < 1400


# ---------------------------------------------------------------------------
# Nearest Anchor Tests
# ---------------------------------------------------------------------------

class TestNearestAnchor:
    """Test nearest anchor selection by haversine distance."""

    def test_delhi_nearest_is_delhi(self, anchors):
        """A user at Delhi coords should get delhi-01."""
        result = nearest_anchor(28.61, 77.20, anchors)
        assert result["id"] == "delhi-01"

    def test_mumbai_nearest_is_mumbai(self, anchors):
        """A user at Mumbai coords should get mumbai-01."""
        result = nearest_anchor(19.07, 72.87, anchors)
        assert result["id"] == "mumbai-01"

    def test_kolkata_nearest_is_kolkata(self, anchors):
        """A user at Kolkata coords should get kolkata-01."""
        result = nearest_anchor(22.57, 88.36, anchors)
        assert result["id"] == "kolkata-01"

    def test_chennai_nearest_is_chennai(self, anchors):
        """A user at Chennai coords should get chennai-01."""
        result = nearest_anchor(13.08, 80.27, anchors)
        assert result["id"] == "chennai-01"

    def test_bangalore_nearest_is_bangalore(self, anchors):
        """A user at Bangalore coords should get bangalore-01."""
        result = nearest_anchor(12.97, 77.59, anchors)
        assert result["id"] == "bangalore-01"

    def test_hyderabad_nearest_is_hyderabad(self, anchors):
        """A user at Hyderabad coords should get hyderabad-01."""
        result = nearest_anchor(17.38, 78.48, anchors)
        assert result["id"] == "hyderabad-01"

    def test_between_cities_picks_closest(self, anchors):
        """A user midway between Mumbai and Bangalore should get one of them."""
        # Point roughly between Mumbai (19.07, 72.87) and Bangalore (12.97, 77.59)
        mid_lat = (19.07 + 12.97) / 2  # ~16.02
        mid_lon = (72.87 + 77.59) / 2  # ~75.23
        result = nearest_anchor(mid_lat, mid_lon, anchors)
        # Should be one of the nearby anchors
        assert result["id"] in ("mumbai-01", "bangalore-01", "hyderabad-01")

    def test_empty_anchors_raises(self):
        """Empty anchor list should raise ValueError."""
        with pytest.raises(ValueError, match="No anchors"):
            nearest_anchor(20.0, 78.0, [])


# ---------------------------------------------------------------------------
# Locate IP Tests
# ---------------------------------------------------------------------------

class TestLocateIP:
    """Test IP geolocation via ip-api.com (mocked)."""

    @pytest.mark.asyncio
    async def test_indian_ip_returns_is_india_true(self):
        """A known Indian IP should return is_india=True with city info."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "country": "India",
            "regionName": "Maharashtra",
            "city": "Mumbai",
            "lat": 19.0760,
            "lon": 72.8777,
            "isp": "Reliance Jio",
            "query": "49.36.0.1",
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("geoip.httpx.AsyncClient", return_value=mock_client):
            result = await locate_ip("49.36.0.1")

        assert result["is_india"] is True
        assert result["city"] == "Mumbai"
        assert result["region"] == "Maharashtra"
        assert result["isp"] == "Reliance Jio"
        assert result["lat"] == pytest.approx(19.076, abs=0.01)
        assert result["source"] == "ip-api"

    @pytest.mark.asyncio
    async def test_non_indian_ip_returns_is_india_false(self):
        """A non-Indian IP should return is_india=False with fallback coords."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "country": "United States",
            "regionName": "California",
            "city": "Mountain View",
            "lat": 37.3861,
            "lon": -122.0839,
            "isp": "Google LLC",
            "query": "8.8.8.8",
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("geoip.httpx.AsyncClient", return_value=mock_client):
            result = await locate_ip("8.8.8.8")

        assert result["is_india"] is False

    @pytest.mark.asyncio
    async def test_api_failure_returns_fallback(self):
        """On API failure, should return fallback dict centered on India."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("geoip.httpx.AsyncClient", return_value=mock_client):
            result = await locate_ip("1.2.3.4")

        assert result["is_india"] is False
        assert result["city"] == "Unknown"
        assert result["lat"] == pytest.approx(20.5937, abs=0.01)
        assert result["lon"] == pytest.approx(78.9629, abs=0.01)

    @pytest.mark.asyncio
    async def test_cache_prevents_duplicate_calls(self):
        """Second call for same /24 subnet should use cache, not API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "country": "India",
            "regionName": "Maharashtra",
            "city": "Mumbai",
            "lat": 19.0760,
            "lon": 72.8777,
            "isp": "Reliance Jio",
            "query": "49.36.128.10",
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("geoip.httpx.AsyncClient", return_value=mock_client):
            # First call — hits API
            result1 = await locate_ip("49.36.128.10")
            # Second call, same /24 — should use cache
            result2 = await locate_ip("49.36.128.55")

        # API should only be called once (cached on /24)
        assert mock_client.get.call_count == 1
        assert result1["city"] == "Mumbai"
        assert result2["city"] == "Mumbai"
        # IP field should reflect the queried IP, not the cached one
        assert result2["ip"] == "49.36.128.55"
