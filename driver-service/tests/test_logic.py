from app.logic import get_driver_status

def test_get_driver_status_success():
    result = get_driver_status(100)
    assert result["status"] == "active"
    assert result["driver_id"] == 100

def test_get_driver_status_invalid():
    result = get_driver_status(-1)
    assert "error" in result