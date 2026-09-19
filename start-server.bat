@echo off
echo Starting EV Charging Stations Server...
echo.
echo Server will be available at: http://localhost:8080
echo Press Ctrl+C to stop the server
echo.
npx http-server . -p 8080 -a localhost --cors --no-dotfiles
pause
