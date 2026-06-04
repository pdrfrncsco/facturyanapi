#!/bin/bash
set -e

# Esperar pelo Postgres se necessário
# ./wait-for-it.sh db:5432

# Colectar ficheiros estáticos
python manage.py collectstatic --noinput

# Executar migrações
python manage.py migrate --noinput

# Iniciar Gunicorn (Produção) ou Runserver (Dev)
if [ "$DJANGO_DEBUG" = "false" ]; then
    echo "Iniciando em modo PRODUÇÃO com Gunicorn..."
    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --threads 2 \
        --access-logfile - \
        --error-logfile -
else
    echo "Iniciando em modo DESENVOLVIMENTO..."
    exec python manage.py runserver 0.0.0.0:8000
fi
