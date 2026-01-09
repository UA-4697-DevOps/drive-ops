from fastapi import FastAPI, HTTPException
from uuid import uuid4

app = FastAPI(title="DriverService", version="0.1.0")

drivers = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/drivers", status_code=201)
def register_driver():
    driver_id = str(uuid4())

    driver = {
        "id": driver_id,
        "status": "OFFLINE",
        "location": None
    }

    drivers[driver_id] = driver
    return driver


@app.get("/drivers/{driver_id}")
def get_driver(driver_id: str):
    driver = drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@app.post("/drivers/{driver_id}/status")
def update_status(driver_id: str, status: str):
    driver = drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    if status not in ["ONLINE", "OFFLINE"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    driver["status"] = status
    return driver


@app.post("/drivers/{driver_id}/location")
def update_location(driver_id: str, location: str):
    driver = drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    driver["location"] = location
    return driver
