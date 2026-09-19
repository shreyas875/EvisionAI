from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from typing import Optional
from ..db import get_db
from ..models.station import Station
from .station import geocode, haversine_km
from ..models.routing_ml import StopRecommender
import datetime

router = APIRouter()
stopper = StopRecommender()

@router.get("/plan")
def plan_route(start: str = Query(...), end: str = Query(...), battery: int = Query(100), charger: str = Query(None), db: Session = Depends(get_db)):
    start_lat, start_lon = geocode(start)
    end_lat, end_lon = geocode(end)
    stop = None
    if battery <= 30:
        candidates = db.query(Station).all()
        if charger:
            candidates = [s for s in candidates if charger in (s.charger_types or "")]
        station_structs = [
            {
                "name": s.name,
                "distance": haversine_km(start_lat,start_lon,s.latitude,s.longitude),
                "num_ports": s.num_ports,
                "lat": s.latitude,
                "lon": s.longitude
            } for s in candidates
        ]
        hour = datetime.datetime.now().hour
        dow = datetime.datetime.now().weekday()
        if station_structs:
            best = stopper.suggest(station_structs, battery, charger or '', hour, dow)
            stop = {
                "name": best["name"],
                "lat": best["lat"],
                "lon": best["lon"],
                "distance_from_start_km": round(best["distance"],2),
                "num_ports": best["num_ports"]
            }
    route = {
        "start": {"lat": start_lat, "lon": start_lon},
        "end": {"lat": end_lat, "lon": end_lon},
        "suggested_stop": stop,
        "notes": "Battery-aware planning now powered by ML (XGBoost-based stop recommender)"
    }
    return route
