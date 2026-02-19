#!/bin/bash

# Exit on error
set -e

# Wait for database to be ready (optional but recommended if not using docker-compose healthchecks)
# We rely on docker-compose healthchecks, but adding a small delay or check is safer.

echo "Running migrations..."
alembic upgrade head

echo "Starting process..."

# If command starts with an option or is empty, run uvicorn
if [ "$#" -eq 0 ] || [ "${1#-}" != "$1" ]; then
    exec uvicorn src.main:app --host 0.0.0.0 --port 8000 "$@"
else
    # Execute the command passed from docker-compose or docker run
    exec "$@"
fi
