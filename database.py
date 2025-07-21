import os
import logging
from pymongo import MongoClient
from datetime import datetime # datetime को import करें

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

# MongoDB client initialize karein
client = None # Default value None set करें
try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    groups_collection = db["groups"] # <-- Groups के लिए एक collection बनाएँ
    logging.info("MongoDB connection successful.")
except Exception as e:
    logging.error(f"Error connecting to MongoDB: {e}")
    # client None रहेगा ताकि बाद में इसका इस्तेमाल करने पर एरर आए अगर कनेक्शन नहीं हुआ

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

# --- Functions for Database Operations ---
def add_or_update_group(group_id: int, group_name: str, **kwargs):
    """
    Groups collection mein group ki jankari add ya update karta hai.
    """
    if client is None:
        logger.error("MongoDB connection not established. Cannot add or update group.")
        return

    # default values को group_data में initialize करें
    group_data = {
        "_id": group_id,
        "name": group_name,
        "is_active": True,
        "welcome_message": WELCOME_MESSAGE_DEFAULT,
        "rules_message": "No rules set yet.",
        "added_at": datetime.now() # वर्तमान समय को added_at में डालें
    }
    
    # kwargs से आए हुए values से default values को overwrite करें
    group_data.update(kwargs)

    try:
        result = groups_collection.update_one(
            {"_id": group_id},
            {"$set": group_data},
            upsert=True
        )
        if result.upserted_id:
            logger.info(f"New group '{group_name}' ({group_id}) added to database.")
        elif result.modified_count > 0:
            logger.info(f"Group '{group_name}' ({group_id}) updated in database.")
        else:
            logger.info(f"Group '{group_name}' ({group_id}) already up to date in database.")
    except Exception as e:
        logger.error(f"Error adding/updating group {group_id} ({group_name}): {e}")

# Yahan aap anya database functions bhi add kar sakte hain, jaise:
# def get_group_settings(group_id: int):
#     if client is None: return None
# #     return groups_collection.find_one({"_id": group_id})

# def delete_group(group_id: int):
#     if client is None: return
#     groups_collection.delete_one({"_id": group_id})
