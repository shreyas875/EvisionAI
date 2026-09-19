from fastapi import APIRouter, Query
from .station import geocode
from ..models.traffic_ml import TrafficDelayRegressor
import datetime

router = APIRouter()

regressor = TrafficDelayRegressor()

@router.get("")
def get_traffic(start: str = Query(...), end: str = Query(...), hour: int = Query(None), weather: str = Query("sunny"), traffic_density: float = Query(1.0), is_holiday: bool = Query(False)):
    start_lat, start_lon = geocode(start)
    end_lat, end_lon = geocode(end)
    distance = abs(end_lat - start_lat)*111 + abs(end_lon - start_lon)*111  # crude km
    hour = hour if hour is not None else datetime.datetime.now().hour
    day_of_week = datetime.datetime.now().weekday()
    weather_map = {"sunny":0,"rainy":1,"foggy":2}
    weather_enc = weather_map.get(weather.lower(),0)
    input_features = {
        "distance": max(0.1, distance),
        "hour": hour,
        "day_of_week": day_of_week,
        "weather": weather_enc,
        "traffic_density": float(traffic_density),
        "is_holiday": int(is_holiday)
    }
    try:
        delay_min = regressor.predict(input_features)
    except Exception as e:
        delay_min = 10
    cond = 'Heavy' if delay_min > 22 else ('Moderate' if delay_min > 10 else 'Light')
    route_options = [
        {"via": "fastest", "estimated_time_min": int(delay_min)},
        {"via": "scenic", "estimated_time_min": int(delay_min*1.09)},
        {"via": "low-traffic", "estimated_time_min": int(delay_min*1.17)},
    ]
    return {"traffic_condition": cond, "route_options": route_options, "predicted_delay": delay_min}
