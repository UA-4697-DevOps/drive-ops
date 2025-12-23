def get_driver_status(driver_id: int):
    """
    Returns the status for a given driver ID.
    
    Args:
        driver_id (int): Identifier of the driver.
    """
    if driver_id > 0:
        return {"driver_id": driver_id, "status": "active"}
    return {"error": "Invalid ID"}