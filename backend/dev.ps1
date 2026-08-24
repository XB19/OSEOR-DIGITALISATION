# Lance l'environnement de dev OSEOR (variante 2 process, plus rapide sur l'API) :
#  - API HTTP en WSGI (waitress) sur le port 8000  -> rapide (connexions DB persistantes)
#  - WebSocket en daphne (ASGI) sur le port 8001   -> notifications temps reel
#
# /!\ IMPORTANT : ces 2 process ne partagent PAS leurs notifications tant que
# REDIS_URL n'est pas configure dans .env (chacun a sa propre file en memoire,
# isolee de l'autre -> les notifications sont bien creees en base mais
# n'arrivent JAMAIS en temps reel au navigateur). Sans Redis local, preferez
# simplement `python manage.py runserver` (un seul process, sert l'API ET le
# WebSocket ensemble, aucune configuration supplementaire requise) et pointez
# frontend/src/environments/environment.ts vers le port 8000 pour les deux.
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
