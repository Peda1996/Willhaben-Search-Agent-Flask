#!/bin/bash

# Function to check the last command status and exit if it failed
check_status() {
  if [ $? -ne 0 ]; then
    echo "Error: $1 failed. Exiting."
    exit 1
  fi
}

echo "Updating repository with git pull..."
git pull
check_status "Git pull"

echo "Pulling latest Docker images..."
docker-compose pull
check_status "Docker image pull"

echo "Building Docker images without cache..."
docker-compose build --no-cache
check_status "Docker image build"

echo "Stopping and removing existing containers..."
docker-compose down
check_status "Stopping containers"

echo "Starting services..."
docker-compose up -d
check_status "Starting containers"

echo "All Docker services updated and started successfully."
