import os
import logging
from pymongo import MongoClient
from datetime import datetime
from typing import Optional, Dict, Any # Optional और Dict को import करें

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
client = None
db = None
groups_collection = None
users_collection = None
violations_collection = None
logs_collection = None
biolink_exceptions_collection = None

try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    groups_collection = db["groups"]
    users_collection = db["users"]
    violations_collection = db["violations"]
    logs_collection = db["logs"] # New collection for general logs (user/group join/leave)
    biolink_exceptions_collection = db["biolink_exceptions"] # New collection for biolink exceptions
    logging.info("MongoDB connection successful.")
except Exception as e:
    logging.error(f"Error connecting to MongoDB: {e}")
    client = None # Ensure client is None if connection fails

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

def add_or_update_group(group_id: int, group_name: str, added_by_user_id: Optional[int] = None, **kwargs):
    """
    Groups collection mein group ki jankari add ya update karta hai.
    """
    if groups_collection is None:
        logger.error("Groups collection not initialized. Cannot add or update group.")
        return

    group_data = {
        "_id": group_id,
        "name": group_name,
        "is_active": kwargs.get("is_active", True),
        "welcome_message": kwargs.get("welcome_message", WELCOME_MESSAGE_DEFAULT),
        "rules_message": kwargs.get("rules_message", "No rules set yet."),
        "filter_abusive": kwargs.get("filter_abusive", True), # Default to True
        "filter_pornographic_text": kwargs.get("filter_pornographic_text", True), # Default to True
        "filter_spam": kwargs.get("filter_spam", True), # Default to True
        "filter_links": kwargs.get("filter_links", True), # Default to True
        "filter_bio_links": kwargs.get("filter_bio_links", True), # Default to True
        "usernamedel_enabled": kwargs.get("usernamedel_enabled", True), # Default to True
        "bot_enabled": kwargs.get("bot_enabled", True), # Default to True
        "added_at": kwargs.get("added_at", datetime.now())
    }
    if added_by_user_id:
        group_data["added_by"] = added_by_user_id

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

def get_group_settings(group_id: int) -> Optional[Dict[str, Any]]:
    """
    Groups collection se group ki settings retrieve karta hai.
    """
    if groups_collection is None:
        logger.error("Groups collection not initialized. Cannot get group settings.")
        return None

    try:
        return groups_collection.find_one({"_id": group_id})
    except Exception as e:
        logger.error(f"Error getting group settings for {group_id}: {e}")
        return None

def update_group_setting(group_id: int, setting_key: str, setting_value: Any):
    """
    Groups collection mein ek specific group setting ko update karta hai.
    """
    if groups_collection is None:
        logger.error("Groups collection not initialized. Cannot update group setting.")
        return

    try:
        result = groups_collection.update_one(
            {"_id": group_id},
            {"$set": {setting_key: setting_value}}
        )
        if result.modified_count > 0:
            logger.info(f"Group {group_id} setting '{setting_key}' updated to '{setting_value}'.")
        else:
            logger.warning(f"Group {group_id} setting '{setting_key}' not updated. It might be the same value or group not found.")
    except Exception as e:
        logger.error(f"Error updating group setting for {group_id}, key '{setting_key}': {e}")

def add_violation(user_id: int, username: str, group_id: int, group_name: str, violation_type: str, original_content: str, case_name: Optional[str] = None):
    """
    Violations collection mein ek naya violation record add karta hai.
    """
    if violations_collection is None:
        logger.error("Violations collection not initialized. Cannot add violation.")
        return

    violation_data = {
        "user_id": user_id,
        "username": username,
        "group_id": group_id,
        "group_name": group_name,
        "violation_type": violation_type,
        "original_content": original_content,
        "timestamp": datetime.now(),
        "case_name": case_name
    }
    try:
        violations_collection.insert_one(violation_data)
        logger.info(f"Violation added for user {user_id} in group {group_id}: {violation_type}")
    except Exception as e:
        logger.error(f"Error adding violation for user {user_id}: {e}")

def get_user_biolink_exception(user_id: int) -> bool:
    """
    Check karta hai ki user ko biolink filter se exception mila hai ya nahi.
    """
    if biolink_exceptions_collection is None:
        logger.error("Biolink exceptions collection not initialized. Cannot get user biolink exception.")
        return False # Default to no exception if collection not ready

    try:
        exception_doc = biolink_exceptions_collection.find_one({"_id": user_id})
        return exception_doc.get("has_exception", False) if exception_doc else False
    except Exception as e:
        logger.error(f"Error getting biolink exception for user {user_id}: {e}")
        return False

def set_user_biolink_exception(user_id: int, has_exception: bool):
    """
    User ke liye biolink filter exception set karta hai.
    """
    if biolink_exceptions_collection is None:
        logger.error("Biolink exceptions collection not initialized. Cannot set user biolink exception.")
        return

    try:
        biolink_exceptions_collection.update_one(
            {"_id": user_id},
            {"$set": {"has_exception": has_exception, "updated_at": datetime.now()}},
            upsert=True
        )
        logger.info(f"Biolink exception for user {user_id} set to {has_exception}")
    except Exception as e:
        logger.error(f"Error setting biolink exception for user {user_id}: {e}")

def get_all_groups() -> list[Dict[str, Any]]:
    """
    Sabhi connected groups ki list return karta hai.
    """
    if groups_collection is None:
        logger.error("Groups collection not initialized. Cannot get all groups.")
        return []

    try:
        return list(groups_collection.find({}))
    except Exception as e:
        logger.error(f"Error getting all groups: {e}")
        return []

def get_total_users() -> int:
    """
    Total track kiye gaye users ki sankhya return karta hai.
    """
    if users_collection is None:
        logger.error("Users collection not initialized. Cannot get total users.")
        return 0

    try:
        return users_collection.count_documents({})
    except Exception as e:
        logger.error(f"Error getting total users: {e}")
        return 0

def get_total_violations() -> int:
    """
    Total record kiye gaye violations ki sankhya return karta hai.
    """
    if violations_collection is None:
        logger.error("Violations collection not initialized. Cannot get total violations.")
        return 0

    try:
        return violations_collection.count_documents({})
    except Exception as e:
        logger.error(f"Error getting total violations: {e}")
        return 0

def add_or_update_user(user_id: int, username: Optional[str], first_name: str, last_name: Optional[str], is_bot: bool):
    """
    Users collection mein user ki jankari add ya update karta hai.
    """
    if users_collection is None:
        logger.error("Users collection not initialized. Cannot add or update user.")
        return

    user_data = {
        "_id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "is_bot": is_bot,
        "last_seen": datetime.now()
    }
    try:
        result = users_collection.update_one(
            {"_id": user_id},
            {"$set": user_data},
            upsert=True
        )
        if result.upserted_id:
            logger.info(f"New user {user_id} ({username or first_name}) added to database.")
        # elif result.modified_count > 0:
            # logger.debug(f"User {user_id} updated in database.") # Too verbose for INFO level
    except Exception as e:
        logger.error(f"Error adding/updating user {user_id}: {e}")

async def log_new_user_or_group(log_type: str, entity_id: int, entity_name: str, inviter_id: Optional[int] = None, inviter_username: Optional[str] = None):
    """
    Naye user ya group ke judne/chodne ko logs collection mein record karta hai.
    """
    if logs_collection is None:
        logger.error("Logs collection not initialized. Cannot log new user/group entry.")
        return

    log_data = {
        "log_type": log_type, # e.g., "new_group", "new_user", "left_user"
        "entity_id": entity_id,
        "entity_name": entity_name,
        "timestamp": datetime.now(),
        "inviter_id": inviter_id,
        "inviter_username": inviter_username
    }
    try:
        logs_collection.insert_one(log_data)
        logger.info(f"Logged {log_type} for {entity_name} (ID: {entity_id})")
    except Exception as e:
        logger.error(f"Error logging new user/group entry for {entity_id}: {e}")
