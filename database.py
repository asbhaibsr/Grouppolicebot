# database.py

from pymongo import MongoClient
from config import (
    MONGO_URI_MESSAGES, MONGO_URI_BUTTONS, MONGO_URI_TRACKING, logger
)
from datetime import datetime

# --- MongoDB Setup ---
# Messages Database
try:
    client_messages = MongoClient(MONGO_URI_MESSAGES)
    db_messages = client_messages.bot_database_messages
    messages_collection = db_messages.messages
    logger.info("MongoDB (Messages) connection successful. Credit: @asbhaibsr")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB (Messages): {e}. Designed by @asbhaibsr")
    messages_collection = None # Set to None if connection fails

# Buttons Database
try:
    client_buttons = MongoClient(MONGO_URI_BUTTONS)
    db_buttons = client_buttons.bot_button_data
    buttons_collection = db_buttons.button_interactions
    logger.info("MongoDB (Buttons) connection successful. Credit: @asbhaibsr")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB (Buttons): {e}. Designed by @asbhaibsr")
    buttons_collection = None # Set to None if connection fails

# Tracking Database
try:
    client_tracking = MongoClient(MONGO_URI_TRACKING)
    db_tracking = client_tracking.bot_tracking_data
    group_tracking_collection = db_tracking.groups_data
    user_tracking_collection = db_tracking.users_data
    earning_tracking_collection = db_tracking.monthly_earnings_data
    reset_status_collection = db_tracking.reset_status
    biolink_exceptions_collection = db_tracking.biolink_exceptions # For biolink deletion exceptions
    owner_taught_responses_collection = db_tracking.owner_taught_responses
    conversational_learning_collection = db_tracking.conversational_learning
    logger.info("MongoDB (Tracking, Earning, Biolink Exceptions, Learning Data) connection successful. Credit: @asbhaibsr")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB (Tracking): {e}. Designed by @asbhaibsr")
    group_tracking_collection = user_tracking_collection = earning_tracking_collection = \
    reset_status_collection = biolink_exceptions_collection = owner_taught_responses_collection = \
    conversational_learning_collection = None # Set to None if connection fails


# --- Ensure Indexes and Default Values ---
if messages_collection:
    messages_collection.create_index([("timestamp", 1)])
    messages_collection.create_index([("user_id", 1)])

if earning_tracking_collection:
    earning_tracking_collection.create_index([("group_message_count", -1)])

if group_tracking_collection:
    group_tracking_collection.create_index("id", unique=True)
    # Ensure bot_enabled field exists for all groups, default to True
    group_tracking_collection.update_many(
        {"bot_enabled": {"$exists": False}},
        {"$set": {"bot_enabled": True}}
    )
    # Ensure new flags exist for all groups, default to False
    group_tracking_collection.update_many(
        {"linkdel_enabled": {"$exists": False}},
        {"$set": {"linkdel_enabled": False}}
    )
    group_tracking_collection.update_many(
        {"biolinkdel_enabled": {"$exists": False}},
        {"$set": {"biolinkdel_enabled": False}}
    )
    group_tracking_collection.update_many(
        {"usernamedel_enabled": {"$exists": False}},
        {"$set": {"usernamedel_enabled": False}}
    )

if user_tracking_collection:
    user_tracking_collection.create_index("id", unique=True)

if owner_taught_responses_collection:
    owner_taught_responses_collection.create_index([("trigger", 1)])

if conversational_learning_collection:
    conversational_learning_collection.create_index([("trigger", 1)])


# --- Database Interaction Functions ---

def add_or_update_group(group_id, name, connected_by_user_id):
    """ग्रुप को डेटाबेस में जोड़ता है या अपडेट करता है।"""
    if not group_tracking_collection: return
    group_data = {
        "id": group_id,
        "name": name,
        "connected_by_user_id": connected_by_user_id,
        "connected_at": datetime.utcnow(),
        "filter_abusive": True,
        "filter_pornographic_text": True,
        "filter_spam": True,
        "filter_links": True,
        "filter_bio_links": True, # बायो लिंक फ़िल्टरिंग वापस
        "welcome_message": "",
        "warn_count": {}, # {user_id: count}
        "slow_mode_enabled": False,
        "slow_mode_delay": 0,
        "bot_enabled": True, # आपके स्निपेट से
        "linkdel_enabled": False, # आपके स्निपेट से
        "biolinkdel_enabled": False, # आपके स्निपेट से
        "usernamedel_enabled": False # आपके स्निपेट से
    }
    group_tracking_collection.update_one({"id": group_id}, {"$set": group_data}, upsert=True)
    return group_tracking_collection.find_one({"id": group_id})

def get_group_settings(group_id):
    """ग्रुप सेटिंग्स प्राप्त करता है।"""
    if not group_tracking_collection: return None
    return group_tracking_collection.find_one({"id": group_id})

def update_group_setting(group_id, setting_name, value):
    """ग्रुप की एक सेटिंग को अपडेट करता है।"""
    if not group_tracking_collection: return
    group_tracking_collection.update_one({"id": group_id}, {"$set": {setting_name: value}})

def add_violation(user_id, group_id, violation_type, original_content, case_name=None):
    """एक उल्लंघन को डेटाबेस में लॉग करता है।"""
    if not violations_collection: return
    violation_data = {
        "user_id": user_id,
        "group_id": group_id,
        "violation_type": violation_type,
        "original_content": original_content,
        "violation_time": datetime.utcnow(),
        "case_name": case_name
    }
    violations_collection.insert_one(violation_data)

def get_user_biolink_exception(user_id):
    """चेक करता है कि यूज़र को बायो लिंक के लिए विशेष अनुमति मिली है या नहीं।"""
    if not biolink_exceptions_collection: return False
    return biolink_exceptions_collection.find_one({"user_id": user_id, "has_exception": True}) is not None

def set_user_biolink_exception(user_id, has_exception):
    """यूज़र की बायो लिंक अपवाद स्थिति सेट करता है।"""
    if not biolink_exceptions_collection: return
    biolink_exceptions_collection.update_one(
        {"user_id": user_id},
        {"$set": {"has_exception": has_exception, "updated_at": datetime.utcnow()}},
        upsert=True
    )

def get_all_groups():
    """सभी कनेक्टेड ग्रुप्स प्राप्त करता है।"""
    if not group_tracking_collection: return []
    return list(group_tracking_collection.find({}))

def get_total_users():
    """कुल ट्रैक किए गए यूज़र्स की संख्या प्राप्त करता है।"""
    if not user_tracking_collection: return 0
    return user_tracking_collection.count_documents({})

def get_total_violations():
    """कुल उल्लंघनों की संख्या प्राप्त करता है।"""
    if not violations_collection: return 0
    return violations_collection.count_documents({})

def add_or_update_user(user_id, username, first_name, last_name, is_bot):
    """यूज़र डेटा को डेटाबेस में जोड़ता या अपडेट करता है।"""
    if not user_tracking_collection: return
    user_data = {
        "id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "is_bot": is_bot,
        "last_active": datetime.utcnow()
    }
    user_tracking_collection.update_one({"id": user_id}, {"$set": user_data}, upsert=True)

def log_new_user_or_group(type_str, id_val, name, inviter_id=None, inviter_username=None):
    """नए यूज़र या ग्रुप जुड़ने को लॉग करता है।"""
    if not new_entries_log_collection: return
    log_data = {
        "type": type_str, # "new_group" or "new_user"
        "id": id_val,
        "name": name,
        "timestamp": datetime.utcnow(),
        "inviter_id": inviter_id,
        "inviter_username": inviter_username
    }
    new_entries_log_collection.insert_one(log_data)

# Owner-taught responses (आपके स्निपेट से)
def add_owner_taught_response(trigger, response):
    if not owner_taught_responses_collection: return
    owner_taught_responses_collection.update_one(
        {"trigger": trigger},
        {"$set": {"response": response, "timestamp": datetime.utcnow()}},
        upsert=True
    )

def get_owner_taught_response(trigger):
    if not owner_taught_responses_collection: return None
    return owner_taught_responses_collection.find_one({"trigger": trigger})

# Conversational learning (आपके स्निपेट से)
def add_conversational_learning(trigger, response):
    if not conversational_learning_collection: return
    conversational_learning_collection.update_one(
        {"trigger": trigger},
        {"$set": {"response": response, "timestamp": datetime.utcnow()}},
        upsert=True
    )

def get_conversational_learning_response(trigger):
    if not conversational_learning_collection: return None
    return conversational_learning_collection.find_one({"trigger": trigger})

# Function to get group status flags (आपके स्निपेट से)
def get_group_status_flags(group_id):
    if not group_tracking_collection: return {}
    group = group_tracking_collection.find_one({"id": group_id})
    if group:
        return {
            "bot_enabled": group.get("bot_enabled", True),
            "linkdel_enabled": group.get("linkdel_enabled", False),
            "biolinkdel_enabled": group.get("biolinkdel_enabled", False),
            "usernamedel_enabled": group.get("usernamedel_enabled", False)
        }
    return {}

# Function to update group status flags (आपके स्निपेट से)
def update_group_status_flag(group_id, flag_name, value):
    if not group_tracking_collection: return
    group_tracking_collection.update_one({"id": group_id}, {"$set": {flag_name: value}})

