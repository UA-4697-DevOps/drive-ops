from dataclasses import dataclass
from typing import List, Optional
import math


@dataclass
class Driver:
    id: str
    lat: float
    lon: float
    available: bool


def distance(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    return math.sqrt((a_lat - b_lat) ** 2 + (a_lon - b_lon) ** 2)


def select_driver(
    drivers: List[Driver],
    pickup_lat: float,
    pickup_lon: float
) -> Optional[Driver]:
    available_drivers = [d for d in drivers if d.available]

    if not available_drivers:
        return None

    return min(
        available_drivers,
        key=lambda d: distance(d.lat, d.lon, pickup_lat, pickup_lon)
    )
