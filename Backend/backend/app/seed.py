from .db import SessionLocal, init_db
from .models.station import Station, StationUsage


def run():
    init_db()
    db = SessionLocal()
    try:
        if db.query(Station).count() > 0:
            print("Stations already seeded")
            return
        stations = [
            Station(name="Pune Central EV Hub", latitude=18.5204, longitude=73.8567, charger_types="CCS2,Type2", num_ports=8),
            Station(name="Baner Fast Charge", latitude=18.5586, longitude=73.7890, charger_types="CCS2,CHAdeMO", num_ports=6),
            Station(name="Magarpatta Green Charge", latitude=18.5149, longitude=73.9250, charger_types="Type2", num_ports=4),
        ]
        for s in stations:
            db.add(s)
        db.commit()
        for s in db.query(Station).all():
            for h in range(0, 24):
                base = 2 if h in (9, 18) else 1
                usage = StationUsage(station_id=s.id, hour_of_day=h, avg_cars_per_hour=base + (h % 3) * 0.5)
                db.add(usage)
        db.commit()
        print("Seeding complete")
    finally:
        db.close()


if __name__ == "__main__":
    run()
