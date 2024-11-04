# Use an official Python runtime (Python 3.12) as a parent image
FROM python:3.12-slim

# Set the working directory in the container to /app/src
WORKDIR /app/src

# Copy the current directory contents into the container at /app/src
COPY . /app

# Create the data directory within the container
RUN mkdir -p /app/src/data

# Install dependencies for Chrome and ChromeDriver
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    unzip \
    curl \
    ca-certificates \
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
    xdg-utils && \
    rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# Install ChromeDriver
RUN CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
    wget -q "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip" && \
    unzip chromedriver_linux64.zip -d /usr/local/bin/ && \
    rm chromedriver_linux64.zip

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Expose the port on which the Flask app will run
EXPOSE 5000

# Set environment variables with the new working directory in src
ENV FLASK_APP=/app/src/app.py
ENV FLASK_ENV=production

# Ensure /app/src/data is created as a persistent volume for config and database storage
VOLUME ["/app/src/data"]

# Run the command to start the Flask app
CMD ["python", "/app/src/app.py"]
