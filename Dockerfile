# Use an official Python runtime (Python 3.12) as a parent image
FROM python:3.12-slim

# Set the working directory in the container to /app/src
WORKDIR /app/src

# Copy the current directory contents into the container at /app/src
COPY . /app/src

# Create the data directory within the container
RUN mkdir -p /app/src/data

# Install any necessary packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port on which the Flask app will run
EXPOSE 5000

# Set environment variables with the new working directory in src
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Ensure /app/src/data is created as a persistent volume for config and database storage
VOLUME ["/app/src/data"]

# Run the command to start the Flask app
CMD ["python", "app.py"]
