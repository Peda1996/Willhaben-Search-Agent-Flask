# Use an official Selenium Docker image that provides compatible Chrome and ChromeDriver versions
FROM selenium/standalone-chrome:latest

# Switch to root to install additional packages
USER root

# Install Python 3.12, pip, and curl (required for the healthcheck)
RUN apt-get update && \
    apt-get install -y python3.12 python3-pip curl && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container to /app/src
WORKDIR /app/src

# Copy the entire application code into the container at /app
COPY . /app

# Create the data directory within the container (for persistent storage)
RUN mkdir -p /app/src/data

# Upgrade pip and install Python dependencies from requirements.txt
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r /app/requirements.txt

# Expose the port on which the Flask app will run
EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=/app/src/app.py
ENV FLASK_ENV=production

# Define a volume for persistent data (optional)
VOLUME ["/app/src/data"]

# Healthcheck to ensure the Flask app is running
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Start the Flask application
CMD ["python3", "/app/src/app.py"]
