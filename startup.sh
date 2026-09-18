#!/bin/bash
# Comando de inicio para Service (Linux - Python)
# Configurar en Azure Portal > Configuración > Comando de inicio
# O directamente: gunicorn backend.main:backend -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120

gunicorn backend.main:backend \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
