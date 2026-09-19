"""
ML-based waiting time prediction model for EV charging stations.
Uses XGBoost with features like time, day, traffic, station load, weather, etc.
"""

import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import random
import math

try:
    import sys
    sys.path.append('C:\\Users\\LENOVO\\AppData\\Local\\Programs\\Python\\Python36\\Lib\\site-packages')
    import xgboost as xgb
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.preprocessing import StandardScaler
    XGBOOST_AVAILABLE = True
    print("XGBoost successfully loaded!")
except ImportError as e:
    print(f"XGBoost import failed: {e}, falling back to RandomForest")
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.preprocessing import StandardScaler
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not available, falling back to RandomForest")


class WaitingTimePredictor:
    """
    ML model for predicting EV charging station waiting times.
    """
    
    def __init__(self, model_path: str = "backend/app/models/waiting_time/model.joblib"):
        self.model_path = model_path
        self.model = None
        self.scaler = StandardScaler()
        self.feature_importance = None
        self.is_trained = False
        
    def generate_synthetic_data(self, n_samples: int = 10000) -> pd.DataFrame:
        """
        Generate synthetic training data for the waiting time prediction model.
        Creates realistic patterns based on time, day, weather, traffic, etc.
        """
        print(f"Generating {n_samples} synthetic samples...")
        
        data = []
        random.seed(42)
        np.random.seed(42)
        
        # Station characteristics
        station_types = ['mall', 'highway', 'city_center', 'residential', 'office']
        charger_types = ['CCS2', 'Type2', 'CHAdeMO', 'Tesla_Supercharger']
        
        for i in range(n_samples):
            # Time features
            hour = random.randint(0, 23)
            day_of_week = random.randint(0, 6)  # 0=Monday, 6=Sunday
            month = random.randint(1, 12)
            
            # Station features
            station_type = random.choice(station_types)
            charger_type = random.choice(charger_types)
            num_ports = random.randint(2, 8)
            
            # Weather features (simplified)
            temperature = random.uniform(-10, 40)  # Celsius
            weather_condition = random.choice(['sunny', 'cloudy', 'rainy', 'snowy'])
            weather_severity = random.uniform(0, 1)
            
            # Traffic features
            traffic_level = random.uniform(0, 1)
            is_holiday = random.choice([True, False])
            is_weekend = day_of_week >= 5
            
            # Historical load
            base_load = random.uniform(0.1, 0.9)
            
            # Calculate realistic waiting time based on features
            wait_time = self._calculate_realistic_wait_time(
                hour, day_of_week, month, station_type, charger_type, num_ports,
                temperature, weather_condition, weather_severity, traffic_level,
                is_holiday, is_weekend, base_load
            )
            
            data.append({
                'hour': hour,
                'day_of_week': day_of_week,
                'month': month,
                'station_type': station_type,
                'charger_type': charger_type,
                'num_ports': num_ports,
                'temperature': temperature,
                'weather_condition': weather_condition,
                'weather_severity': weather_severity,
                'traffic_level': traffic_level,
                'is_holiday': is_holiday,
                'is_weekend': is_weekend,
                'base_load': base_load,
                'wait_time_minutes': wait_time
            })
        
        return pd.DataFrame(data)
    
    def _calculate_realistic_wait_time(self, hour, day_of_week, month, station_type, 
                                     charger_type, num_ports, temperature, weather_condition,
                                     weather_severity, traffic_level, is_holiday, is_weekend, base_load):
        """Calculate realistic waiting time based on various factors."""
        
        # Base waiting time
        base_wait = 5.0
        
        # Time-based factors
        if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
            time_factor = 1.5
        elif 22 <= hour or hour <= 6:  # Night hours
            time_factor = 0.3
        else:
            time_factor = 1.0
            
        # Day of week factor
        if is_weekend:
            day_factor = 1.2
        else:
            day_factor = 1.0
            
        # Station type factor
        station_factors = {
            'mall': 1.3,
            'highway': 1.1,
            'city_center': 1.5,
            'residential': 0.8,
            'office': 1.2
        }
        station_factor = station_factors.get(station_type, 1.0)
        
        # Charger type factor
        charger_factors = {
            'CCS2': 0.8,  # Fast charging
            'Type2': 1.2,  # Slower
            'CHAdeMO': 0.9,
            'Tesla_Supercharger': 0.7  # Very fast
        }
        charger_factor = charger_factors.get(charger_type, 1.0)
        
        # Weather factor
        weather_factors = {
            'sunny': 1.0,
            'cloudy': 1.1,
            'rainy': 1.3,
            'snowy': 1.5
        }
        weather_factor = weather_factors.get(weather_condition, 1.0) * (1 + weather_severity * 0.5)
        
        # Traffic factor
        traffic_factor = 1 + traffic_level * 0.8
        
        # Load factor (exponential increase with load)
        load_factor = 1 + (base_load ** 2) * 3
        
        # Port availability factor
        port_factor = max(0.5, 1 - (num_ports - 2) * 0.1)
        
        # Holiday factor
        holiday_factor = 1.3 if is_holiday else 1.0
        
        # Calculate final waiting time
        wait_time = (base_wait * time_factor * day_factor * station_factor * 
                    charger_factor * weather_factor * traffic_factor * 
                    load_factor * port_factor * holiday_factor)
        
        # Add some randomness
        wait_time *= (1 + random.uniform(-0.2, 0.2))
        
        return max(0, min(120, wait_time))  # Cap between 0 and 120 minutes
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features for training/prediction."""
        
        # Create feature matrix
        feature_columns = [
            'hour', 'day_of_week', 'month', 'num_ports', 'temperature',
            'weather_severity', 'traffic_level', 'is_holiday', 'is_weekend', 'base_load'
        ]
        
        # One-hot encode categorical variables
        df_encoded = df.copy()
        
        # Station type encoding
        station_type_dummies = pd.get_dummies(df['station_type'], prefix='station_type')
        df_encoded = pd.concat([df_encoded, station_type_dummies], axis=1)
        
        # Charger type encoding
        charger_type_dummies = pd.get_dummies(df['charger_type'], prefix='charger_type')
        df_encoded = pd.concat([df_encoded, charger_type_dummies], axis=1)
        
        # Weather condition encoding
        weather_dummies = pd.get_dummies(df['weather_condition'], prefix='weather')
        df_encoded = pd.concat([df_encoded, weather_dummies], axis=1)
        
        # Combine all features
        all_feature_columns = feature_columns + list(station_type_dummies.columns) + \
                             list(charger_type_dummies.columns) + list(weather_dummies.columns)
        
        X = df_encoded[all_feature_columns].values
        y = df_encoded['wait_time_minutes'].values
        
        return X, y
    
    def train(self, n_samples: int = 10000, test_size: float = 0.2):
        """Train the waiting time prediction model."""
        print("Training waiting time prediction model...")
        
        # Generate synthetic data
        df = self.generate_synthetic_data(n_samples)
        print(f"Generated dataset with {len(df)} samples")
        
        # Prepare features
        X, y = self.prepare_features(df)
        print(f"Feature matrix shape: {X.shape}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        if XGBOOST_AVAILABLE:
            print("Training XGBoost model...")
            self.model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                n_jobs=-1
            )
        else:
            print("Training RandomForest model...")
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate model
        y_pred = self.model.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        print(f"Model evaluation:")
        print(f"  MAE: {mae:.2f} minutes")
        print(f"  MSE: {mse:.2f}")
        print(f"  R²: {r2:.3f}")
        
        # Get feature importance
        if hasattr(self.model, 'feature_importances_'):
            self.feature_importance = dict(zip(
                self.get_feature_names(), 
                self.model.feature_importances_
            ))
            print(f"Top 5 most important features:")
            sorted_features = sorted(self.feature_importance.items(), 
                                   key=lambda x: x[1], reverse=True)
            for feature, importance in sorted_features[:5]:
                print(f"  {feature}: {importance:.3f}")
        
        self.is_trained = True
        
        # Save model
        self.save_model()
        
        return {
            'mae': mae,
            'mse': mse,
            'r2': r2,
            'feature_importance': self.feature_importance
        }
    
    def get_feature_names(self) -> List[str]:
        """Get feature names for the model."""
        return [
            'hour', 'day_of_week', 'month', 'num_ports', 'temperature',
            'weather_severity', 'traffic_level', 'is_holiday', 'is_weekend', 'base_load',
            'station_type_mall', 'station_type_highway', 'station_type_city_center',
            'station_type_residential', 'station_type_office',
            'charger_type_CCS2', 'charger_type_Type2', 'charger_type_CHAdeMO',
            'charger_type_Tesla_Supercharger',
            'weather_sunny', 'weather_cloudy', 'weather_rainy', 'weather_snowy'
        ]
    
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict waiting time for given features."""
        if not self.is_trained:
            self.load_model()
        
        if not self.is_trained:
            raise ValueError("Model not trained and no saved model found")
        
        # Convert features to DataFrame
        df = pd.DataFrame([features])
        
        # Prepare features (same as training)
        X, _ = self.prepare_features(df)
        X_scaled = self.scaler.transform(X)
        
        # Make prediction
        prediction = self.model.predict(X_scaled)[0]
        confidence = self._calculate_confidence(prediction, features)
        
        return {
            'predicted_wait_time_minutes': max(0, prediction),
            'confidence': confidence,
            'feature_importance': self.feature_importance
        }
    
    def _calculate_confidence(self, prediction: float, features: Dict[str, Any]) -> float:
        """Calculate confidence score for prediction."""
        # Simple confidence based on how close to typical ranges
        if prediction < 5:
            confidence = 0.9
        elif prediction < 15:
            confidence = 0.8
        elif prediction < 30:
            confidence = 0.7
        else:
            confidence = 0.6
        
        # Adjust based on feature completeness
        required_features = ['hour', 'day_of_week', 'num_ports', 'base_load']
        missing_features = sum(1 for f in required_features if f not in features)
        confidence *= (1 - missing_features * 0.1)
        
        return max(0.1, min(0.95, confidence))
    
    def save_model(self):
        """Save the trained model and scaler."""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_importance': self.feature_importance,
            'is_trained': self.is_trained
        }
        
        joblib.dump(model_data, self.model_path)
        print(f"Model saved to {self.model_path}")
    
    def load_model(self):
        """Load the trained model and scaler."""
        if os.path.exists(self.model_path):
            model_data = joblib.load(self.model_path)
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_importance = model_data['feature_importance']
            self.is_trained = model_data['is_trained']
            print(f"Model loaded from {self.model_path}")
        else:
            print(f"No saved model found at {self.model_path}")


def train_model():
    """Train and save the waiting time prediction model."""
    predictor = WaitingTimePredictor()
    results = predictor.train(n_samples=15000)
    return results


if __name__ == "__main__":
    # Train the model when run directly
    print("Training waiting time prediction model...")
    results = train_model()
    print("Training completed!")

