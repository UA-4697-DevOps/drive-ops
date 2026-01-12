"""
Geographical utilities
"""
import math
from typing import List, Dict, Any


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two points using Haversine formula
    
    Returns: Distance in kilometers
    """
    R = 6371
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def find_nearby_drivers(
    drivers: Dict[str, Dict[str, Any]],
    pickup_lat: float,
    pickup_lng: float,
    radius_km: float = 5.0,
    max_drivers: int = 10
) -> List[Dict[str, Any]]:
    """Find available drivers near pickup location"""
    nearby = []
    
    for driver_id, driver in drivers.items():
        if driver.get("status") not in ["AVAILABLE", "ONLINE"]:
            continue
        
        location = driver.get("location")
        if isinstance(location, dict):
            lat = location.get("lat")
            lng = location.get("lng")
        elif isinstance(location, str) and "," in location:
            try:
                lat, lng = map(float, location.split(",")[:2])
            except (ValueError, AttributeError):
                continue
        else:
            continue
        
        if lat is None or lng is None:
            continue
        
        distance = haversine_distance(pickup_lat, pickup_lng, lat, lng)
        
        if distance <= radius_km:
            driver_copy = driver.copy()
            driver_copy["distance_km"] = round(distance, 2)
            nearby.append(driver_copy)
    
    nearby.sort(key=lambda d: d["distance_km"])
    return nearby[:max_drivers]
