# config.py

import os
import re
import logging
from dotenv import load_dotenv

# .env फ़ाइल से पर्यावरण चर लोड करें
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment Variables ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

# आपके द्वारा प्रदान किए गए स्निपेट के अनुसार विभिन्न MongoDB URIs
MONGO_URI_MESSAGES = os.getenv("MONGO_URI_MESSAGES")
MONGO_URI_BUTTONS = os.getenv("MONGO_URI_BUTTONS")
MONGO_URI_TRACKING = os.getenv("MONGO_URI_TRACKING")

OWNER_ID = int(os.getenv("OWNER_ID"))

API_ID = int(os.getenv("API_ID")) # Pyrogram के लिए API_ID और API_HASH
API_HASH = os.getenv("API_HASH")

# दो लॉग चैनल की IDs
NEW_USER_GROUP_LOG_CHANNEL_ID = int(os.getenv("NEW_USER_GROUP_LOG_CHANNEL_ID", "-1001234567891"))
CASE_LOG_CHANNEL_ID = int(os.getenv("CASE_LOG_CHANNEL_ID", "-1001234567892"))

# --- Constants ---
MAX_MESSAGES_THRESHOLD = 100000
PRUNE_PERCENTAGE = 0.30
UPDATE_CHANNEL_USERNAME = os.getenv("UPDATE_CHANNEL_USERNAME", "earntalkchatcash") # आपका अपडेट चैनल
ASBHAI_USERNAME = os.getenv("ASBHAI_USERNAME", "asbhaibsr") # आपका/मालिक का यूजरनेम
ASFILTER_BOT_USERNAME = os.getenv("ASFILTER_BOT_USERNAME", "asfilter_bot") # आपके प्रीमियम रिवॉर्ड बॉट का यूजरनेम
BOT_PHOTO_URL = os.getenv("BOT_PHOTO_URL", "https://envs.sh/FU3.jpg") # बॉट की फोटो URL
REPO_LINK = os.getenv("REPO_LINK", "https://github.com/asbhaibsr/Chatbot-asbhai.git") # आपके रेपो का लिंक

WELCOME_MESSAGE_DEFAULT = "नमस्ते {username}! हमारे ग्रुप में आपका स्वागत है।"

# Regex for common URL patterns including t.me and typical link formats
URL_PATTERN_REGEX = re.compile(r"(?:https?://|www\.|t\.me/)[^\s/$.?#].[^\s]*", re.IGNORECASE)

# Flask port for health checks (Koyeb specific)
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))

# Cooldown settings
COMMAND_COOLDOWN_TIME = 3 # seconds (for commands like /start, /topusers)
MESSAGE_REPLY_COOLDOWN_TIME = 8 # seconds (for general messages)

