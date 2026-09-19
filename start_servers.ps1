Write-Host "Starting EVisionAI Servers..." -ForegroundColor Green
Write-Host ""

Write-Host "Starting ML API Server (Python)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python ml_api_server.py"

Write-Host "Waiting for ML server to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host "Starting Main Server (Node.js)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "node server.js"

Write-Host ""
Write-Host "Both servers are starting..." -ForegroundColor Green
Write-Host "ML API Server: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Main Server: http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor White
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
