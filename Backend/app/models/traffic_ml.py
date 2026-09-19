import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any

try:
    import sys
    sys.path.append('C:\\Users\\LENOVO\\AppData\\Local\\Programs\\Python\\Python36\\Lib\\site-packages')
    import xgboost as xgb
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    XGBOOST_AVAILABLE = True
    print("XGBoost successfully loaded for traffic!")
except ImportError as e:
    print(f"XGBoost import failed for traffic: {e}, falling back to RandomForest")
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not available.")

class TrafficDelayRegressor:
    def __init__(self, model_path="backend/app/models/traffic_ml.joblib"):
        self.model_path = model_path
        self.model = None
        self.is_trained = False

    def generate_synthetic_data(self, n_samples=6000):
        arr = []
        np.random.seed(42)
        for _ in range(n_samples):
            distance = np.random.uniform(0.5, 45)  # km
            hour = np.random.randint(0,24)
            day_of_week = np.random.randint(0,7)
            weather = np.random.choice([0,1,2]) # 0=sunny,1=rainy,2=foggy
            traffic_density = np.random.uniform(0.2,2.5)  # traffic load
            is_holiday = np.random.choice([0,1])

            base_time = distance / np.random.uniform(30,80) * 60  # base mins
            rush = 1.25 if 7<=hour<=10 or 17<=hour<=20 else 1.0
            t_factor = 1.4 if traffic_density>1.3 else (1.2 if traffic_density>0.7 else 1.0)
            w_factor = {0:1.0,1:1.18,2:1.35}[weather]
            h_factor = 1.18 if is_holiday else 1.0

            delay = base_time * rush * t_factor * w_factor * h_factor
            delay += np.random.uniform(-4,4)

            arr.append({
                "distance":distance,
                "hour":hour,
                "day_of_week":day_of_week,
                "weather":weather,
                "traffic_density":traffic_density,
                "is_holiday":is_holiday,
                "delay_min":max(1,delay)
            })
        return pd.DataFrame(arr)

    def train(self, n_samples=6000):
        df = self.generate_synthetic_data(n_samples)
        X = df[["distance","hour","day_of_week","weather","traffic_density","is_holiday"]].values
        y = df["delay_min"].values
        X_train, X_test, y_train, y_test = train_test_split(X,y,test_size=0.23,random_state=42)
        self.model = xgb.XGBRegressor(n_estimators=60,max_depth=7,learning_rate=0.19,random_state=42) if XGBOOST_AVAILABLE else None
        if self.model is not None:
            self.model.fit(X_train, y_train)
            y_pred = self.model.predict(X_test)
            print(f"TrafficDelayRegressor MAE: {mean_absolute_error(y_test,y_pred):.2f}  R^2: {r2_score(y_test,y_pred):.3f}")
            self.is_trained = True
            self.save_model()
        else:
            # Fallback to RandomForest
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.model.fit(X_train, y_train)
            y_pred = self.model.predict(X_test)
            print(f"TrafficDelayRegressor (RandomForest) MAE: {mean_absolute_error(y_test,y_pred):.2f}  R^2: {r2_score(y_test,y_pred):.3f}")
            self.is_trained = True
            self.save_model()

    def save_model(self):
        joblib.dump(self.model, self.model_path)
    def load_model(self):
        self.model = joblib.load(self.model_path)
        self.is_trained = True

    def predict(self, features: Dict[str,Any]) -> float:
        if not self.is_trained:
            self.load_model()
        X = np.array([[features[k] for k in ["distance","hour","day_of_week","weather","traffic_density","is_holiday"]]])
        pred = float(self.model.predict(X)[0])
        return max(1, pred)

def train_traffic_model():
    reg = TrafficDelayRegressor()
    reg.train()
    print("TrafficDelayRegressor trained and saved.")

if __name__=="__main__":
    train_traffic_model()
