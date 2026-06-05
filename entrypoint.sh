#!/bin/sh
set -e

echo "=== Collectabase startup ==="

# Ensure data directory exists
mkdir -p /app/data /app/uploads

# Run Alembic migrations – creates all tables on first run, applies future migrations safely
echo "Running database migrations..."
cd /app
python -m alembic --config backend/alembic.ini upgrade head
echo "Migrations complete."

# Start the application. If TLS cert+key are provided, uvicorn terminates HTTPS
# itself (no reverse proxy needed for a single app); otherwise it serves plain HTTP.
SSL_ARGS=""
if [ -n "$SSL_CERTFILE" ] && [ -n "$SSL_KEYFILE" ] && [ -f "$SSL_CERTFILE" ] && [ -f "$SSL_KEYFILE" ]; then
    echo "TLS cert found — starting Uvicorn with HTTPS."
    SSL_ARGS="--ssl-certfile $SSL_CERTFILE --ssl-keyfile $SSL_KEYFILE"
else
    echo "No TLS cert — starting Uvicorn with plain HTTP."
fi

echo "Starting Uvicorn..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 $SSL_ARGS
