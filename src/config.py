import json
import logging
import uuid

# Flask Secret Key
SECRET_KEY = str(uuid.uuid4())

willhaben_prefix = "https://www.willhaben.at"

# Config file path
CONFIG_FILE_PATH = 'data/config.json'

# Default configuration
config = {
    'check_frequency': 60,  # in seconds
    'telegram_token': ''
}

# Load configuration from JSON file if available
def load_config():
    global config
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config.update(json.load(f))
    except FileNotFoundError:
        # If the config file does not exist, create it with default values
        save_config()

# Save configuration to JSON file
def save_config():
    with open(CONFIG_FILE_PATH, 'w') as f:
        json.dump(config, f, indent=4)

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load the config at startup
load_config()
