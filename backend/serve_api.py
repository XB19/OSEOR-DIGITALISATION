"""
Serveur HTTP de l'API en WSGI (waitress).

Pourquoi WSGI plutôt que daphne : sous ASGI, Django n'a pas de connexions
DB persistantes, donc chaque requête rouvre une connexion (~1,2 s de
latence vers un Postgres distant). En WSGI, les connexions persistent
(CONN_MAX_AGE) → l'API répond 2 à 3× plus vite.

Les WebSockets (notifications temps réel) restent servis par daphne :
    daphne -p 8001 config.asgi:application

Lancement : python serve_api.py

Réglages par variables d'environnement :

    API_HOST     interface d'écoute (défaut 0.0.0.0)
    API_PORT     port (défaut 8000)
    API_THREADS  threads waitress (défaut 4)

L'écoute par défaut est 0.0.0.0 et non 127.0.0.1 : ce script est le point
d'entrée du conteneur `api` (voir backend/Dockerfile). Lié à la seule
boucle locale, le service n'était joignable que depuis l'intérieur de son
propre conteneur — nginx recevait « connection refused », le port publié
8000 ne menait nulle part, et le frontend Angular ne pouvait appeler
aucune API. Ce qui est exposé au réseau se décide dans docker-compose.yml
et par ALLOWED_HOSTS, pas ici.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from waitress import serve  # noqa: E402
from django.conf import settings  # noqa: E402
from config.wsgi import application  # noqa: E402


def parametres_serveur(environnement=None):
    """Interface, port et nombre de threads, lus dans l'environnement."""
    environnement = os.environ if environnement is None else environnement

    return (
        environnement.get("API_HOST", "0.0.0.0"),
        int(environnement.get("API_PORT", "8000")),
        int(environnement.get("API_THREADS", "4")),
    )


# En dev, sert aussi les fichiers statiques (CSS de l'admin Django).
if settings.DEBUG:
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    application = StaticFilesHandler(application)

if __name__ == "__main__":
    hote, port, threads = parametres_serveur()

    print(f"API HTTP (WSGI/waitress) sur http://{hote}:{port}")
    print("Pensez à lancer aussi le WebSocket : daphne -p 8001 config.asgi:application")

    serve(application, host=hote, port=port, threads=threads)
