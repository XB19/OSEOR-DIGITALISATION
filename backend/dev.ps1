# Lance l'environnement de dev OSEOR :
#  - API HTTP en WSGI (waitress) sur le port 8000  -> rapide (connexions DB persistantes)
#  - WebSocket en daphne (ASGI) sur le port 8001   -> notifications temps reel
#
# Usage :  .\dev.ps1
# (Le frontend Angular se lance a part :  cd ..\frontend ; npm start)

$ErrorActionPreference = "Stop"
$racine = $PSScriptRoot

Write-Host "Demarrage API WSGI (port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$racine'; python serve_api.py"

Write-Host "Demarrage WebSocket daphne (port 8001)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$racine'; daphne -p 8001 config.asgi:application"

Write-Host ""
Write-Host "OK :" -ForegroundColor Green
Write-Host "  API HTTP   -> http://127.0.0.1:8000"
Write-Host "  WebSocket  -> ws://127.0.0.1:8001/ws"
Write-Host "  Frontend   -> cd ..\frontend ; npm start  (http://localhost:4200)"
