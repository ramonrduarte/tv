#!/bin/sh
set -e

echo "Aplicando migrations..."
python manage.py migrate --noinput

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "Agendando conferência dos painéis (a frequência fica na tela de Conferência)..."
(
  while true; do
    sleep 60
    python manage.py conferir_paineis || true
    sleep 3540
  done
) &

echo "Iniciando servidor..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8080 \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
