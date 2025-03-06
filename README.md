# Willhaben Web Crawler Bot

This project is a web crawler bot designed to periodically check specific URLs on [willhaben.at](https://www.willhaben.at/) and notify users about updates via a Telegram bot. The project is built with Python (using Flask and Telegram Bot API) and can be deployed using Docker and Docker Compose.

## Features
- **Flask API**: Configure URLs and settings, view URL history.
- **Periodic Crawling**: Scheduled checks for updates on specific URLs.
- **Telegram Notifications**: Sends notifications via Telegram messages.
- **Web Interface**: View and manage crawled URLs and their statuses.

## Requirements
- **Git**
- **Docker & Docker Compose** (for containerized deployment)
- **Python 3.12** (for local deployment)
- Required Python packages (see `requirements.txt`)

> **Note:** Ensure the repository is cloned into your working directory before proceeding.

## Setup Instructions

### Clone the Repository
Clone the repo into your desired directory:
```bash
git clone https://github.com/yourusername/willhaben-web-crawler.git
cd willhaben-web-crawler
```

### Running the Bot with Docker Compose

1. **Build and Start the Services**

   Use Docker Compose to build and run the application:
   ```bash
   docker compose up --build -d
   ```
   This command will build the Docker images (if needed) and start the Flask app along with the Telegram bot service. The Flask API will be accessible at `http://localhost:5000`.

2. **Using the `update.sh` Script**

   The `update.sh` script automates the process of updating the application by:
   - Pulling the latest code from the Git repository.
   - Pulling the latest Docker images.
   - Rebuilding Docker containers without cache.
   - Restarting services to apply the updates.

   Ensure the script is executable:
   ```bash
   chmod +x update.sh
   ```
   Then, run the script:
   ```bash
   ./update.sh
   ```

### Running the Bot Locally

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Set Up the Database:**  
   SQLite will be initialized automatically on the first run.
3. **Run the Flask Application:**
   ```bash
   python app.py
   ```
4. **Start the Telegram Bot:**
   Follow the instructions provided in the `/help` command within Telegram to set up URLs and receive notifications.

## Available Telegram Commands
- `/start <password>` - Initialize the bot for your chat.
- `/help` - Display help message with commands and usage.
- `/addurl <name> <url>` - Add a URL to be crawled with a specified name.
- `/listurls` - List all URLs being crawled.
- `/removeurl <id>` - Remove a URL from the crawl list by its ID.

## Project Structure

- `app.py`: Main Flask application.
- `bot.py`: Handles Telegram bot interactions.
- `crawler.py`: Manages periodic URL checks.
- `db_utils.py`: Database setup and functions.
- `Dockerfile`: Docker configuration file.
- `docker-compose.yml`: Docker Compose configuration for managing services.
- `update.sh`: Script to automate updates, rebuild Docker images, and restart services.

## License
This project is open-source under the MIT license.

## Notes
- This project is specifically configured to check URLs from willhaben.at periodically. Modify or expand the functionality as needed.
- Remember to clone the repository into your working directory before starting the setup process.
