export const environment = {
  production: false,
  // Dev local simple : `python manage.py runserver` sert l'API ET le
  // WebSocket sur le MÊME process/port (channels+daphne sont intégrés au
  // runserver de Django). Pas besoin de lancer un second process.
  //
  // ⚠️ Si vous utilisez plutôt le split waitress (serve_api.py, port 8000)
  // + daphne séparé (port 8001) via dev.ps1, il faut IMPÉRATIVEMENT
  // configurer REDIS_URL dans le backend (.env) — sinon les deux process
  // ont chacun leur propre file de notifications en mémoire, qui ne se
  // synchronisent jamais : les notifications sont créées en base mais
  // n'arrivent jamais en temps réel. Voir REDIS_URL dans backend/.env.example.
  apiUrl: 'http://127.0.0.1:8000/api',
  wsUrl: 'ws://127.0.0.1:8000/ws',
};
