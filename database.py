import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
from config import logger, WELCOME_MESSAGE_DEFAULT # WELCOME_MESSAGE_DEFAULT को इम्पोर्ट किया गया
import sys # sys इम्पोर्ट किया गया

# load_dotenv() # <-- इस लाइन को हटा दिया गया क्योंकि इसे config.py में पहले ही लोड कर लिया गया है

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    logger.error("MONGO_URI environment variable not set. Exiting.")
    sys.exit(1) # exit को sys.exit से बदला गया

try:
    client = MongoClient(MONGO_URI)
    # Ping the database to confirm connection
    client.admin.command('ping')
    logger.info("Successfully connected to MongoDB!")
    db = client.group_police_bot
except Exception as e:
    logger.critical(f"MongoDB से जुड़ने में असमर्थ: {e}. कृपया अपनी MONGO_URI जांचें।")
    sys.exit(1)

# Collections
groups_collection = db.groups
users_collection = db.users
violations_collection = db.violations
logs_collection = db.logs # For new user/group entries
keywords_collection = db.keywords # For managing keywords like abusive words

def add_or_update_group(group_id: int, group_name: str, added_by_user_id: int = None):
    """
    Adds a new group or updates an existing one.
    Initializes default settings if it's a new group.
    """
    group_data = groups_collection.find_one({"id": group_id})
    if not group_data:
        default_settings = {
            "id": group_id,
            "name": group_name,
            "bot_enabled": True,
            "filter_abusive": True,
            "filter_pornographic_text": True,
            "filter_spam": True,
            "filter_links": True,
            "filter_bio_links": True,
            "usernamedel_enabled": True, # New setting for username filter
            "welcome_message": WELCOME_MESSAGE_DEFAULT, # <-- config.py से WELCOME_MESSAGE_DEFAULT का उपयोग किया गया
            "date_added": datetime.now(),
            "added_by": added_by_user_id
        }
        groups_collection.insert_one(default_settings)
        logger.info(f"New group added: {group_name} ({group_id})")
    else:
        # Update group name in case it changed
        groups_collection.update_one(
            {"id": group_id},
            {"$set": {"name": group_name, "last_updated": datetime.now()}}
        )
        logger.info(f"Group updated: {group_name} ({group_id})")

def get_group_settings(group_id: int) -> dict:
    """Retrieves settings for a specific group."""
    return groups_collection.find_one({"id": group_id})

def update_group_setting(group_id: int, setting_name: str, setting_value):
    """Updates a specific setting for a group."""
    groups_collection.update_one(
        {"id": group_id},
        {"$set": {setting_name: setting_value, "last_updated": datetime.now()}}
    )
    logger.info(f"Group {group_id} setting '{setting_name}' updated to '{setting_value}'")

def add_or_update_user(user_id: int, username: str, first_name: str, last_name: str, is_bot: bool):
    """Adds a new user or updates an existing one."""
    user_data = users_collection.find_one({"id": user_id})
    if not user_data:
        users_collection.insert_one({
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "is_bot": is_bot,
            "date_added": datetime.now(),
            "last_active": datetime.now(),
            "biolink_exception": False # Default to false
        })
        logger.info(f"New user added: {username} ({user_id})")
    else:
        users_collection.update_one(
            {"id": user_id},
            {"$set": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "last_active": datetime.now()
            }}
        )

def add_violation(username: str, user_id: int, group_name: str, group_id: int, violation_type: str, original_content: str, case_name: str = None):
    """Records a violation in the database."""
    violation_entry = {
        "user_id": user_id,
        "username": username,
        "group_id": group_id,
        "group_name": group_name,
        "violation_type": violation_type,
        "original_content": original_content,
        "timestamp": datetime.now(),
        "case_name": case_name
    }
    violations_collection.insert_one(violation_entry)
    logger.warning(f"Violation recorded for user {user_id} in group {group_id}: {violation_type}")

def get_total_users():
    """Returns the total number of unique users."""
    return users_collection.count_documents({})

def get_total_violations():
    """Returns the total number of violations recorded."""
    return violations_collection.count_documents({})

def get_all_groups():
    """Returns a list of all connected groups."""
    return list(groups_collection.find({}))

def log_new_user_or_group(log_type: str, entity_id: int, entity_name: str, inviter_id: int = None, inviter_username: str = None):
    """Logs new group additions or new user joins."""
    log_entry = {
        "type": log_type, # "new_group" or "new_user"
        "entity_id": entity_id,
        "entity_name": entity_name,
        "timestamp": datetime.now(),
        "inviter_id": inviter_id,
        "inviter_username": inviter_username
    }
    logs_collection.insert_one(log_entry)
    logger.info(f"Log entry created: {log_type} for {entity_name} (ID: {entity_id})")

def set_user_biolink_exception(user_id: int, allowed: bool):
    """Sets or removes a user's exception for bio link filtering."""
    users_collection.update_one(
        {"id": user_id},
        {"$set": {"biolink_exception": allowed}},
        upsert=True # Create user if not exists
    )
    logger.info(f"User {user_id} biolink exception set to {allowed}")

def get_user_biolink_exception(user_id: int) -> bool:
    """Checks if a user has a bio link exception."""
    user_data = users_collection.find_one({"id": user_id})
    return user_data.get("biolink_exception", False) if user_data else False

# --- Keyword Management ---
def get_keyword_list(list_name: str) -> list[str]:
    """Retrieves a list of keywords by name (e.g., 'abusive_words', 'pornographic_keywords')."""
    keyword_doc = keywords_collection.find_one({"name": list_name})
    return keyword_doc.get("words", []) if keyword_doc else []

def add_keywords(list_name: str, keywords_to_add: list[str]) -> int:
    """Adds new keywords to a specific list. Returns count of added words."""
    existing_doc = keywords_collection.find_one({"name": list_name})
    if existing_doc:
        existing_words = set(existing_doc.get("words", []))
        added_count = 0
        for word in keywords_to_add:
            if word not in existing_words:
                existing_words.add(word)
                added_count += 1
        
        keywords_collection.update_one(
            {"name": list_name},
            {"$set": {"words": list(existing_words), "last_updated": datetime.now()}}
        )
        logger.info(f"Added {added_count} keywords to {list_name}.")
        return added_count
    else:
        # Create new list if it doesn't exist
        keywords_collection.insert_one({
            "name": list_name,
            "words": list(set(keywords_to_add)), # Ensure unique on initial insert
            "created_at": datetime.now(),
            "last_updated": datetime.now()
        })
        logger.info(f"Created new keyword list '{list_name}' with {len(set(keywords_to_add))} words.")
        return len(set(keywords_to_add))


def remove_keywords(list_name: str, keywords_to_remove: list[str]) -> int:
    """Removes keywords from a specific list. Returns count of removed words."""
    existing_doc = keywords_collection.find_one({"name": list_name})
    if existing_doc:
        existing_words = set(existing_doc.get("words", []))
        removed_count = 0
        for word in keywords_to_remove:
            if word in existing_words:
                existing_words.remove(word)
                removed_count += 1
        
        keywords_collection.update_one(
            {"name": list_name},
            {"$set": {"words": list(existing_words), "last_updated": datetime.now()}}
        )
        logger.info(f"Removed {removed_count} keywords from {list_name}.")
        return removed_count
    else:
        logger.warning(f"Keyword list '{list_name}' not found for removal.")
        return 0

def get_all_keyword_lists():
    """Returns a list of all defined keyword list names."""
    return [doc["name"] for doc in keywords_collection.find({}, {"name": 1})]
