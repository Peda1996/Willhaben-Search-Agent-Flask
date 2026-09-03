#!/bin/bash
# Standalone (Docker Compose) frissítés. Home Assistant alatt NEM ez a folyamat:
# ott az add-on oldalán az "Update" gombbal frissül.
set -e

echo "Pulling latest code..."
git pull

echo "Rebuilding and restarting..."
docker compose build
docker compose up -d

echo "Done."
