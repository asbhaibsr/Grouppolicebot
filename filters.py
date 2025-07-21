import re
from pyrogram.types import Message
from pyrogram.filters import create
from config import logger
from database import get_keyword_list, get_user_biolink_exception
import asyncio

# Global lists for keywords, loaded from DB
ABUSIVE_WORDS = []
PORNOGRAPHIC_KEYWORDS = []

def load_keywords_from_db():
    """Loads abusive and pornographic keywords from the database."""
    global ABUSIVE_WORDS, PORNOGRAPHIC_KEYWORDS
    ABUSIVE_WORDS = [word.lower() for word in get_keyword_list("abusive_words")]
    PORNOGRAPHIC_KEYWORDS = [word.lower() for word in get_keyword_list("pornographic_keywords")]
    logger.info(f"Loaded {len(ABUSIVE_WORDS)} abusive words and {len(PORNOGRAPHIC_KEYWORDS)} pornographic keywords from DB.")

# Load keywords on bot startup
load_keywords_from_db()

# --- Common Helper Functions ---

def contains_word_from_list(text: str, word_list: list) -> bool:
    """Checks if the text contains any word from the given list."""
    text_lower = text.lower()
    for word in word_list:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            return True
    return False

# --- Message Content Filters ---

def is_abusive(text: str) -> bool:
    """Checks if the text contains abusive words."""
    return contains_word_from_list(text, ABUSIVE_WORDS)

def is_pornographic_text(text: str) -> bool:
    """Checks if the text contains pornographic keywords."""
    return contains_word_from_list(text, PORNOGRAPHIC_KEYWORDS)

def contains_links(text: str) -> bool:
    """Checks if the text contains any URLs."""
    # Regex to detect common URL patterns
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.search(text))

def is_spam(text: str, min_length: int = 200, repetition_threshold: int = 3) -> bool:
    """
    Checks if the text is spam based on length and repetition.
    - min_length: If message is longer than this, check for repetition.
    - repetition_threshold: Number of times a pattern can repeat.
    """
    if len(text) > min_length:
        # Check for character repetition (e.g., "aaaaaaa")
        if re.search(r'(.)\1{' + str(repetition_threshold - 1) + r',}', text):
            return True
        # Check for word repetition (e.g., "hello hello hello")
        words = text.split()
        if len(words) > 1:
            for i in range(len(words) - repetition_threshold + 1):
                if all(words[i] == words[i+j] for j in range(repetition_threshold)):
                    return True
    return False

async def has_bio_link(client, user_id: int) -> bool:
    """Checks if a user's bio (about section) contains a link."""
    try:
        user_info = await client.get_users(user_id)
        if user_info and user_info.bio:
            return contains_links(user_info.bio)
        return False
    except Exception as e:
        logger.error(f"Error checking bio for user {user_id}: {e}")
        return False

def contains_usernames(text: str) -> bool:
    """Checks if the text contains Telegram usernames (e.g., @username, t.me/username)."""
    # Regex to find @usernames or t.me/usernames
    username_pattern = re.compile(r'(?:@|t\.me/)([a-zA-Z0-9_]{5,})')
    return bool(username_pattern.search(text))

# --- Custom Pyrogram Filters ---

@create
async def is_not_edited(_, __, message: Message):
    """Filters out edited messages."""
    return message.edit_date is None

@create
async def is_awaiting_welcome_message_input(_, __, message: Message):
    """Checks if the user is currently awaiting welcome message input."""
    from bot import user_data_awaiting_input
    return message.from_user.id in user_data_awaiting_input and 'awaiting_welcome_message_input' in user_data_awaiting_input[message.from_user.id]

@create
async def is_not_command_or_exclamation(_, __, message: Message):
    """Checks if the message is not a command or starts with an exclamation mark."""
    if message.text:
        return not (message.text.startswith('/') or message.text.startswith('!'))
    return True
