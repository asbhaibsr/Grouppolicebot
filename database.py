from pymongo import MongoClient
from datetime import datetime
from config import MONGO_URI, MONGO_DB_NAME, logger

# MongoDB Client initialization
try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    logger.info("MongoDB connected successfully!")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    client = None
    db = None

# Collections
# PyMongo 'is not None' checks applied here
groups_collection = db["groups"] if db is not None else None
users_collection = db["users"] if db is not None else None
violations_collection = db["violations"] if db is not None else None
biolink_exceptions_collection = db["biolink_exceptions"] if db is not None else None
new_entries_log_collection = db["new_entries_log"] if db is not None else None
# Chatbot-related collections removed.

# --- Group Operations ---
def add_or_update_group(group_id: int, group_name: str, added_by_user_id: int = None):
    if groups_collection is None: return # Check 'is None' for collections
    groups_collection.update_one(
        {"id": group_id},
        {
            "$set": {
                "name": group_name,
                "added_by": added_by_user_id,
                "last_updated": datetime.utcnow()
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow(),
                "bot_enabled": True,
                "filter_abusive": True,
                "filter_pornographic_text": True,
                "filter_spam": True,
                "filter_links": True,
                "filter_bio_links": True,
                "usernamedel_enabled": True,
                "welcome_message": None # Default welcome message will be used if None
            }
        },
        upsert=True
    )
    logger.info(f"Group {group_name} ({group_id}) added/updated.")

def get_group_settings(group_id: int) -> dict:
    if groups_collection is None: return {} # Check 'is None' for collections
    return groups_collection.find_one({"id": group_id})

def update_group_setting(group_id: int, setting_name: str, value):
    if groups_collection is None: return # Check 'is None' for collections
    groups_collection.update_one(
        {"id": group_id},
        {"$set": {setting_name: value, "last_updated": datetime.utcnow()}}
    )
    logger.info(f"Group {group_id} setting '{setting_name}' updated to {value}.")

def get_all_groups() -> list:
    if groups_collection is None: return [] # Check 'is None' for collections
    return list(groups_collection.find({}))

# --- User Operations ---
def add_or_update_user(user_id: int, username: str, first_name: str, last_name: str = None, is_bot: bool = False):
    if users_collection is None: return # Check 'is None' for collections
    users_collection.update_one(
        {"id": user_id},
        {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "is_bot": is_bot,
                "last_activity": datetime.utcnow()
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

def get_total_users() -> int:
    if users_collection is None: return 0 # Check 'is None' for collections
    return users_collection.count_documents({})

# --- Violation Operations ---
def add_violation(username: str, user_id: int, group_name: str, group_id: int, violation_type: str, original_content: str, case_name: str = None):
    if violations_collection is None: return # Check 'is None' for collections
    violations_collection.insert_one({
        "username": username,
        "user_id": user_id,
        "group_name": group_name,
        "group_id": group_id,
        "violation_type": violation_type,
        "original_content": original_content,
        "case_name": case_name,
        "timestamp": datetime.utcnow()
    })
    logger.warning(f"Violation recorded for {username} ({user_id}) in {group_name}: {violation_type}")

def get_total_violations() -> int:
    if violations_collection is None: return 0 # Check 'is None' for collections
    return violations_collection.count_documents({})

# --- Bio Link Exception Operations ---
def get_user_biolink_exception(user_id: int) -> bool:
    if biolink_exceptions_collection is None: return False # Check 'is None' for collections
    # Returns True if an exception exists, False otherwise
    return biolink_exceptions_collection.find_one({"user_id": user_id}) is not None

def set_user_biolink_exception(user_id: int, allow: bool):
    if biolink_exceptions_collection is None: return # Check 'is None' for collections
    if allow:
        biolink_exceptions_collection.update_one(
            {"user_id": user_id},
            {"$set": {"timestamp": datetime.utcnow()}},
            upsert=True
        )
        logger.info(f"Bio link exception granted for user {user_id}.")
    else:
        biolink_exceptions_collection.delete_one({"user_id": user_id})
        logger.info(f"Bio link exception removed for user {user_id}.")

# --- New Entries Log Operations ---
def log_new_user_or_group(log_type: str, entity_id: int, entity_name: str, inviter_id: int = None, inviter_username: str = None):
    if new_entries_log_collection is None: return # Check 'is None' for collections
    new_entries_log_collection.insert_one({
        "log_type": log_type, # "new_group" or "new_user" or "left_user"
        "entity_id": entity_id,
        "entity_name": entity_name,
        "inviter_id": inviter_id,
        "inviter_username": inviter_username,
        "timestamp": datetime.utcnow()
    })
    logger.info(f"New entry logged: {log_type} - {entity_name} ({entity_id})")

