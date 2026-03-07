import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, 'data')
SESSION_DIR = os.path.join(DATA_DIR, 'sessions')
FILTERS_CONFIG_FILE = os.path.join(DATA_DIR, 'filters.json')
SUCCESSFUL_LEADS_FILE = os.path.join(DATA_DIR, 'successful_leads.txt')
CREDENTIALS_FILE = os.path.join(DATA_DIR, 'credentials.json')
ENV_FILE = os.path.join(BASE_DIR, '.env')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)
load_dotenv(ENV_FILE)

API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')

if not API_ID or not API_HASH:
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                creds = json.load(f)
                API_ID = creds.get('TG_API_ID')
                API_HASH = creds.get('TG_API_HASH')
        except Exception:
            pass

def save_credentials(api_id, api_hash):
    global API_ID, API_HASH
    API_ID = str(api_id)
    API_HASH = api_hash
    with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'TG_API_ID': API_ID, 'TG_API_HASH': API_HASH}, f)

COLORS = {
    "bg_primary":     "#0f1117",
    "bg_secondary":   "#161b27",
    "bg_card":        "#1c2333",
    "accent":         "#3b82f6",
    "success":        "#22c55e",
    "danger":         "#ef4444",
    "text_primary":   "#e2e8f0",
    "text_muted":     "#475569",
    "border":         "#2d3748",
    "accent_hover":   "#2563eb",
    "success_hover":  "#16a34a",
    "danger_hover":   "#dc2626",
    "warning":        "#f59e0b",
}

DEFAULT_FILTERS = {
    "fem_endings_regex": ".*(ova|eva|ова|ева|а|я|ия|iya|ia|xon|хон|bibi|биби)$",
    "blacklist_keywords": ["logist", "dispatcher", "логист", "диспетчер", "@lorry_filter_bot"],
    "bot_service_keywords": ["Guruhda yozish uchun", "qo'shishingiz kerak", "robot"],
    "max_line_breaks": 5,
    "max_common_groups": 2,
    "min_uz_char_percentage": 0.3,
    "show_terminal_logs": True,
    "forward_destinations": ["me"]
}

def load_filters():
    if os.path.exists(FILTERS_CONFIG_FILE):
        try:
            with open(FILTERS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**DEFAULT_FILTERS, **json.load(f)}
        except:
            return DEFAULT_FILTERS
    return DEFAULT_FILTERS

def save_filters(config):
    with open(FILTERS_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def log_successful_lead(text):
    with open(SUCCESSFUL_LEADS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n{text}\n\n")
