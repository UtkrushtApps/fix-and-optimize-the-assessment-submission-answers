#!/usr/bin/env bash
set -e

echo "Starting services..."
docker compose up -d

echo "Waiting for PostgreSQL to be ready..."
until docker compose exec db pg_isready -U submissions_user -d submissions_db > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Waiting for Django app to start..."
until curl -s http://localhost:8000/api/submissions/ > /dev/null 2>&1 || curl -s http://localhost:8000/api/submissions/ -o /dev/null; do
  sleep 2
done

echo "Running migrations..."
docker compose exec app python manage.py migrate --noinput

echo "Environment is ready."
echo "Django app: http://localhost:8000"
echo "Run tests with: docker compose exec app python manage.py test app"
