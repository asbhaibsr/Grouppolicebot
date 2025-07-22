# database.py

import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import logging

# Setup a basic logger for the database module
# If you are already importing 'logger' from config.py and want to use that,
# you can remove these lines and uncomment 'from config import logger' below.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# If you want to use the logger from config.py, uncomment the line below
# from config import logger


# --- MongoDB URI Configuration ---
# MONGODB_URI should be set as an environment variable in your deployment environment (e.g., Koyeb)
MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    logger.critical("MONGODB_URI environment variable not set. Exiting.")
    exit(1)

# --- MongoDB Connection ---
client = None
db = None
users_collection = None
groups_collection = None
warns_collection = None
cooldowns_collection = None

try:
    client = MongoClient(MONGODB_URI)
    db = client.get_database("group_police_bot") # Replace with your preferred database name
    users_collection = db.users
    groups_collection = db.groups
    warns_collection = db.warns
    cooldowns_collection = db.cooldowns
    
    # Ping to check connection
    client.admin.command('ping')
    logger.info("MongoDB connected successfully!")
except ConnectionFailure as e:
    logger.critical(f"MongoDB connection failed: {e}")
    exit(1)
except OperationFailure as e:
    logger.critical(f"MongoDB operation failed (authentication/authorization issue?): {e}")
    exit(1)
except Exception as e:
    logger.critical(f"An unexpected error occurred during MongoDB connection: {e}")
    exit(1)


# --- User Management Functions ---
def add_or_update_user(user_id: int, username: str | None, first_name: str, last_name: str | None, is_bot: bool):
    """Adds or updates a user's information in the database."""
    users_collection.update_one(
        {"_id": user_id}, # Use _id for MongoDB's primary key for efficient lookup
        {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "is_bot": is_bot,
                "last_seen": datetime.now() # Update last seen timestamp on every interaction
            },
            "$setOnInsert": {
                "created_at": datetime.now() # Set creation timestamp only if it's a new document
            }
        },
        upsert=True # Create a new document if _id does not exist
    )
    logger.debug(f"User {user_id} added/updated.")

def get_user(user_id: int):
    """Retrieves a user's information from the database."""
    return users_collection.find_one({"_id": user_id})


# --- Group Management Functions ---
def add_or_update_group(group_id: int, title: str, added_by_user_id: int):
    """Adds or updates a group's information in the database, setting default settings on insert."""
    groups_collection.update_one(
        {"_id": group_id},
        {
            "$set": {
                "title": title,
                "last_updated": datetime.now()
            },
            "$setOnInsert": {
                "added_by": added_by_user_id,
                "added_at": datetime.now(),
                # Default settings for new groups:
                "welcome_enabled": True, 
                "welcome_message": "👋 नमस्ते {username}! {groupname} में आपका स्वागत है।",
                "anti_link_enabled": False, 
                "anti_flood_enabled": False,
                "warn_limit": 3 # Default warn limit before a ban
            }
        },
        upsert=True
    )
    logger.info(f"Group {group_id} added/updated in database.")

def get_group(group_id: int):
    """Retrieves a group's information and settings from the database."""
    return groups_collection.find_one({"_id": group_id})

def update_group_settings(group_id: int, settings: dict):
    """Updates specific settings for a given group."""
    groups_collection.update_one(
        {"_id": group_id},
        {"$set": settings}
    )
    logger.info(f"Settings updated for group {group_id}.")

def get_all_groups():
    """Retrieves a list of all groups stored in the database."""
    return list(groups_collection.find({}))

def delete_group(group_id: int):
    """Deletes a group and its associated warns from the database."""
    groups_collection.delete_one({"_id": group_id})
    warns_collection.delete_many({"group_id": group_id}) # Also clean up associated warns
    logger.info(f"Group {group_id} and its warns deleted from database.")


# --- Warn System Functions ---
def add_warn(group_id: int, user_id: int) -> int:
    """Adds a warn to a user in a specific group and returns the new warn count."""
    result = warns_collection.find_one_and_update(
        {"group_id": group_id, "user_id": user_id},
        {"$inc": {"warns": 1}, "$set": {"last_warned": datetime.now()}},
        upsert=True,
        return_document=True # Returns the updated document
    )
    return result["warns"] # The updated warn count

def get_warns(group_id: int, user_id: int) -> int:
    """Retrieves the current warn count for a user in a specific group."""
    result = warns_collection.find_one({"group_id": group_id, "user_id": user_id})
    return result["warns"] if result else 0

def delete_warns(group_id: int, user_id: int):
    """Resets (deletes) all warns for a user in a specific group."""
    warns_collection.delete_one({"group_id": group_id, "user_id": user_id})
    logger.info(f"Warns for user {user_id} in group {group_id} reset.")


# --- Command Cooldown System Functions ---
def add_command_cooldown(user_id: int, command_name: str, timestamp: datetime):
    """Records the last usage time for a command by a user."""
    cooldowns_collection.update_one(
        {"_id": user_id, "command": command_name},
        {"$set": {"last_used": timestamp}},
        upsert=True
    )
    logger.debug(f"Cooldown updated for user {user_id} command {command_name}.")

def get_command_cooldown(user_id: int, command_name: str) -> datetime | None:
    """Retrieves the last usage time for a command by a user."""
    result = cooldowns_collection.find_one({"_id": user_id, "command": command_name})
    return result["last_used"] if result else None

def reset_command_cooldown(user_id: int, command_name: str):
    """Resets the cooldown for a specific command for a user."""
    cooldowns_collection.delete_one({"_id": user_id, "command": command_name})
    logger.debug(f"Cooldown reset for user {user_id} command {command_name}.")
