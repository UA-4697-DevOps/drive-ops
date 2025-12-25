from src.matching import Driver, select_driver

def test_selects_nearest_available_driver():
    drivers = [
        Driver(id="A", lat=0, lon=0, available=True),
        Driver(id="B", lat=10, lon=10, available=True),
    ]
    chosen = select_driver(drivers, pickup_lat=1, pickup_lon=1)
    assert chosen is not None
    assert chosen.id == "A"

def test_returns_none_if_no_available_drivers():
    drivers = [
        Driver(id="A", lat=0, lon=0, available=False),
        Driver(id="B", lat=10, lon=10, available=False),
    ]
    chosen = select_driver(drivers, pickup_lat=1, pickup_lon=1)
    assert chosen is None
