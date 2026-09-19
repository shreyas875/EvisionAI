import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List,Dict,Any

try:
    import sys
    sys.path.append('C:\\Users\\LENOVO\\AppData\\Local\\Programs\\Python\\Python36\\Lib\\site-packages')
    import xgboost as xgb
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    XGBOOST_AVAILABLE = True
    print("XGBoost successfully loaded for routing!")
except ImportError as e:
    print(f"XGBoost import failed for routing: {e}, falling back to RandomForest")
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not available for route ML.")

class StopRecommender:
    def __init__(self, model_path="backend/app/models/routing_ml.joblib"):
        self.model_path = model_path
        self.model = None
        self.is_trained = False

    def generate_synthetic_data(self, n_samples=3000, n_stations=10):
        out = []
        np.random.seed(77)
        for _ in range(n_samples):
            station_choices = np.arange(n_stations)
            dist = np.random.uniform(3,60,size=n_stations)
            battery = np.random.randint(10, 45)
            charger = np.random.choice([0,1,2,3])  # 0=ccs2,1=cha,2=type2,3=tesla
            hour = np.random.randint(0,24)
            dow = np.random.randint(0,7)
            ports = np.random.randint(2,8,size=n_stations)
            # pick best: closer when battery low, more ports, ccs2/tesla preferred
            best = np.argmin(dist + (30-battery)*0.25 - ports*1.5 + (charger==2)*6)
            for i in range(n_stations):
                out.append({
                    'station_ix': i,
                    'dist':dist[i],
                    'battery':battery,
                    'charger':charger,
                    'hour':hour,
                    'day_of_week':dow,
                    'ports':ports[i],
                    'chosen': int(i==best)
                })
        return pd.DataFrame(out)

    def train(self, n_samples=3000, n_stations=10):
        df = self.generate_synthetic_data(n_samples, n_stations)
        X = df[['station_ix','dist','battery','charger','hour','day_of_week','ports']].values
        y = df['chosen'].values
        X_train,X_test,y_train,y_test = train_test_split(X,y,test_size=0.22,random_state=42)
        self.model = xgb.XGBClassifier(n_estimators=70,max_depth=5,learning_rate=0.14,random_state=42,n_jobs=1) if XGBOOST_AVAILABLE else None
        if self.model is not None:
            self.model.fit(X_train,y_train)
            preds = self.model.predict(X_test)
            print(f"StopRecommender Accuracy: {accuracy_score(y_test,preds):.3f}")
            self.is_trained = True
            self.save_model()
        else:
            # Fallback to RandomForest
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.model.fit(X_train, y_train)
            preds = self.model.predict(X_test)
            print(f"StopRecommender (RandomForest) Accuracy: {accuracy_score(y_test,preds):.3f}")
            self.is_trained = True
            self.save_model()
    def save_model(self):
        joblib.dump(self.model, self.model_path)
    def load_model(self):
        self.model = joblib.load(self.model_path)
        self.is_trained = True

    def suggest(self, stations:List[Dict], battery:int, charger:str, hour:int, dow:int):
        charger_map = {'ccs2':0,'cha':1,'type2':2,'tesla':3}
        charger_ix = charger_map.get((charger or '').lower(),0)
        arr = []
        for i,s in enumerate(stations):
            arr.append([i,s['distance'],battery,charger_ix,hour,dow,s['num_ports']])
        if not arr:
            return None
        if not self.is_trained:
            self.load_model()
        proba = self.model.predict_proba(np.array(arr))[:,1]
        ix = int(np.argmax(proba))
        return stations[ix].copy()  # best

def train_stop_model():
    rec = StopRecommender()
    rec.train()
    print("StopRecommender trained and saved.")

if __name__=="__main__":
    train_stop_model()
