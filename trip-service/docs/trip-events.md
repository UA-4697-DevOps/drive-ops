# Trip Service Event Schemas

Цей документ описує структуру повідомлень, які `TripService` використовує для взаємодії з іншими сервісами через Message Broker.

### Версіонування
В усіх подіях використовується поле `event_version`. 
- Поточна версія: **1.0**
- Усі зміни, що ламають сумісність (breaking changes), вимагатимуть підняття мажорної версії.

---

### 1. trip.event.created (Publish)
Ця подія публікується одразу після того, як поїздка успішно створена в базі даних зі статусом `PENDING`.

**Приклад JSON:**
```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "trip.event.created",
  "event_version": "1.0",
  "correlation_id": "corr-uuid-12345",
  "timestamp": "2025-12-29T12:00:00Z",
  "payload": {
    "trip_id": "trip-abc-123",
    "passenger_id": "pass-xyz-789",
    "pickup": {
      "address": "вул. Хрещатик, 1",
      "lat": 50.4501,
      "lng": 30.5234
    },
    "dropoff": {
      "address": "Аеропорт Бориспіль",
      "lat": 50.3450,
      "lng": 30.8947
    },
    "created_at": "2025-12-29T12:00:00Z"
  }
}
```

### 2. trip.event.driver_assigned
**Опис:** Цю подію `TripService` отримує від `DriverService` після того, як водій натиснув "Прийняти поїздку". На основі цих даних сервіс оновлює статус поїздки в базі даних.

**Приклад JSON:**
```json
{
  "event_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "event_type": "trip.event.driver_assigned",
  "event_version": "1.0",
  "correlation_id": "corr-uuid-12345",
  "timestamp": "2025-12-29T12:05:00Z",
  "payload": {
    "trip_id": "trip-abc-123",
    "driver_id": "driver-fixed-999",
    "assigned_at": "2025-12-29T12:05:00Z"
  }
}
```
