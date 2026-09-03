#!/usr/bin/env sh
set -e

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "${DATA_DIR}"

cd /app/src
exec python app.py
