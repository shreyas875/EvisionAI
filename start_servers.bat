@echo off
echo Starting EVisionAI Servers...
echo.

echo Starting ML API Server (Python)...
start "ML API Server" cmd /k "python ml_api_server.py"

echo Waiting for ML server to start...
timeout /t 3 /nobreak > nul

echo Starting Main Server (Node.js)...
start "Main Server" cmd /k "node server.js"

echo.
echo Both servers are starting...
echo ML API Server: http://localhost:8000
echo Main Server: http://localhost:8080
echo.
echo Press any key to exit...
pause > nul
