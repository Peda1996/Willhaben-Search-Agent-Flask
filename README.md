
# Willhaben Web Crawler Bot

This project is a web crawler bot designed to periodically check specific URLs on [willhaben.at](https://www.willhaben.at/) and notify users about updates through a Telegram bot. The project is built with Python (using Flask and Telegram Bot API) and can be deployed via Docker.

## Features
- **Flask API**: Configure URLs and settings, view URL history.
- **Periodic Crawling**: Scheduled to check for updates on specific URLs.
- **Telegram Notifications**: Notifies users of updates via Telegram messages.
- **Web Interface**: View and manage crawled URLs and their status.
  
## Setup Instructions

### Requirements
- **Python 3.12**
- **Docker** (optional for containerized deployment)
- Required Python packages (see `requirements.txt`)

### Configuration

The following configurations can be modified:
- `check_frequency` (seconds): Sets the interval for URL checks.
- `telegram_token`: Token for your Telegram bot.

### Running the Bot with Docker

To deploy the project using Docker, follow these steps:

1. **Build the Docker image**:
    ```bash
    docker build -t willhaben-web-crawler .
    ```

2. **Run the container**:
    ```bash
    docker run -p 5000:5000 willhaben-web-crawler
    ```

This command will start the Flask app, accessible at `http://localhost:5000`.

### Running the Bot Locally

1. **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2. **Set up the database** (SQLite will be initialized automatically on first run).

3. **Run the Flask application**:
    ```bash
    python app.py
    ```

4. **Start the Telegram Bot**:
    Follow instructions in the `/help` command within Telegram to set up URLs and receive notifications.

### Available Telegram Commands
- `/start <password>` - Initialize the bot for your chat.
- `/help` - Display help message with commands and usage.
- `/addurl <name> <url>` - Add a URL to be crawled with a specified name.
- `/listurls` - List all URLs being crawled.
- `/removeurl <id>` - Remove a URL from the crawl list by its ID.

### Project Structure

- `app.py`: Main Flask application.
- `bot.py`: Handles Telegram bot interactions.
- `crawler.py`: Manages periodic URL checks.
- `db_utils.py`: Database setup and functions.
- `Dockerfile`: Docker configuration file.

## License
This project is open-source under the MIT license.

## Notes
This project is specifically configured to check URLs from willhaben.at periodically. Modify or expand the functionality based on your requirements.
