"""
Tests for dns_proxy module — anchor communication.
"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

from dns_proxy import query_anchor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_anchor():
    """A sample anchor dict."""
    return {
        "id": "mumbai-01",
        "city": "Mumbai",
        "wg_ip": "10.8.0.2",
        "lat": 19.0760,
        "lon": 72.8777,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestQueryAnchor:
    """Test the query_anchor function."""

    @pytest.mark.asyncio
    async def test_successful_response(self, sample_anchor):
        """On success, should return the anchor's parsed JSON response."""
        expected = {
            "domain": "google.com",
            "record_type": "A",
            "answers": ["142.250.207.238"],
            "query_time_ms": 12.0,
            "resolver_used": "system default",
            "status": "OK",
            "raw_output": "...",
            "anchor_id": "mumbai-01",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = expected
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("dns_proxy.httpx.AsyncClient", return_value=mock_client):
            result = await query_anchor(sample_anchor, "google.com", "A")

        assert result == expected
        # Verify the correct URL was called
        mock_client.post.assert_called_once_with(
            "http://10.8.0.2:8053/resolve",
            json={"domain": "google.com", "record_type": "A"},
        )

    @pytest.mark.asyncio
    async def test_timeout_returns_error_dict(self, sample_anchor):
        """On timeout, should return an error dict — NOT raise an exception."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("connection timed out")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("dns_proxy.httpx.AsyncClient", return_value=mock_client):
            result = await query_anchor(sample_anchor, "google.com", "A")

        # Must return error dict, not raise
        assert result["error"] == "anchor_unreachable"
        assert result["anchor_id"] == "mumbai-01"
        assert result["answers"] == []
        assert result["domain"] == "google.com"
        assert result["record_type"] == "A"

    @pytest.mark.asyncio
    async def test_connection_error_returns_error_dict(self, sample_anchor):
        """On connection error, should return error dict gracefully."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("dns_proxy.httpx.AsyncClient", return_value=mock_client):
            result = await query_anchor(sample_anchor, "example.com", "AAAA")

        assert result["error"] == "anchor_unreachable"
        assert result["anchor_id"] == "mumbai-01"
        assert result["answers"] == []

    @pytest.mark.asyncio
    async def test_error_detail_present(self, sample_anchor):
        """Error dict should include error_detail with failure info."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timed out after 10s")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("dns_proxy.httpx.AsyncClient", return_value=mock_client):
            result = await query_anchor(sample_anchor, "test.com", "MX")

        assert "error_detail" in result
        assert "mumbai-01" in result["error_detail"]
