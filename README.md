# EVisionAI - EV Charging Station Locator & ML Predictor

![EVisionAI](https://img.shields.io/badge/EVision-AI-success?style=for-the-badge&logo=electric)
![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python)
![Node.js](https://img.shields.io/badge/Node.js-14+-green?style=for-the-badge&logo=node.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.68.1-009688?style=for-the-badge&logo=fastapi)

## Overview

Welcome to **EVisionAI**, an advanced, full-stack web application designed to help users locate nearby electric vehicle (EV) charging stations using the **TomTom Maps API**, and accurately predict station waiting times using **Machine Learning (XGBoost & Scikit-learn)**. 

Whether you are a guest looking for a quick charge or a registered user managing your routes, EVisionAI provides real-time predictions, mapped locations, and color-coded availability data.

---

## Architecture & Tech Stack

This project uses a dual-server architecture:
1. **Frontend Server (Node.js)**: A lightweight Node.js server (`server.js`) running on port `8080` serves the vanilla HTML/CSS/JS frontend files and acts as a reverse proxy.
2. **AI Backend Server (Python/FastAPI)**: An automated Python backend running on port `8000` via `uvicorn`. It handles all database operations (SQLite & SQLAlchemy) and the Machine Learning prediction logic.

### Key Technologies 
- **Frontend**: HTML5, Vanilla JavaScript, CSS3
- **Map & Routing**: TomTom Maps Web SDK (`@tomtom-international/web-sdk-maps`)
- **Backend (API)**: Python, FastAPI, Uvicorn, SQLAlchemy
- **Machine Learning**: XGBoost, Scikit-learn, Pandas, Numpy, Joblib
- **Database**: SQLite (`evisionai.db`)

---

## ⚙️ Features

- 🗺️ **Live Map Integration**: Find charging stations dynamically using TomTom's SDK.
- 🤖 **AI Wait-Time Predictions**: The XGBoost model predicts wait times based on 20+ real-time features including time of day, weather conditions, traffic severity, and station types.
- 🚦 **Color-coded Availability**:
  - 🟢 **Green**: < 5 minutes (Low wait time)
  - 🟡 **Yellow**: 5-15 minutes (Moderate congestion)
  - 🔴 **Red**: > 15 minutes (Busy station)
- 👤 **Dual Dashboards**: Dedicated interfaces for Guests and logged-in Users.
- ⚡ **Auto-starting Backend**: The Node.js server automatically spins up the Python API backend for you upon start!

---

## 🚀 Installation & Setup

### Prerequisites
Make sure you have both [Node.js](https://nodejs.org/) and [Python (3.8+)](https://www.python.org/) installed on your machine.

### 1. Clone the repository
```bash
git clone https://github.com/bhushan-22/EVisionAI.git
cd EVisionAI
```

### 2. Setup the Python Virtual Environment
It is highly recommended to configure the python virtual environment to handle the AI dependencies.
```bash
# Enter the backend directory
cd backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install AI/Backend requirements
pip install -r requirements.txt

# Go back to the root folder
cd ..
```

### 3. Install Node.js Dependencies
```bash
npm install
```

---

## 💻 Running the Application

You only need to start the main Node server; it is configured to **automatically launch the Python AI backend**.

```bash
npm start
# OR
node server.js
```

### Access Points:
- 📱 **Welcome Page**: [http://localhost:8080/welcome.html](http://localhost:8080/welcome.html)
- 🏠 **Main App**: [http://localhost:8080/index.html](http://localhost:8080/index.html)
- 🎯 **Guest Dashboard**: [http://localhost:8080/guest-dashboard.html](http://localhost:8080/guest-dashboard.html)
- 🤖 **AI Backend API**: Local proxy runs at `http://localhost:8080/stations/*`

---

## 🧠 Machine Learning Details

Our ML Model is trained dynamically using synthetic data to predict wait times using features such as:
- **Environmental**: Weather conditions, severity, and temperature.
- **Contextual**: Traffic levels, holiday indicators, time-of-day.
- **Station-specific**: Charger type (CCS2, Type2, Tesla), port count.

> *(If your predictions aren't loading, you can retrain the model locally by running `python backend/train_model.py` or sending a POST request to `/stations/train_model`.)*

For full details on the machine learning component, see `ML_WAITING_TIME_SYSTEM.md`.
