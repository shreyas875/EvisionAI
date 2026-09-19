#!/usr/bin/env python3
"""
Training script for the EVisionAI waiting time prediction model.
Run this script to train and save the ML model.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.waiting_time.model import train_model

if __name__ == "__main__":
    print("=" * 60)
    print("EVisionAI Waiting Time Prediction Model Training")
    print("=" * 60)
    
    try:
        print("Starting model training...")
        results = train_model()
        
        print("\n" + "=" * 60)
        print("Training completed successfully!")
        print("=" * 60)
        print(f"Model Performance:")
        print(f"  Mean Absolute Error: {results['mae']:.2f} minutes")
        print(f"  Mean Squared Error: {results['mse']:.2f}")
        print(f"  R² Score: {results['r2']:.3f}")
        
        if results.get('feature_importance'):
            print(f"\nTop 5 Most Important Features:")
            sorted_features = sorted(results['feature_importance'].items(), 
                                   key=lambda x: x[1], reverse=True)
            for i, (feature, importance) in enumerate(sorted_features[:5], 1):
                print(f"  {i}. {feature}: {importance:.3f}")
        
        print(f"\nModel saved to: backend/app/models/waiting_time/model.joblib")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error during training: {e}")
        sys.exit(1)
