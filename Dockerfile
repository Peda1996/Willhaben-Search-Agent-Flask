# Use an official Python runtime (Python 3.12) as a parent image
FROM python:3.12-slim

# Set the working directory in the container to /app/src
WORKDIR /app/src

# Copy the current directory contents into the container at /app/src
COPY . /app

# Create the data directory within the container
RUN mkdir -p /app/src/data

# Install dependencies for Chrome and ChromeDriver, including libvulkan1 and distutils
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    unzip \
    curl \
    ca-certificates \
    python3-distutils \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libgbm-dev \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libvulkan1 && \
    rm -rf /var/lib/apt/lists/*

# Install Chrome and ensure the correct version
RUN wget -q -O google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Expose the port on which the Flask app will run
EXPOSE 5000

# Set environment variables with the new working directory in src
ENV FLASK_APP=/app/src/app.py
ENV FLASK_ENV=production

# Ensure /app/src/data is created as a persistent volume for config and database storage
VOLUME ["/app/src/data"]

# Run the command to start the Flask app
CMD ["python", "/app/src/app.py"]

# Healthcheck to ping Flask
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1