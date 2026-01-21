import asyncio
from src.database import AsyncSessionLocal
from src.services.driver_repository import DriverRepository

DEMO_DRIVERS = [
    {"first_name": "Ivan", "last_name": "Franko", "phone_number": "+380501111111", "is_active": True},
    {"first_name": "Lesya", "last_name": "Ukrainka", "phone_number": "+380502222222", "is_active": True},
    {"first_name": "Taras", "last_name": "Shevchenko", "phone_number": "+380503333333", "is_active": False},
]

async def seed_data():
    print("🚀 Починаємо реєстрацію демо-водіїв...")
    async with AsyncSessionLocal() as session:
        repo = DriverRepository(session)
        
        for driver_data in DEMO_DRIVERS:
            # Перевірка, чи водій вже існує (за номером телефону)
            existing = await repo.get_by_phone_number(driver_data["phone_number"])

            if existing:
                print(f"⏭️  Пропущено (вже існує): {driver_data['first_name']} {driver_data['last_name']} ({driver_data['phone_number']})")
                continue

            try:
                new_driver = await repo.create(**driver_data)
                print(f"✅ Додано водія: {new_driver.first_name} {new_driver.last_name}")
            except Exception as e:
                print(f"❌ Помилка при додаванні {driver_data['first_name']}: {e}")
                await session.rollback()
                
    print("🏁 Наповнення бази завершено.")

if __name__ == "__main__":
    asyncio.run(seed_data())