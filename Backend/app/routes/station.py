from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Depends
from ..db import get_db
from ..models.station import Station, StationUsage
from ..models.waiting_time.model import WaitingTimePredictor
import math
import datetime
import random
import httpx
import asyncio
import json
import os

try:
    from sklearn.ensemble import RandomForestRegressor  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # fallback placeholders
    RandomForestRegressor = None
    np = None

router = APIRouter()

# OpenChargeMap API configuration
OPENCHARGEMAP_API_BASE = "https://api.openchargemap.io/v3/poi/"
OPENCHARGEMAP_API_KEY = "your-api-key-here"  # Replace with actual API key if needed

# Cache for real-time occupancy data
occupancy_cache: Dict[str, Dict[str, Any]] = {}
cache_timestamp: Dict[str, datetime.datetime] = {}
CACHE_DURATION_MINUTES = 5  # Cache for 5 minutes


async def fetch_openchargemap_data(lat: float, lon: float, radius_km: int = 10) -> List[Dict[str, Any]]:
    """Fetch real-time data from OpenChargeMap API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{OPENCHARGEMAP_API_BASE}?output=json&latitude={lat}&longitude={lon}&distance={radius_km}&maxresults=50&includecomments=true"
            if OPENCHARGEMAP_API_KEY != "your-api-key-here":
                url += f"&key={OPENCHARGEMAP_API_KEY}"
            
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error fetching OpenChargeMap data: {e}")
        return []


def calculate_real_occupancy(station_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate real occupancy based on OpenChargeMap data"""
    try:
        # Extract key information
        status_type = station_data.get('StatusType', {})
        is_operational = status_type.get('IsOperational', True)
        
        if not is_operational:
            return {
                'is_operational': False,
                'occupancy_rate': 1.0,  # 100% "occupied" if closed
                'wait_time_min': 999,  # Very high wait time
                'available_points': 0,
                'total_points': station_data.get('NumberOfPoints', 1)
            }
        
        # Get connection information
        connections = station_data.get('Connections', [])
        total_points = station_data.get('NumberOfPoints', len(connections))
        
        # Estimate current usage based on status and comments
        available_points = total_points
        
        # Check for status information in connections
        for conn in connections:
            conn_status = conn.get('StatusType', {})
            if not conn_status.get('IsOperational', True):
                available_points -= 1
        
        # Estimate based on recent comments/usage patterns
        comments = station_data.get('Comments', [])
        recent_comments = [c for c in comments if c.get('CommentTypeID') == 10]  # Usage comments
        
        # Simple heuristic: if there are recent "busy" comments, reduce availability
        busy_indicators = ['busy', 'full', 'wait', 'queue', 'occupied']
        recent_busy_comments = sum(1 for comment in recent_comments 
                                 if any(indicator in comment.get('Comment', '').lower() 
                                       for indicator in busy_indicators))
        
        if recent_busy_comments > 0:
            available_points = max(0, available_points - min(recent_busy_comments, total_points // 2))
        
        occupancy_rate = (total_points - available_points) / max(1, total_points)
        
        # Calculate wait time based on occupancy
        avg_session_time_min = 30  # Average charging session time
        if occupancy_rate >= 0.9:  # 90%+ occupied
            wait_time_min = avg_session_time_min * 2
        elif occupancy_rate >= 0.7:  # 70%+ occupied
            wait_time_min = avg_session_time_min * 1.5
        elif occupancy_rate >= 0.5:  # 50%+ occupied
            wait_time_min = avg_session_time_min
        else:  # Less than 50% occupied
            wait_time_min = max(0, avg_session_time_min * occupancy_rate)
        
        return {
            'is_operational': True,
            'occupancy_rate': occupancy_rate,
            'wait_time_min': wait_time_min,
            'available_points': available_points,
            'total_points': total_points,
            'data_source': 'openchargemap_real'
        }
        
    except Exception as e:
        print(f"Error calculating real occupancy: {e}")
        return {
            'is_operational': True,
            'occupancy_rate': 0.5,  # Default fallback
            'wait_time_min': 15,
            'available_points': 1,
            'total_points': 2,
            'data_source': 'fallback'
        }


def get_cached_occupancy(station_name: str) -> Optional[Dict[str, Any]]:
    """Get cached occupancy data if still valid"""
    if station_name in occupancy_cache and station_name in cache_timestamp:
        if datetime.datetime.now() - cache_timestamp[station_name] < datetime.timedelta(minutes=CACHE_DURATION_MINUTES):
            return occupancy_cache[station_name]
    return None


def cache_occupancy_data(station_name: str, data: Dict[str, Any]):
    """Cache occupancy data with timestamp"""
    occupancy_cache[station_name] = data
    cache_timestamp[station_name] = datetime.datetime.now()


# Haversine distance in km
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# Very basic mock geocoder: expects "lat,lon" or returns fixed demo coords
def geocode(location: str):
    try:
        if "," in location:
            lat_str, lon_str = location.split(",", 1)
            return float(lat_str.strip()), float(lon_str.strip())
    except Exception:
        pass
    # Default city center
    return 18.5204, 73.8567  # Pune


def estimate_service_rate_per_port_per_hour(charger_types: str) -> float:
    """Return average service rate (sessions per hour) per port based on charger type mix.

    Heuristic:
    - DC fast (contains 'CCS', 'CHAdeMO', 'DC'): ~2 sessions/hour/port (≈30 min/session)
    - Otherwise (e.g., Type2/AC): ~1 session/hour/port (≈60 min/session)
    If mixed, take the max (favoring faster capability).
    """
    types = (charger_types or "").upper()
    if any(k in types for k in ["CCS", "CHADEMO", "DC"]):
        return 2.0
    return 1.0


def erlang_c_wait_minutes(arrival_rate_per_hour: float, service_rate_per_port_per_hour: float, num_ports: int) -> float:
    """Compute expected queue wait time (minutes) for M/M/c using Erlang C.

    Returns 0 if system under-utilized with near-zero queueing. Caps large waits when unstable.
    """
    c = max(1, int(num_ports))
    lam = max(0.0, float(arrival_rate_per_hour))
    mu = max(1e-6, float(service_rate_per_port_per_hour))
    if lam <= 1e-9:
        return 0.0
    rho = lam / (c * mu)
    if rho >= 0.999:  # unstable / saturated
        return 120.0  # cap at 2 hours

    a = lam / mu
    # Compute P0
    s = 0.0
    fact = 1.0
    for n in range(0, c):
        if n > 0:
            fact *= n
        s += (a ** n) / fact
    # term for n=c
    fact_c = fact * c if c > 0 else 1.0
    s += (a ** c) / (fact_c * (1.0 - rho))
    p0 = 1.0 / s if s > 0 else 0.0

    # Erlang C probability of wait
    erlang_c = ((a ** c) / fact_c) * (1.0 / (1.0 - rho)) * p0 if fact_c > 0 and (1.0 - rho) > 0 else 1.0

    # Expected waiting time in queue (hours)
    wq_hours = erlang_c / (c * mu - lam)
    return max(0.0, wq_hours * 60.0)


@router.get("/realtime-wait-times-advanced")
async def get_advanced_realtime_wait_times(
    location: str = Query(...), 
    battery: int = Query(100), 
    charger: Optional[str] = None, 
    use_real_data: bool = Query(True),
    db: Session = Depends(get_db)
):
    """Get real-time waiting times with OpenChargeMap integration - Level 3 Advanced"""
    user_lat, user_lon = geocode(location)
    stations: List[Station] = db.query(Station).all()
    if not stations:
        raise HTTPException(status_code=404, detail="No stations in database. Seed data required.")

    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute
    
    # Fetch real-time data from OpenChargeMap if requested
    openchargemap_data = []
    if use_real_data:
        try:
            openchargemap_data = await fetch_openchargemap_data(user_lat, user_lon, radius_km=20)
            print(f"Fetched {len(openchargemap_data)} stations from OpenChargeMap")
        except Exception as e:
            print(f"Failed to fetch OpenChargeMap data: {e}")
            use_real_data = False

    # Create a mapping of OpenChargeMap stations by name/location
    ocm_station_map = {}
    for ocm_station in openchargemap_data:
        try:
            station_name = ocm_station.get('AddressInfo', {}).get('Title', 'Unknown Station')
            ocm_station_map[station_name.lower()] = ocm_station
        except:
            continue

    results = []
    for s in stations:
        if charger and charger not in (s.charger_types or ""):
            continue

        distance_km = haversine_km(user_lat, user_lon, s.latitude, s.longitude)

        # Try to get real occupancy data first
        real_occupancy = None
        data_source = "simulated"
        
        # Check cache first
        cached_data = get_cached_occupancy(s.name)
        if cached_data:
            real_occupancy = cached_data
            data_source = "cached"
        elif use_real_data and s.name.lower() in ocm_station_map:
            # Calculate real occupancy from OpenChargeMap data
            ocm_data = ocm_station_map[s.name.lower()]
            real_occupancy = calculate_real_occupancy(ocm_data)
            cache_occupancy_data(s.name, real_occupancy)
            data_source = "openchargemap_real"

        if real_occupancy:
            # Use real occupancy data
            wait_time_min = real_occupancy['wait_time_min']
            utilization = real_occupancy['occupancy_rate']
            is_operational = real_occupancy['is_operational']
            available_points = real_occupancy.get('available_points', s.num_ports)
            total_points = real_occupancy.get('total_points', s.num_ports)
            
            # Add some time-based variation even with real data
            time_factor = (hour * 60 + minute) % 1440
            random.seed(int(time_factor / 10))
            time_variation = 1.0 + (random.random() - 0.5) * 0.1  # ±5% variation
            wait_time_min *= time_variation
            
        else:
            # Fallback to simulated data (existing logic)
            historical = 0.0
            for u in s.usage:
                if u.hour_of_day == hour:
                    historical = u.avg_cars_per_hour
                    break

            time_factor = (hour * 60 + minute) % 1440
            random.seed(int(time_factor / 10))
            time_variation = 1.0 + (random.random() - 0.5) * 0.6
            peak_factor = 1.0
            if hour in [7, 8, 17, 18]:
                peak_factor = 1.3
            elif hour in [22, 23, 0, 1, 2, 3, 4, 5]:
                peak_factor = 0.7
            
            predicted = historical * time_variation * peak_factor
            mu_per_port = estimate_service_rate_per_port_per_hour(s.charger_types)
            service_variation = 1.0 + (random.random() - 0.5) * 0.2
            mu_per_port *= service_variation
            
            wait_time_min = erlang_c_wait_minutes(predicted, mu_per_port, s.num_ports)
            wait_variation = 1.0 + (random.random() - 0.5) * 0.4
            wait_time_min *= wait_variation
            wait_time_min = max(0, wait_time_min)
            
            utilization = min(0.999, predicted / max(1e-6, s.num_ports * mu_per_port))
            is_operational = True
            available_points = max(0, s.num_ports - int(predicted))
            total_points = s.num_ports

        results.append({
            "station_id": s.id,
            "station_name": s.name,
            "distance_km": round(distance_km, 2),
            "charger_types": s.charger_types,
            "wait_time_min": round(wait_time_min, 1),
            "utilization": round(utilization, 3),
            "is_operational": is_operational,
            "available_points": available_points,
            "total_points": total_points,
            "data_source": data_source,
            "predicted_cars_per_hour": round(predicted if 'predicted' in locals() else 0, 1),
            "service_rate_per_port": round(mu_per_port if 'mu_per_port' in locals() else 0, 2),
            "timestamp": now.isoformat(),
            "last_updated": datetime.datetime.now().strftime("%H:%M:%S"),
            "cache_age_minutes": 0 if data_source == "openchargemap_real" else 
                               int((datetime.datetime.now() - cache_timestamp.get(s.name, now)).total_seconds() / 60) if s.name in cache_timestamp else 0
        })

    return {
        "location": {"lat": user_lat, "lon": user_lon},
        "timestamp": now.isoformat(),
        "update_interval_seconds": 10,
        "real_data_enabled": use_real_data,
        "openchargemap_stations_found": len(openchargemap_data),
        "cache_size": len(occupancy_cache),
        "results": results
    }


@router.get("/realtime-wait-times")
def get_realtime_wait_times(location: str = Query(...), battery: int = Query(100), charger: Optional[str] = None, db: Session = Depends(get_db)):
    """Get real-time waiting times for all stations - updates every 10 seconds"""
    user_lat, user_lon = geocode(location)
    stations: List[Station] = db.query(Station).all()
    if not stations:
        raise HTTPException(status_code=404, detail="No stations in database. Seed data required.")

    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute
    
    # Add some randomness based on current time to simulate real-time changes
    time_factor = (hour * 60 + minute) % 1440  # minutes in day
    random.seed(int(time_factor / 10))  # Change every 10 minutes

    results = []
    for s in stations:
        if charger and charger not in (s.charger_types or ""):
            continue

        distance_km = haversine_km(user_lat, user_lon, s.latitude, s.longitude)

        # Get historical data
        historical = 0.0
        for u in s.usage:
            if u.hour_of_day == hour:
                historical = u.avg_cars_per_hour
                break

        # Add real-time variation (±30% based on time of day and randomness)
        time_variation = 1.0 + (random.random() - 0.5) * 0.6  # ±30% variation
        peak_factor = 1.0
        if hour in [7, 8, 17, 18]:  # Rush hours
            peak_factor = 1.3
        elif hour in [22, 23, 0, 1, 2, 3, 4, 5]:  # Night hours
            peak_factor = 0.7
        
        predicted = historical * time_variation * peak_factor

        # Calculate real-time wait time with more dynamic factors
        mu_per_port = estimate_service_rate_per_port_per_hour(s.charger_types)
        
        # Add some randomness to service rate (simulate varying charging speeds)
        service_variation = 1.0 + (random.random() - 0.5) * 0.2  # ±10% service variation
        mu_per_port *= service_variation
        
        wait_time_min = erlang_c_wait_minutes(predicted, mu_per_port, s.num_ports)
        
        # Add some randomness to wait time (±20%)
        wait_variation = 1.0 + (random.random() - 0.5) * 0.4
        wait_time_min *= wait_variation
        wait_time_min = max(0, wait_time_min)  # Ensure non-negative
        
        utilization = round(min(0.999, predicted / max(1e-6, s.num_ports * mu_per_port)), 3)

        results.append({
            "station_id": s.id,
            "station_name": s.name,
            "distance_km": round(distance_km, 2),
            "charger_types": s.charger_types,
            "wait_time_min": round(wait_time_min, 1),
            "utilization": utilization,
            "predicted_cars_per_hour": round(predicted, 1),
            "service_rate_per_port": round(mu_per_port, 2),
            "timestamp": now.isoformat(),
            "last_updated": datetime.datetime.now().strftime("%H:%M:%S")
        })

    return {
        "location": {"lat": user_lat, "lon": user_lon},
        "timestamp": now.isoformat(),
        "update_interval_seconds": 10,
        "results": results
    }


@router.get("/find")
def find_stations(location: str = Query(...), battery: int = Query(100), charger: Optional[str] = None, db: Session = Depends(get_db)):
    user_lat, user_lon = geocode(location)
    stations: List[Station] = db.query(Station).all()
    if not stations:
        raise HTTPException(status_code=404, detail="No stations in database. Seed data required.")

    now = datetime.datetime.now()
    hour = now.hour

    results = []
    # Optional ML model for wait time prediction
    model = None
    if RandomForestRegressor and np is not None:
        # Train simple model per request using historical usage (placeholder)
        X = []
        y = []
        for s in stations:
            for u in s.usage:
                # features: [hour_of_day, num_ports]
                X.append([u.hour_of_day, s.num_ports])
                # target: avg cars per hour
                y.append(u.avg_cars_per_hour)
        if X and y:
            model = RandomForestRegressor(n_estimators=50, random_state=42)
            model.fit(np.array(X), np.array(y))

    for s in stations:
        if charger and charger not in (s.charger_types or ""):
            continue

        distance_km = haversine_km(user_lat, user_lon, s.latitude, s.longitude)

        # Queue estimation
        historical = 0.0
        for u in s.usage:
            if u.hour_of_day == hour:
                historical = u.avg_cars_per_hour
                break
        # Predict unknown cars using simple model
        predicted = historical
        if model and np is not None:
            try:
                predicted = float(model.predict(np.array([[hour, s.num_ports]]))[0])
            except Exception:
                predicted = historical

        ports_in_use = min(int(predicted), s.num_ports)
        waiting_cars = max(0, int(predicted - ports_in_use))

        # Battery-aware scoring (penalize long distances when battery low)
        battery_factor = 1.0
        if battery <= 20:
            battery_factor = 0.6
        elif battery <= 40:
            battery_factor = 0.8

        # M/M/c queueing-based wait estimate using Erlang C
        mu_per_port = estimate_service_rate_per_port_per_hour(s.charger_types)
        wait_time_min = erlang_c_wait_minutes(predicted, mu_per_port, s.num_ports)
        utilization = round(min(0.999, (predicted) / max(1e-6, s.num_ports * mu_per_port)), 3)

        # Compatibility boost if charger requested and available
        compatibility = 1.0
        if charger and charger in s.charger_types:
            compatibility = 1.1

        # Score: lower distance and lower wait time better, multiplied by factors
        score = (1.0 / (1.0 + distance_km)) * (1.0 / (1.0 + wait_time_min/30)) * battery_factor * compatibility

        results.append({
            "station_name": s.name,
            "distance_km": round(distance_km, 2),
            "charger_types": s.charger_types,
            "wait_time_min": wait_time_min,
            "utilization": utilization,
            "wait_method": "mmc_erlang_c",
            "score": round(score, 4),
        })

    # Sort by score desc
    results.sort(key=lambda r: r["score"], reverse=True)
    return {"location": {"lat": user_lat, "lon": user_lon}, "results": results}


@router.get("/predict_waiting")
async def predict_waiting_time(
    station_id: int = Query(...),
    hour: Optional[int] = Query(None),
    day_of_week: Optional[int] = Query(None),
    weather_condition: Optional[str] = Query("sunny"),
    weather_severity: Optional[float] = Query(0.5),
    traffic_level: Optional[float] = Query(0.5),
    is_holiday: Optional[bool] = Query(False),
    db: Session = Depends(get_db)
):
    """
    Predict waiting time for a specific station using ML model.
    Returns predicted wait time with confidence and feature importance.
    """
    try:
        # Get station from database
        station = db.query(Station).filter(Station.id == station_id).first()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
        
        # Initialize predictor
        predictor = WaitingTimePredictor()
        
        # Use current time if not provided
        now = datetime.datetime.now()
        hour = hour if hour is not None else now.hour
        day_of_week = day_of_week if day_of_week is not None else now.weekday()
        
        # Prepare features for prediction
        features = {
            'hour': hour,
            'day_of_week': day_of_week,
            'month': now.month,
            'station_type': 'city_center',  # Default, could be enhanced with station metadata
            'charger_type': station.charger_types.split(',')[0] if station.charger_types else 'Type2',
            'num_ports': station.num_ports,
            'temperature': 25.0,  # Default temperature, could be fetched from weather API
            'weather_condition': weather_condition,
            'weather_severity': weather_severity,
            'traffic_level': traffic_level,
            'is_holiday': is_holiday,
            'is_weekend': day_of_week >= 5,
            'base_load': 0.5  # Default load, could be calculated from historical data
        }
        
        # Make prediction
        prediction_result = predictor.predict(features)
        
        # Get top feature importance
        top_features = []
        if prediction_result.get('feature_importance'):
            sorted_features = sorted(
                prediction_result['feature_importance'].items(),
                key=lambda x: x[1], reverse=True
            )
            top_features = sorted_features[:5]
        
        return {
            "station_id": station_id,
            "station_name": station.name,
            "predicted_wait_time_minutes": round(prediction_result['predicted_wait_time_minutes'], 1),
            "confidence": round(prediction_result['confidence'], 3),
            "wait_time_category": get_wait_time_category(prediction_result['predicted_wait_time_minutes']),
            "top_feature_importance": [
                {"feature": feat, "importance": round(imp, 3)} 
                for feat, imp in top_features
            ],
            "features_used": features,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/voice_command")
async def process_voice_command(command_data: Dict[str, Any]):
    """
    Process voice commands using AI for natural language understanding.
    Uses OpenAI GPT or similar API for command interpretation.
    """
    print(f"🎤 Voice command received: {command_data}")

    try:
        command = command_data.get("command", "").strip()
        if not command:
            print("❌ Empty command received")
            return {"response": "I didn't hear any command. Please try again.", "action": "none"}

        # Use OpenAI API for natural language processing (you'll need to set OPENAI_API_KEY)
        openai_key = os.getenv("OPENAI_API_KEY", "")
        print(f"🔑 OpenAI key available: {bool(openai_key)}")

        # TEMPORARY: Force rule-based processing for testing
        print("🔄 Using rule-based processing (OpenAI disabled for testing)...")
        response = process_with_rules(command)

        # Uncomment below to enable OpenAI when key is working:
        # if openai_key:
        #     # Use OpenAI for advanced NLP
        #     print("🤖 Processing with OpenAI...")
        #     response = await process_with_openai(command, openai_key)
        # else:
        #     # Fallback to rule-based processing
        #     print("🔄 Falling back to rule-based processing...")
        #     response = process_with_rules(command)

        print(f"✅ Voice command processed: {response}")
        return response

    except Exception as e:
        print(f"❌ Voice command processing error: {e}")
        return {
            "response": "Sorry, I'm having trouble processing your request right now.",
            "action": "error",
            "error": str(e)
        }


async def process_with_openai(command: str, api_key: str) -> Dict[str, Any]:
    """Process command using OpenAI GPT for natural language understanding."""
    print(f"🔄 Processing with OpenAI: '{command}'")
    print(f"🔑 API Key available: {bool(api_key)}")

    # If no API key, go directly to fallback
    if not api_key:
        print("❌ No OpenAI API key found, using fallback")
        return process_with_rules(command)

    try:
        system_prompt = """
        You are an AI voice assistant for an EV charging station locator app.
        Analyze the user's voice command and determine the appropriate action.

        Available actions:
        - plan_route: Plan a new route with charging stops
        - show_green_stations: Show stations with wait time < 5 minutes
        - show_yellow_stations: Show stations with wait time 5-15 minutes
        - show_red_stations: Show stations with wait time > 15 minutes
        - update_wait_times: Refresh real-time wait time data
        - get_station_count: Tell user how many stations are available
        - get_battery_status: Report current battery level
        - highlight_top_station: Highlight the best recommended station
        - get_help: Show available commands
        - none: No specific action needed

        IMPORTANT: Respond ONLY with valid JSON format:
        {
            "response": "Natural language response to user",
            "action": "action_name",
            "confidence": 0.0-1.0,
            "parameters": {}
        }
        """

        print("📡 Sending request to OpenAI API...")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Voice command: {command}"}
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                }
            )

            print(f"📊 OpenAI API Status: {response.status_code}")
            print(f"📄 OpenAI Response: {response.text[:500]}")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Parse JSON response
                try:
                    result = json.loads(content)
                    print(f"✅ Parsed OpenAI result: {result}")
                    return result
                except json.JSONDecodeError as e:
                    print(f"❌ JSON parsing failed: {e}")
                    # Fallback if JSON parsing fails
                    return {
                        "response": "I understood your request but had trouble processing it.",
                        "action": "none",
                        "confidence": 0.3
                    }
            elif response.status_code == 401:
                print("❌ OpenAI API: Invalid API key")
                return process_with_rules(command)
            elif response.status_code == 429:
                print("❌ OpenAI API: Rate limit exceeded")
                return process_with_rules(command)
            else:
                print(f"❌ OpenAI API error: {response.status_code} - {response.text}")
                return process_with_rules(command)

    except Exception as e:
        print(f"❌ OpenAI processing failed: {e}")
        # Fallback to rule-based processing
        return process_with_rules(command)


def process_with_rules(command: str) -> Dict[str, Any]:
    """Fallback rule-based command processing."""
    print(f"🔄 Processing with rules: '{command}'")
    cmd = command.lower()

    # Route planning
    if any(word in cmd for word in ['plan', 'find', 'navigate', 'route']):
        print("✅ Detected route planning command")
        return {
            "response": "Planning your optimal EV route with charging stops.",
            "action": "plan_route",
            "confidence": 0.9
        }

    # Station filtering by color
    if any(word in cmd for word in ['green', 'fast', 'quick']) and 'station' in cmd:
        print("✅ Detected green stations command")
        return {
            "response": "Showing stations with wait times under 5 minutes.",
            "action": "show_green_stations",
            "confidence": 0.85
        }

    if any(word in cmd for word in ['yellow', 'medium']) and 'station' in cmd:
        print("✅ Detected yellow stations command")
        return {
            "response": "Showing stations with moderate wait times of 5 to 15 minutes.",
            "action": "show_yellow_stations",
            "confidence": 0.85
        }

    if any(word in cmd for word in ['red', 'busy', 'long']) and 'station' in cmd:
        print("✅ Detected red stations command")
        return {
            "response": "Showing stations with high wait times over 15 minutes.",
            "action": "show_red_stations",
            "confidence": 0.85
        }

    # Updates
    if any(word in cmd for word in ['update', 'refresh', 'latest']):
        print("✅ Detected update command")
        return {
            "response": "Updating real-time wait times for all stations.",
            "action": "update_wait_times",
            "confidence": 0.9
        }

    # Information queries
    if 'how many' in cmd and 'station' in cmd:
        print("✅ Detected station count command")
        return {
            "response": "Let me check how many charging stations are available.",
            "action": "get_station_count",
            "confidence": 0.8
        }

    if 'battery' in cmd:
        print("✅ Detected battery command")
        return {
            "response": "Checking your current battery status.",
            "action": "get_battery_status",
            "confidence": 0.8
        }

    if any(word in cmd for word in ['best', 'top']) and 'station' in cmd:
        print("✅ Detected top station command")
        return {
            "response": "Highlighting the top recommended charging station.",
            "action": "highlight_top_station",
            "confidence": 0.8
        }

    # Help
    if any(word in cmd for word in ['help', 'command', 'what can you']):
        print("✅ Detected help command")
        return {
            "response": "I can help you find charging stations, filter by wait times, update information, and plan routes. Try saying: show green stations, update wait times, or plan route.",
            "action": "get_help",
            "confidence": 0.9
        }

    # Default
    print("❓ Command not recognized, using default response")
    return {
        "response": f"I heard: {command}. I'm still learning! Try saying 'help' to see what I can do.",
        "action": "none",
        "confidence": 0.3
    }


def get_wait_time_category(wait_time_minutes: float) -> str:
    """Categorize wait time for color coding."""
    if wait_time_minutes < 5:
        return "green"  # < 5 minutes
    elif wait_time_minutes < 15:
        return "yellow"  # 5-15 minutes
    else:
        return "red"  # > 15 minutes


@router.post("/train_model")
async def train_waiting_time_model():
    """
    Train the waiting time prediction model with synthetic data.
    This endpoint can be called to retrain the model.
    """
    try:
        predictor = WaitingTimePredictor()
        results = predictor.train(n_samples=15000)
        
        return {
            "message": "Model training completed successfully",
            "results": results,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.get("/predict_all_stations")
async def predict_all_stations_waiting(
    location: str = Query(...),
    weather_condition: Optional[str] = Query("sunny"),
    weather_severity: Optional[float] = Query(0.5),
    traffic_level: Optional[float] = Query(0.5),
    is_holiday: Optional[bool] = Query(False),
    db: Session = Depends(get_db)
):
    """
    Predict waiting times for all stations with ML model.
    Returns predictions with color-coded categories.
    """
    try:
        user_lat, user_lon = geocode(location)
        stations = db.query(Station).all()
        
        if not stations:
            raise HTTPException(status_code=404, detail="No stations in database")
        
        predictor = WaitingTimePredictor()
        now = datetime.datetime.now()
        
        results = []
        for station in stations:
            distance_km = haversine_km(user_lat, user_lon, station.latitude, station.longitude)
            
            # Prepare features for this station
            features = {
                'hour': now.hour,
                'day_of_week': now.weekday(),
                'month': now.month,
                'station_type': 'city_center',  # Could be enhanced
                'charger_type': station.charger_types.split(',')[0] if station.charger_types else 'Type2',
                'num_ports': station.num_ports,
                'temperature': 25.0,
                'weather_condition': weather_condition,
                'weather_severity': weather_severity,
                'traffic_level': traffic_level,
                'is_holiday': is_holiday,
                'is_weekend': now.weekday() >= 5,
                'base_load': 0.5
            }
            
            # Make prediction
            prediction_result = predictor.predict(features)
            wait_time = prediction_result['predicted_wait_time_minutes']
            
            results.append({
                "station_id": station.id,
                "station_name": station.name,
                "distance_km": round(distance_km, 2),
                "charger_types": station.charger_types,
                "predicted_wait_time_minutes": round(wait_time, 1),
                "wait_time_category": get_wait_time_category(wait_time),
                "confidence": round(prediction_result['confidence'], 3),
                "num_ports": station.num_ports,
                "latitude": station.latitude,
                "longitude": station.longitude
            })
        
        # Sort by wait time
        results.sort(key=lambda x: x['predicted_wait_time_minutes'])
        
        return {
            "location": {"lat": user_lat, "lon": user_lon},
            "timestamp": now.isoformat(),
            "model_version": "1.0",
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
