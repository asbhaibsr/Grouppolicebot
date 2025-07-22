import os
from pymongo import MongoClient
from datetime import datetime
from config import logger

# MongoDB कनेक्शन स्ट्रिंग environment variables से
MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    logger.error("MONGODB_URI environment variable not set. Exiting.")
    exit(1)

try:
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client.get_database("GroupPoliceBotDB")
    
    # Collections
    users_collection = db.get_collection("users")
    groups_collection = db.get_collection("groups")
    violations_collection = db.get_collection("violations")
    logs_collection = db.get_collection("logs") # नया लॉगिंग कलेक्शन

    logger.info("MongoDB connected successfully!")

except Exception as e:
    logger.critical(f"Failed to connect to MongoDB: {e}", exc_info=True)
    exit(1)

# --- User Functions ---
def add_or_update_user(user_id: int, username: str, first_name: str, last_name: str, is_bot: bool):
    """
    यूज़र डेटाबेस में यूज़र को जोड़ता या अपडेट करता है।
    """
    user_data = {
        "id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "is_bot": is_bot,
        "last_updated": datetime.now()
    }
    try:
        users_collection.update_one(
            {"id": user_id},
            {"$set": user_data},
            upsert=True
        )
        logger.debug(f"User {user_id} data added/updated in DB.")
    except Exception as e:
        logger.error(f"Error adding/updating user {user_id}: {e}", exc_info=True)

def get_user_by_id(user_id: int):
    """
    ID के आधार पर यूज़र डेटा प्राप्त करता है।
    """
    try:
        user = users_collection.find_one({"id": user_id})
        return user
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}", exc_info=True)
        return None

def get_total_users():
    """
    डेटाबेस में कुल यूज़र्स की संख्या प्राप्त करता है।
    """
    try:
        return users_collection.count_documents({})
    except Exception as e:
        logger.error(f"Error getting total users: {e}", exc_info=True)
        return 0

# --- Group Functions ---
def add_or_update_group(group_id: int, group_name: str, added_by_user_id: int = None):
    """
    ग्रुप को डेटाबेस में जोड़ता है या उसकी सेटिंग्स को अपडेट करता है।
    यदि ग्रुप पहले से मौजूद नहीं है, तो डिफ़ॉल्ट सेटिंग्स के साथ जोड़ता है।
    """
    default_settings = {
        "bot_enabled": True,
        "filter_abusive": True,
        "filter_pornographic_text": True,
        "filter_spam": True,
        "filter_links": True,
        "filter_bio_links": True,
        "usernamedel_enabled": True, # सुनिश्चित करें कि यह भी डिफ़ॉल्ट रूप से शामिल है
        "welcome_message": "👋 नमस्ते {username}! {groupname} में आपका स्वागत है।",
        "case_log_channel_id": None, # अगर आप ग्रुप-विशिष्ट लॉग चाहते हैं
        "new_user_group_log_channel_id": None # अगर आप ग्रुप-विशिष्ट लॉग चाहते हैं
    }

    group_data = {
        "id": group_id,
        "name": group_name,
        "added_by": added_by_user_id,
        "last_updated": datetime.now()
    }
    try:
        existing_group = groups_collection.find_one({"id": group_id})
        if existing_group:
            # केवल 'name' और 'last_updated' को अपडेट करें, सेटिंग्स को नहीं छेड़ें
            groups_collection.update_one(
                {"id": group_id},
                {"$set": {"name": group_name, "last_updated": datetime.now()}}
            )
            logger.debug(f"Group {group_id} data updated in DB.")
        else:
            # नए ग्रुप के लिए डिफ़ॉल्ट सेटिंग्स के साथ डालें
            group_data.update(default_settings)
            groups_collection.insert_one(group_data)
            logger.info(f"New group {group_id} ({group_name}) added to DB with default settings.")
    except Exception as e:
        logger.error(f"Error adding/updating group {group_id}: {e}", exc_info=True)

def get_group_settings(group_id: int):
    """
    ग्रुप की सेटिंग्स प्राप्त करता है।
    """
    try:
        settings = groups_collection.find_one({"id": group_id})
        return settings
    except Exception as e:
        logger.error(f"Error getting group settings for {group_id}: {e}", exc_info=True)
        return None

def update_group_setting(group_id: int, setting_name: str, setting_value):
    """
    एक विशिष्ट ग्रुप सेटिंग को अपडेट करता है।
    """
    try:
        groups_collection.update_one(
            {"id": group_id},
            {"$set": {setting_name: setting_value}}
        )
        logger.info(f"Group {group_id} setting '{setting_name}' updated to '{setting_value}'.")
    except Exception as e:
        logger.error(f"Error updating group {group_id} setting '{setting_name}': {e}", exc_info=True)

def get_all_groups():
    """
    सभी कनेक्टेड ग्रुप्स को लिस्ट करता है।
    """
    try:
        return list(groups_collection.find({}))
    except Exception as e:
        logger.error(f"Error getting all groups: {e}", exc_info=True)
        return []

# --- Violation Functions ---
def add_violation(user_id: int, username: str, group_id: int, group_name: str, violation_type: str, original_content: str, case_name: str = None):
    """
    डेटाबेस में एक उल्लंघन रिकॉर्ड करता है।
    """
    violation_data = {
        "user_id": user_id,
        "username": username,
        "group_id": group_id,
        "group_name": group_name,
        "violation_type": violation_type,
        "original_content": original_content,
        "case_name": case_name,
        "timestamp": datetime.now()
    }
    try:
        violations_collection.insert_one(violation_data)
        logger.info(f"Violation recorded for user {user_id} in group {group_id}: {violation_type}.")
    except Exception as e:
        logger.error(f"Error adding violation for user {user_id}: {e}", exc_info=True)

def get_total_violations():
    """
    कुल उल्लंघनों की संख्या प्राप्त करता है।
    """
    try:
        return violations_collection.count_documents({})
    except Exception as e:
        logger.error(f"Error getting total violations: {e}", exc_info=True)
        return 0

# --- Bio Link Exception Functions ---
def get_user_biolink_exception(user_id: int) -> bool:
    """
    चेक करता है कि किसी यूज़र को बायो लिंक के लिए विशेष अनुमति मिली है या नहीं।
    """
    try:
        user_data = users_collection.find_one({"id": user_id})
        return user_data.get("biolink_exception", False) if user_data else False
    except Exception as e:
        logger.error(f"Error getting biolink exception for user {user_id}: {e}", exc_info=True)
        return False

def set_user_biolink_exception(user_id: int, status: bool):
    """
    किसी यूज़र के लिए बायो लिंक अपवाद स्थिति सेट करता है।
    """
    try:
        users_collection.update_one(
            {"id": user_id},
            {"$set": {"biolink_exception": status}},
            upsert=True
        )
        logger.info(f"Biolink exception for user {user_id} set to {status}.")
    except Exception as e:
        logger.error(f"Error setting biolink exception for user {user_id}: {e}", exc_info=True)

# --- General Logging Function (for new user/group adds) ---
def log_new_user_or_group(log_type: str, entity_id: int, entity_name: str, inviter_id: int = None, inviter_username: str = None):
    """
    नए यूज़र या ग्रुप जुड़ने को डेटाबेस में लॉग करता है।
    """
    log_data = {
        "log_type": log_type, # "new_user" or "new_group" or "left_user"
        "entity_id": entity_id,
        "entity_name": entity_name,
        "timestamp": datetime.now()
    }
    if inviter_id:
        log_data["inviter_id"] = inviter_id
        log_data["inviter_username"] = inviter_username
    
    try:
        logs_collection.insert_one(log_data)
        logger.info(f"Logged new {log_type}: {entity_name} ({entity_id}).")
    except Exception as e:
        logger.error(f"Error logging new {log_type} {entity_id}: {e}", exc_info=True)
