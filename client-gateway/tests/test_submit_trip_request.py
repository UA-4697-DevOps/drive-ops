import pytest
from bot.main import submit_trip_request
import respx


@pytest.mark.asyncio
async def test_submit_trip_request_success():
    order = {
        "pickup": "123 Main St",
        "dropoff": "456 Elm St",
        "comment": "Please hurry",
    }

    with respx.mock() as respx_mock:
        respx_mock.post("http://localhost:8080/trips").respond(
            status_code=201, json={"id": "123", "status": "pending"}
        )

        response = await submit_trip_request(chat_id=1, order=order)

    assert response["success"] is True
    assert response["trip_id"] == "123"
    assert response["status"] == "pending"
    assert response["error"] is None


@pytest.mark.asyncio
async def test_submit_trip_request_failure():
    order = {
        "pickup": "123 Main St",
        "dropoff": "456 Elm St",
        "comment": "Please hurry",
    }

    with respx.mock() as respx_mock:
        respx_mock.post("http://localhost:8080/trips").respond(
            status_code=500, text="Internal Server Error"
        )

        response = await submit_trip_request(chat_id=1, order=order)

    assert response["success"] is False
    assert response["trip_id"] is None
    assert response["status"] == "error"
    assert response["error"]["status_code"] == 500
    assert response["error"]["message"] == "Internal Server Error"


@pytest.mark.asyncio
async def test_submit_trip_request_invalid_data():
    order = {
        "pickup": "",
        "dropoff": "456 Elm St",
        "comment": "Please hurry",
    }

    with respx.mock() as respx_mock:
        respx_mock.post("http://localhost:8080/trips").respond(
            status_code=400, text="Invalid pickup address"
        )

        response = await submit_trip_request(chat_id=1, order=order)

    assert response["success"] is False
    assert response["trip_id"] is None
    assert response["status"] == "error"
    assert response["error"]["status_code"] == 400
    assert response["error"]["message"] == "Invalid pickup address"
