import os
import logging

# --- Bot API Credentials ---
# BotFather se milne wala Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
# my.telegram.org se milne wala API ID
API_ID = int(os.getenv("API_ID", "YOUR_API_ID_HERE"))
# my.telegram.org se milne wala API Hash
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH_HERE")

# --- MongoDB Configuration ---
# MongoDB connection string (Atlas ya local)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/grouppolice")
# Database ka naam
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "grouppolice_db")

# --- Channel IDs (Numeric IDs) ---
# Jahan violations log ki jayengi
CASE_LOG_CHANNEL_ID = int(os.getenv("CASE_LOG_CHANNEL_ID", "-100123456789")) # Replace with your channel ID
# Jahan naye users/groups ke judne ki jankari log ki jayegi
NEW_USER_GROUP_LOG_CHANNEL_ID = int(os.getenv("NEW_USER_GROUP_LOG_CHANNEL_ID", "-100987654321")) # Replace with your channel ID

# --- Bot Owner ID ---
# Aapki Telegram User ID (numeric)
OWNER_ID = int(os.getenv("OWNER_ID", "YOUR_OWN_TELEGRAM_USER_ID")) # Replace with your User ID

# --- Default Messages and URLs ---
WELCOME_MESSAGE_DEFAULT = "👋 Welcome, {username}! Enjoy your stay in {groupname}."
UPDATE_CHANNEL_USERNAME = os.getenv("UPDATE_CHANNEL_USERNAME", "YourUpdateChannelUsername") # Without @
ASBHAI_USERNAME = os.getenv("ASBHAI_USERNAME", "YourContactUsername") # Without @
BOT_PHOTO_URL = os.getenv("BOT_PHOTO_URL", "https://telegra.ph/file/a7e35b71234a7e9373e34.jpg") # Replace with your bot's photo URL
REPO_LINK = os.getenv("REPO_LINK", "https://github.com/YourRepo/YourBot") # Replace with your bot's GitHub repo link

# --- Cooldown Settings (in seconds) ---
# Sirf commands ke liye cooldown rakha gaya hai
COMMAND_COOLDOWN_TIME = int(os.getenv("COMMAND_COOLDOWN_TIME", 5)) # Commands per user

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

