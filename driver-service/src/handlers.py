from dataclasses import dataclass
from typing import Protocol, Optional
from src.matching import Driver, select_driver


@dataclass
class TripCreatedEvent:
    trip_id: str
    pickup_lat: float
    pickup_lon: float


class Publisher(Protocol):
    def publish(self, topic: str, payload: dict) -> None:
        ...


class DriverRepository(Protocol):
    def list_nearby(self, lat: float, lon: float) -> list[Driver]:
        ...


def handle_trip_created(
    event: TripCreatedEvent,
    repo: DriverRepository,
    publisher: Publisher
) -> Optional[str]:
    drivers = repo.list_nearby(event.pickup_lat, event.pickup_lon)
    chosen_driver = select_driver(
        drivers,
        event.pickup_lat,
        event.pickup_lon
    )

    if not chosen_driver:
        return None

    publisher.publish(
        "driver.notify.trip_request",
        {
            "tripId": event.trip_id,
            "driverId": chosen_driver.id
        }
    )

    return chosen_driver.id
