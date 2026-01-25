#!/bin/sh

# Fail fast
set -e

echo "🚀 [Entrypoint] Container started."

if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "🛠️ [Entrypoint] Migration Mode Detected."

    echo "   -> Running Database Migrations..."
    flask db upgrade

    echo "   -> Running Data Bootstrap (Ingestion + AI)..."
    flask bootstrap
else
    echo "⏩ [Entrypoint] Skipping Migrations (Worker or Replica mode)."
fi

echo "🔥 [Entrypoint] Executing command..."
exec "$@"