# config.py

import os
from dotenv import load_dotenv
import logging
import sys

load_dotenv()

# --- Core Bot Settings ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# --- Log Channel IDs ---
CASE_LOG_CHANNEL_ID = int(os.getenv("CASE_LOG_CHANNEL_ID"))
NEW_USER_GROUP_LOG_CHANNEL_ID = int(os.getenv("NEW_USER_GROUP_LOG_CHANNEL_ID"))

# --- Owner and Support Info ---
OWNER_ID = int(os.getenv("OWNER_ID"))
UPDATE_CHANNEL_USERNAME = os.getenv("UPDATE_CHANNEL_USERNAME", "asbhai_bsr")
ASBHAI_USERNAME = os.getenv("ASBHAI_USERNAME", "asbhaibsr") # 'H' हटा दिया, अब यह bot.py से मेल खाता है

# --- Default Messages & URLs ---
WELCOME_MESSAGE_DEFAULT = "👋 नमस्ते {username}! {groupname} में आपका स्वागत है।"
BOT_PHOTO_URL = os.getenv("BOT_PHOTO_URL", "https://envs.sh/PX8.jpg")
REPO_LINK = "https://github.com/your-github-username/your-repo-name"

# --- Cooldowns ---
COMMAND_COOLDOWN_TIME = int(os.getenv("COMMAND_COOLDOWN_TIME", 5))

# --- Logging Configuration ---
logging.getLogger("pyrogram").setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_logs.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration Validation ---
if not all([BOT_TOKEN, API_ID, API_HASH, CASE_LOG_CHANNEL_ID, NEW_USER_GROUP_LOG_CHANNEL_ID, OWNER_ID]):
    logger.critical("आवश्यक पर्यावरण चर (`BOT_TOKEN`, `API_ID`, `API_HASH`, `CASE_LOG_CHANNEL_ID`, `NEW_USER_GROUP_LOG_CHANNEL_ID`, `OWNER_ID`) सेट नहीं हैं। कृपया अपनी `.env` फ़ाइल जांचें और उन्हें प्रदान करें।")
    sys.exit(1)

# MONGODB_URI को config.py में रखने की बजाय database.py में सीधे os.getenv से एक्सेस करना बेहतर है,
# क्योंकि यह एक डेटाबेस-विशिष्ट सेटिंग है और सीधे env से आनी चाहिए।
# database.py में सुनिश्चित करें कि यह मौजूद है।
