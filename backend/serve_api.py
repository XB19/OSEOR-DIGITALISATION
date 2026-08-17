"""
Serveur HTTP de l'API en WSGI (waitress) — DEV.

Pourquoi : sous daphne (ASGI), Django n'a pas de connexions DB persistantes,
donc chaque requête rouvre une connexion à Supabase (~1,2s de latence depuis
l'Afrique). En WSGI, les connexions persistent (CONN_MAX_AGE) → l'API répond
2 à 3× plus vite en dev.

Les WebSockets (notifications temps réel) restent servis par daphne :
    daphne -p 8001 config.asgi:application

Lancement : python serve_api.py
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from waitress import serve  # noqa: E402
from django.conf import settings  # noqa: E402
from config.wsgi import application  # noqa: E402

# En dev, sert aussi les fichiers statiques (CSS de l'admin Django).
if settings.DEBUG:
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    application = StaticFilesHandler(application)

if __name__ == "__main__":
    print("API HTTP (WSGI/waitress) sur http://127.0.0.1:8000")
    print("Pensez à lancer aussi le WebSocket : daphne -p 8001 config.asgi:application")
    # Peu de threads en dev : chaque thread garde 1 connexion DB persistante,
    # donc moins de threads = démarrage à chaud plus rapide (mono-utilisateur).
    serve(application, host="127.0.0.1", port=8000, threads=3)
