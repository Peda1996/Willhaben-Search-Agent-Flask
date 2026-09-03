import json
import logging
import os
import uuid

# Persistent data directory. In the Home Assistant add-on this is /data
# (mounted and persisted by the Supervisor); locally it defaults to ./data.
DATA_DIR = os.environ.get('DATA_DIR', 'data')

# Flask Secret Key
SECRET_KEY = os.environ.get('SECRET_KEY') or str(uuid.uuid4())

# Config file path
CONFIG_FILE_PATH = os.path.join(DATA_DIR, 'config.json')

# Default configuration
config = {
    'check_frequency': 60,  # in seconds
    'telegram_token': '',
    'start_password': 'default_password',  # Replace this with the actual password
    'offer_factor': 0.87,  # drafted seller offer = asking price * this factor
}


# Load configuration from JSON file if available
def load_config():
    global config
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config.update(json.load(f))
    except FileNotFoundError:
        # If the config file does not exist, create it with default values
        save_config()


# Save configuration to JSON file
def save_config():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE_PATH, 'w') as f:
        json.dump(config, f, indent=4)


# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load the config at startup
load_config()
