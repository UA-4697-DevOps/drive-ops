"""
Unit tests for HTTP client interactions with the trip service.

Tests the submit_trip_request() function covering:
- Successful trip creation (201)
- Client errors (400)
- Server errors (500)
- Timeout scenarios (504)
- Connection failures
"""

import pytest
import respx
from httpx import Response
from bot.main import submit_trip_request


@pytest.mark.asyncio
class TestSubmitTripRequest:
    """Test suite for HTTP interactions with trip service."""

    @respx.mock
    async def test_submit_trip_success_201(self):
        """Test successful trip submission with 201 Created response."""
        chat_id = 12345
        order = {
            "pickup": "вул. Хрещатик, 1",
            "dropoff": "вул. Бессарабська, 2",
            "passenger_id": "12345",
            "comment": "Будь ласка, швидко"
        }
        
        expected_response = {
            "trip_id": "trip-123",
            "status": "pending"
        }
        
        respx.post("http://localhost:8080/trips").mock(
            return_value=Response(201, json=expected_response)
        )
        
        result = await submit_trip_request(chat_id, order)
        
        assert result["success"] is True
        assert result["trip_id"] == "trip-123"
        assert result["status"] == "pending"
        assert result["error"] is None

    @respx.mock
    async def test_submit_trip_success_200(self):
        """Test successful trip submission with 200 OK response."""
        chat_id = 67890
        order = {
            "pickup": "пл. Незалежності",
            "dropoff": "Вокзал",
            "passenger_id": "67890",
            "comment": ""
        }
        
        expected_response = {
            "id": "trip-456",
            "status": "accepted"
        }
        
        respx.post("http://localhost:8080/trips").mock(
            return_value=Response(200, json=expected_response)
        )
        
        result = await submit_trip_request(chat_id, order)
        
        assert result["success"] is True
        assert result["trip_id"] == "trip-456"
        assert result["status"] == "accepted"

    @respx.mock
    async def test_submit_trip_client_error_400(self):
        """Test handling of 400 Bad Request error."""
        chat_id = 12345
        order = {
            "pickup": "",  # Invalid: empty location
            "dropoff": "вул. Бессарабська, 2",
            "passenger_id": "12345",
            "comment": ""
        }
        
        error_response = {
            "error": "Invalid pickup location"
        }
        
        respx.post("http://localhost:8080/trips").mock(
            return_value=Response(400, json=error_response)
        )
        
        result = await submit_trip_request(chat_id, order)
        
        assert result["success"] is False
        assert result["error"]["status_code"] == 400
        assert result["trip_id"] is None

    @respx.mock
    async def test_submit_trip_server_error_500(self):
        """Test handling of 500 Internal Server Error."""
        chat_id = 12345
        order = {
            "pickup": "вул. Хрещатик, 1",
            "dropoff": "вул. Бессарабська, 2",
            "passenger_id": "12345",
            "comment": ""
        }
        
        respx.post("http://localhost:8080/trips").mock(
            return_value=Response(500, text="Internal Server Error")
        )
        
        result = await submit_trip_request(chat_id, order)
        
        assert result["success"] is False
        assert result["error"]["status_code"] == 500
        assert result["trip_id"] is None

    @respx.mock
    async def test_submit_trip_timeout(self):
        """Test handling of request timeout."""
        import httpx
        
        chat_id = 12345
        order = {
            "pickup": "вул. Хрещатик, 1",
            "dropoff": "вул. Бессарабська, 2",
            "passenger_id": "12345",
            "comment": ""
        }
        
        respx.post("http://localhost:8080/trips").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        
        result = await submit_trip_request(chat_id, order)
        
        assert result["success"] is False
        assert result["error"]["status_code"] == 504
        assert result["trip_id"] is None

    @respx.mock
    async def test_submit_trip_connection_error(self):
        """Test handling of connection errors."""
        import httpx
        
        chat_id = 12345
        order = {
            "pickup": "вул. Хрещатик, 1",
            "dropoff": "вул. Бессарабська, 2",
            "passenger_id": "12345",
            "comment": ""
        }
        
        respx.post("http://localhost:8080/trips").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        
        result = await submit_trip_request(chat_id, order)
        
        assert result["success"] is False
        assert result["error"]["status_code"] == 503
        assert result["trip_id"] is None

    @respx.mock
    async def test_submit_trip_unexpected_error(self):
        """Test handling of unexpected errors during request."""
        chat_id = 12345
        order = {
            "pickup": "вул. Хрещатик, 1",
            "dropoff": "вул. Бессарабська, 2",
            "passenger_id": "12345",
            "comment": ""
        }
        
        respx.post("http://localhost:8080/trips").mock(
            side_effect=Exception("Unexpected error")
        )
        
        result = await submit_trip_request(chat_id, order)
        
        assert result["success"] is False
        assert result["error"]["status_code"] == 500
        assert result["trip_id"] is None
