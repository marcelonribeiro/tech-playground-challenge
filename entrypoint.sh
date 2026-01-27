#!/bin/sh
set -e

echo "🚀 [Entrypoint] Container started."

if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "🛠️ [Entrypoint] Migration Mode Detected."

    echo "   -> Running Database Migrations..."
    flask db upgrade

    echo "   -> Running Unified Bootstrap (Ingestion + AI)..."
    flask bootstrap
else
    echo "⏩ [Entrypoint] Skipping Migrations (Worker/Replica mode)."
fi

echo "🔥 [Entrypoint] Executing command..."
exec "$@"