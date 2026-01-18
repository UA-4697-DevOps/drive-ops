import math
from typing import List, Dict, Any


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Розрахунок відстані між двома точками за формулою Гаверсину.
    
    Returns: Відстань у кілометрах
    """
    R = 6371  # Радіус Землі в км
    
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
    pickup_lng: float,  # Змінено з pickup_lon для консистентності
    radius_km: float = 5.0,
    max_drivers: int = 10
) -> List[Dict[str, Any]]:
    """Пошук доступних водіїв поруч із точкою посадки"""
    nearby = []
    
    for driver_id, driver in drivers.items():
        # Тільки ті, хто на лінії та вільний
        if driver.get("status") not in ["AVAILABLE", "ONLINE"]:
            continue
        
        location = driver.get("location")
        lat, lng = None, None

        # Парсинг локації (підтримуємо і словник, і рядок "lat,lng")
        if isinstance(location, dict):
            lat = location.get("lat")
            lng = location.get("lng")
        elif isinstance(location, str) and "," in location:
            try:
                lat, lng = map(float, location.split(",")[:2])
            except (ValueError, TypeError):
                continue
        
        if lat is None or lng is None:
            continue
        
        # ВИПРАВЛЕНО: тепер використовуємо pickup_lng, як і в аргументах
        distance = haversine_distance(pickup_lat, pickup_lng, lat, lng)
        
        if distance <= radius_km:
            driver_copy = driver.copy()
            driver_copy["distance_km"] = round(distance, 2)
            nearby.append(driver_copy)
    
    # Сортування: спочатку найближчі
    nearby.sort(key=lambda d: d["distance_km"])
    return nearby[:max_drivers]
