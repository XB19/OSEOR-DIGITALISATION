#!/bin/sh
# Migrations + collectstatic : uniquement sur le service qui porte
# RUN_MIGRATIONS=1 (le service "api"), pour éviter que l'API et le
# WebSocket ne se marchent dessus au démarrage.
set -e

if [ "$RUN_MIGRATIONS" = "1" ]; then
  echo "Application des migrations..."
  python manage.py migrate --noinput

  echo "Collecte des fichiers statiques..."
  python manage.py collectstatic --noinput
fi

exec "$@"
