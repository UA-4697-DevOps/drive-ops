from unittest.mock import Mock

from src.handlers import TripCreatedEvent, handle_trip_created
from src.matching import Driver


class FakeDriverRepository:
    def list_nearby(self, lat: float, lon: float):
        return [
            Driver(id="driver-1", lat=0, lon=0, available=True),
            Driver(id="driver-2", lat=10, lon=10, available=True),
        ]


def test_handle_trip_created_publishes_event():
    repo = FakeDriverRepository()
    publisher = Mock()

    event = TripCreatedEvent(
        trip_id="trip-123",
        pickup_lat=1,
        pickup_lon=1,
    )

    chosen_driver_id = handle_trip_created(event, repo, publisher)

    assert chosen_driver_id == "driver-1"

    publisher.publish.assert_called_once_with(
        "driver.notify.trip_request",
        {
            "tripId": "trip-123",
            "driverId": "driver-1",
        },
    )
