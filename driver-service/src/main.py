from fastapi import FastAPI
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
