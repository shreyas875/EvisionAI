#!/usr/bin/env python3
"""
Test script to verify ML models work correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all ML imports work."""
    try:
        from app.models.waiting_time.model import WaitingTimePredictor
        print("✓ WaitingTimePredictor import successful")
        
        from app.models.traffic_ml import TrafficDelayRegressor
        print("✓ TrafficDelayRegressor import successful")
        
        from app.models.routing_ml import StopRecommender
        print("✓ StopRecommender import successful")
        
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_waiting_time_model():
    """Test waiting time prediction."""
    try:
        from app.models.waiting_time.model import WaitingTimePredictor
        
        predictor = WaitingTimePredictor()
        
        # Test prediction with correct feature names
        features = {
            'hour': 14,
            'day_of_week': 1,
            'month': 6,
            'num_ports': 4,
            'temperature': 25.0,
            'weather_severity': 0.3,
            'traffic_level': 0.4,
            'is_holiday': False,
            'is_weekend': False,
            'base_load': 0.7,
            'station_type': 'highway',
            'charger_type': 'CCS2',
            'weather_condition': 'sunny'
        }
        
        result = predictor.predict(features)
        print(f"✓ Waiting time prediction: {result['predicted_wait_time_minutes']:.1f} minutes")
        print(f"  Confidence: {result['confidence']:.2f}")
        return True
        
    except Exception as e:
        print(f"✗ Waiting time model error: {e}")
        return False

def test_traffic_model():
    """Test traffic delay prediction."""
    try:
        from app.models.traffic_ml import TrafficDelayRegressor
        
        predictor = TrafficDelayRegressor()
        
        features = {
            'distance': 15.5,
            'hour': 14,
            'day_of_week': 1,
            'is_holiday': False,
            'weather': 0.3,
            'traffic_density': 0.6
        }
        
        delay = predictor.predict(features)
        print(f"✓ Traffic prediction: {delay:.1f} minutes delay")
        return True
        
    except Exception as e:
        print(f"✗ Traffic model error: {e}")
        return False

def test_routing_model():
    """Test stop recommendation."""
    try:
        from app.models.routing_ml import StopRecommender
        
        recommender = StopRecommender()
        
        candidates = [
            {
                'station_id': 1,
                'distance_from_start_km': 5.2,
                'num_ports': 4,
                'charger_type_match': 1,
                'user_battery_percentage': 25,
                'hour_of_day': 14,
                'day_of_week': 1,
                'is_holiday': False
            },
            {
                'station_id': 2,
                'distance_from_start_km': 8.1,
                'num_ports': 6,
                'charger_type_match': 0,
                'user_battery_percentage': 25,
                'hour_of_day': 14,
                'day_of_week': 1,
                'is_holiday': False
            }
        ]
        
        # Convert candidates to the format expected by suggest method
        stations = []
        for c in candidates:
            stations.append({
                'distance': c['distance_from_start_km'],
                'num_ports': c['num_ports']
            })
        
        result = recommender.suggest(
            stations=stations,
            battery=candidates[0]['user_battery_percentage'],
            charger='ccs2',
            hour=candidates[0]['hour_of_day'],
            dow=candidates[0]['day_of_week']
        )
        print(f"✓ Stop recommendation: {result is not None}")
        if result:
            print(f"  Best stop: {result.get('name', 'Unknown')} at {result.get('distance', 0):.1f}km")
        return True
        
    except Exception as e:
        print(f"✗ Routing model error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("EVisionAI ML Models Test")
    print("=" * 60)
    
    success = True
    
    print("\n1. Testing imports...")
    success &= test_imports()
    
    print("\n2. Testing waiting time model...")
    success &= test_waiting_time_model()
    
    print("\n3. Testing traffic model...")
    success &= test_traffic_model()
    
    print("\n4. Testing routing model...")
    success &= test_routing_model()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ All ML models working correctly!")
    else:
        print("✗ Some ML models have issues")
    print("=" * 60)
