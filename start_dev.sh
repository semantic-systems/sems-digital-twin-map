#!/bin/bash
# Starts the DB in Docker with the port exposed, so you can run the
# backend and frontend locally for development.
#
# Backend (PyCharm / terminal):
#   uvicorn app.main:app --reload --port 8052
#   (run from backend/ with PYTHONPATH set, or configure PyCharm run config)
#
# Frontend (terminal):
#   cd frontend && npm run dev

set -e

echo "Starting PostgreSQL..."
docker compose -f docker-compose.yaml -f docker-compose.dev.yaml up -d postgis pgadmin

echo ""
echo "PostgreSQL is reachable at localhost:5432"
echo "pgAdmin at http://localhost:8080"
echo ""
echo "Start the backend:  cd backend && uvicorn app.main:app --reload --port 8052"
echo "Start the frontend: cd frontend && npm run dev"
