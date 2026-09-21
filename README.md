# Willhaben Web Crawler Bot

This project is a web crawler bot designed to periodically check specific URLs on [willhaben.at](https://www.willhaben.at/) and notify users about updates via a Telegram bot. The project is built with Python (using Flask and Telegram Bot API) and can be deployed using Docker and Docker Compose.

## Features
- **Flask API**: Configure URLs and settings, view URL history.
- **Periodic Crawling**: Scheduled checks for updates on specific URLs.
- **Telegram Notifications**: Sends notifications via Telegram messages.
- **Web Interface**: View and manage crawled URLs and their statuses.
- **Search Workspaces**: Keep independent searches, history, members, and notifications in separate shared workspaces.

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
- `/start <password>` - Register the chat and join the default workspace.
- `/help` - Show all commands and explain workspaces.
- `/spaces` - List workspaces available to this chat.
- `/use <number or name>` - Switch the active workspace.
- `/create <name>` - Create a separate workspace and become its owner.
- `/invite [viewer|editor]` - Create a seven-day invitation code (owner only).
- `/join <code>` - Join an invited workspace.
- `/members` - List workspace members, their roles and notification status.
- `/notify on|off` - Enable or disable notifications for the active workspace.
- `/addurl <name> <url>` - Add a URL to the active workspace.
- `/listurls` - List URLs in the active workspace.
- `/removeurl <id>` - Remove an URL from the active workspace.
- `/stop` - Unregister the chat completely.

## Search Workspaces and Migration

The application automatically migrates existing installations on the next startup. It creates the permanent default workspace **Allgemein**, puts all existing monitored URLs and Telegram chats into it, and keeps their history. The prior one-list behaviour therefore continues unchanged.

Every additional workspace has an independent URL list, result history and Telegram recipient list. A new result is only sent to members of the workspace that owns the matching search and only when their notifications are enabled. The same search URL may be used in different workspaces.

Use the workspace picker at the top of the browser interface to change context. The **Suchraum verwalten** page lets an administrator rename a workspace, create invitation codes, and adjust member roles and notification settings. The default workspace cannot be deleted; non-default workspaces can only be deleted when empty, preventing accidental loss of searches or history.

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
