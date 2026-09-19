@echo off
echo ========================================
echo    EVisionAI Server Starter
echo ========================================
echo.
echo Stopping any existing servers on port 8080...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo.
echo Starting server...
echo Server will be available at: http://localhost:8080
echo Press Ctrl+C to stop the server
echo.
npx http-server . -p 8080 --cors -a 0.0.0.0 --no-dotfiles
pause
