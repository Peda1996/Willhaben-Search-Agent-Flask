# Use an official Python runtime as the base image
FROM python:3.12-slim

# Set the working directory to /app/src
WORKDIR /app/src

# Install required system packages and the venv module
RUN apt-get update && \
    rm -rf /var/lib/apt/lists/*

# Copy your application code into the container at /app
COPY . /app

# Create the data directory (for persistent storage)
RUN mkdir -p /app/src/data

# Create and activate a virtual environment, upgrade pip, and install dependencies
RUN python3 -m venv /venv && \
    /venv/bin/pip install --no-cache-dir --upgrade pip && \
    /venv/bin/pip install --no-cache-dir -r /app/requirements.txt

# Expose the Flask app port
EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=/app/src/app.py
ENV FLASK_ENV=production

# Healthcheck to ensure the Flask app is running
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Start the Flask application using the virtual environment's Python interpreter
CMD ["/venv/bin/python", "/app/src/app.py"]
