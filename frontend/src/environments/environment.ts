export const environment = {
  production: false,
  // API HTTP servie par WSGI (waitress) — connexions DB persistantes (rapide)
  apiUrl: 'http://127.0.0.1:8000/api',
  // WebSocket servi par daphne (ASGI) sur un port dédié
  wsUrl: 'ws://127.0.0.1:8001/ws',
};
