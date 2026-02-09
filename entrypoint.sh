#!/bin/bash

# Exit on error
set -e

# Wait for database to be ready (optional but recommended if not using docker-compose healthchecks)
# We rely on docker-compose healthchecks, but adding a small delay or check is safer.

echo "Running migrations..."
alembic upgrade head

echo "Starting server..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
