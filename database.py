import os
import logging

# --- Bot API Credentials ---
# BotFather se milne wala Token
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" # <--- Aapko yahan apna asli BOT TOKEN dalna hai
# my.telegram.org se milne wala API ID
API_ID = 29970536
# my.telegram.org se milne wala API Hash
API_HASH = "f4bfdcdd4a5c1b7328a7e4f25f024a09"

# --- MongoDB Configuration ---
# MongoDB connection string (Atlas ya local)
MONGO_URI = "mongodb+srv://nihiyel619:ZQ9H89pGV5lR8aIZ@cluster0.x2ecdqo.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# Database ka naam
MONGO_DB_NAME = "grouppolice_db"

# --- Channel IDs (Numeric IDs) ---
# Jahan violations log ki jayengi
CASE_LOG_CHANNEL_ID = -1002352329534
# Jahan naye users/groups ke judne ki jankari log ki jayegi
NEW_USER_GROUP_LOG_CHANNEL_ID = -1002717243409

# --- Bot Owner ID ---
# Aapki Telegram User ID (numeric)
OWNER_ID = 7315805581

# --- Default Messages and URLs ---
WELCOME_MESSAGE_DEFAULT = "👋 Welcome, {username}! Enjoy your stay in {groupname}."
UPDATE_CHANNEL_USERNAME = "earntalkchatcash" # Without @
ASBHAI_USERNAME = "asbhaibsr" # Without @
BOT_PHOTO_URL = "https://telegra.ph/file/a7e35b71234a7e9373e34.jpg"
REPO_LINK = "https://github.com/YourRepo/YourBot" # <--- Yahan apna sahi repo link dalna hai

# --- Cooldown Settings (in seconds) ---
# Sirf commands ke liye cooldown rakha gaya hai
COMMAND_COOLDOWN_TIME = 5 # Commands per user

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
