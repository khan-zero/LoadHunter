import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

import platform
from pathlib import Path

APP_VERSION = "v1.0.21"

def get_data_dir() -> str:
    """Returns an OS-specific, safe directory for application data."""
    system = platform.system()
    app_name = "LoadHunter"
    
    if system == "Windows":
        # Windows: %APPDATA%\LoadHunter
        base_dir = os.environ.get("APPDATA")
        if not base_dir:
            base_dir = os.path.expanduser("~")
        data_dir = os.path.join(base_dir, app_name)
    elif system == "Darwin":
        # Mac: ~/Library/Application Support/LoadHunter
        data_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", app_name)
    else:
        # Linux/Unix: ~/.local/share/LoadHunter
        base_dir = os.environ.get("XDG_DATA_HOME")
        if not base_dir:
            base_dir = os.path.join(os.path.expanduser("~"), ".local", "share")
        data_dir = os.path.join(base_dir, app_name)
        
    return data_dir

def get_bundle_dir() -> str:
    """Returns the directory of the executable or script."""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

# Data will be stored in the OS-specific user app data folder
DATA_DIR = get_data_dir()
BUNDLE_DIR = get_bundle_dir()

# APP_DIR is where the .exe or main.py is located
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = BUNDLE_DIR

# All data (logs, filters, sessions) should live in the OS-specific data dir for persistence
SESSION_DIR = os.path.join(DATA_DIR, 'sessions')
FILTERS_CONFIG_FILE = os.path.join(DATA_DIR, 'filters.json')
SUCCESSFUL_LEADS_FILE = os.path.join(DATA_DIR, 'successful_leads.txt')
CREDENTIALS_FILE = os.path.join(DATA_DIR, 'credentials.json')
LOG_FILE = os.path.join(DATA_DIR, 'loadhunter.log')
ERROR_LOG_FILE = os.path.join(DATA_DIR, 'error_log.txt')
ENV_FILE = os.path.join(APP_DIR, '.env')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)

# Try to load environment variables from .env file
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE)
else:
    # Also check the current working directory as a fallback
    cwd_env = os.path.join(os.getcwd(), '.env')
    if os.path.exists(cwd_env):
        load_dotenv(cwd_env)

API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')

def _check_api_keys():
    global API_ID, API_HASH
    if not API_ID or not API_HASH:
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
                    if not API_ID: API_ID = creds.get('TG_API_ID')
                    if not API_HASH: API_HASH = creds.get('TG_API_HASH')
            except Exception as e:
                print(f"Warning: Failed to load credentials from {CREDENTIALS_FILE}: {e}")

_check_api_keys()

if not API_ID or not API_HASH:
    # Log the locations searched for debugging
    with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"\n--- API KEYS MISSING {datetime.now()} ---\n")
        f.write(f"Searched ENV_FILE: {ENV_FILE}\n")
        f.write(f"Searched CREDENTIALS_FILE: {CREDENTIALS_FILE}\n")
        f.write(f"CWD: {os.getcwd()}\n")
        f.write(f"APP_DIR: {APP_DIR}\n")

def save_credentials(api_id, api_hash):
    global API_ID, API_HASH
    API_ID = str(api_id)
    API_HASH = api_hash
    with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'TG_API_ID': API_ID, 'TG_API_HASH': API_HASH}, f)

COLORS = {
    "bg_primary":     "#202020",      # Windows 11 solid dark background
    "bg_secondary":   "#282828",      # Navigation/Sidebar layers
    "bg_card":        "#2D2D2D",      # Elevated cards
    "accent":         "#60CDFF",      # Windows 11 blue accent (Dark Mode)
    "success":        "#6CCB5F",      # Softer fluent green
    "danger":         "#FF99A4",      # Fluent pastel red
    "text_primary":   "#FFFFFF",
    "text_muted":     "#A0A0A0",
    "border":         "#333333",      # Crisp, subtle thin borders
    "accent_hover":   "#4AB4E6",
    "success_hover":  "#5BB050",
    "danger_hover":   "#E6858F",
    "warning":        "#FCE100",
}

DEFAULT_FILTERS = {
    "fem_endings_regex": ".*(ova|eva|ова|ева|а|я|ия|iya|ia|xon|хон|bibi|биби)$",
    "blacklist_keywords": ["logist", "dispatcher", "логист", "диспетчер", "@lorry_filter_bot"],
    "bot_service_keywords": ["Guruhda yozish uchun", "qo'shishingiz kerak", "robot"],
    "max_line_breaks": 5,
    "max_common_groups": 2,
    "min_uz_char_percentage": 0.3,
    "show_terminal_logs": True,
    "save_critical_logs": True,
    "forward_destinations": ["me"],
    "check_feminine": True
}

def sanity_check_filters(config):
    """Verifies that the config contains all required keys and valid types."""
    if not isinstance(config, dict):
        return DEFAULT_FILTERS
    
    # Ensure all default keys exist
    for key, value in DEFAULT_FILTERS.items():
        if key not in config:
            config[key] = value
            
    # Validate specific types
    if not isinstance(config.get("blacklist_keywords"), list):
        config["blacklist_keywords"] = DEFAULT_FILTERS["blacklist_keywords"]
    if not isinstance(config.get("bot_service_keywords"), list):
        config["bot_service_keywords"] = DEFAULT_FILTERS["bot_service_keywords"]
    if not isinstance(config.get("forward_destinations"), list):
        config["forward_destinations"] = DEFAULT_FILTERS["forward_destinations"]
        
    return config

def load_filters():
    """Loads filters from file with validation and fallback."""
    if os.path.exists(FILTERS_CONFIG_FILE):
        try:
            with open(FILTERS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                return sanity_check_filters(loaded_config)
        except (json.JSONDecodeError, IOError, Exception):
            # If corrupted or unreadable, reset to default
            save_filters(DEFAULT_FILTERS)
            return DEFAULT_FILTERS
    return DEFAULT_FILTERS

def save_filters(config):
    """Saves filters to the OS-specific data directory."""
    try:
        validated_config = sanity_check_filters(config)
        with open(FILTERS_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(validated_config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving filters: {e}")


def log_successful_lead(text):
    with open(SUCCESSFUL_LEADS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n{text}\n\n")
