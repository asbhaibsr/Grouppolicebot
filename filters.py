import re
import os
from dotenv import load_dotenv
from pyrogram import filters, Client
from pyrogram.types import Message

# Load environment variables (optional)
load_dotenv()

# --- Helper function to load keywords from a file ---
def load_keywords_from_file(filename: str) -> list[str]:
    """Loads keywords from a text file, one keyword per line."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # Filter out empty lines and strip whitespace
            keywords = [line.strip().lower() for line in f if line.strip()]
        return keywords
    except FileNotFoundError:
        print(f"Warning: Keyword file '{filename}' not found. Using default empty list.")
        return []
    except Exception as e:
        print(f"Error loading keywords from '{filename}': {e}. Using default empty list.")
        return []

# --- Keyword Lists (अब ये फाइलों से लोड होंगे) ---
ABUSIVE_WORDS = load_keywords_from_file("abusive_words.txt")
PORNOGRAPHIC_KEYWORDS = load_keywords_from_file("pornographic_words.txt")

# यदि फाइलें नहीं मिलीं या खाली हैं, तो पर्यावरण वेरिएबल से डिफ़ॉल्ट प्रदान करें
if not ABUSIVE_WORDS:
    ABUSIVE_WORDS = os.getenv("ABUSIVE_WORDS_DEFAULT", "fuck,bitch,asshole,madarchod,behenchod,randi").split(',')
    print("Using default ABUSIVE_WORDS from environment variable or hardcoded.")
if not PORNOGRAPHIC_KEYWORDS:
    PORNOGRAPHIC_KEYWORDS = os.getenv("PORNOGRAPHIC_KEYWORDS_DEFAULT", "porn,sex,nude,xxx,boobs,bobs,chudai,lund,chut").split(',')
    print("Using default PORNOGRAPHIC_KEYWORDS from environment variable or hardcoded.")


# Regular expression for common link patterns
LINK_PATTERN = re.compile(r'https?://[^\s]+|www\.[^\s]+|\b\w+\.(com|org|net|in|co|gov|edu)\b')

# Regular expression for Telegram usernames (e.g., @channel, @bot)
USERNAME_PATTERN = re.compile(r'@[\w\d_]{5,32}')


# --- Custom Filter Functions ---

# यह फ़िल्टर चेक करता है कि मैसेज एडिटेड नहीं है.
@filters.create
async def is_not_edited(_, __, message: Message):
    """
    Checks if a message is not an edited message.
    Usage: filters.text & filters.group & is_not_edited
    """
    return message.edit_date is None

# यह फ़िल्टर चेक करता है कि यूज़र वेलकम मैसेज इनपुट के लिए इंतज़ार कर रहा है या नहीं.
@filters.create
async def is_awaiting_welcome_message_input(_, __, message: Message):
    """
    Checks if a user is currently awaiting welcome message input.
    """
    # Circular import से बचने के लिए इसे यहां runtime पर import किया गया है.
    # अगर bot.py से import करते हैं और bot.py filters.py को import करता है,
    # तो circular dependency बन जाती है.
    try:
        from bot import user_data_awaiting_input
    except ImportError:
        # अगर bot.py अभी तक पूरी तरह से लोड नहीं हुआ है, तो False return करें.
        return False

    return message.from_user.id in user_data_awaiting_input and \
           'awaiting_welcome_message_input' in user_data_awaiting_input[message.from_user.id]

# यह फ़िल्टर चेक करता है कि प्राइवेट टेक्स्ट मैसेज '/' या '!' से शुरू नहीं होता है.
@filters.create
async def is_not_command_or_exclamation(_, __, message: Message):
    """
    Checks if a private text message does not start with '/' or '!'.
    """
    return message.text and not (message.text.startswith('/') or message.text.startswith('!'))


# --- Existing Utility Functions (ये functions filters.py में ही रहेंगे) ---

def is_abusive(text: str) -> bool:
    """Checks if the text contains abusive words."""
    text_lower = text.lower()
    for word in ABUSIVE_WORDS:
        # We use word boundaries (\b) to match whole words only.
        # This prevents matching "ass" in "class".
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            return True
    return False

def is_pornographic_text(text: str) -> bool:
    """Checks if the text contains pornographic keywords."""
    text_lower = text.lower()
    for keyword in PORNOGRAPHIC_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            return True
    return False

def contains_links(text: str) -> bool:
    """Checks if the text contains any common link patterns."""
    return bool(LINK_PATTERN.search(text))

def is_spam(text: str, max_length: int = 2000, min_unique_chars_ratio: float = 0.3) -> bool:
    """
    Checks for potential spam based on length and character repetition.
    Args:
        text (str): The message text.
        max_length (int): Maximum allowed message length before considered potentially spam.
        min_unique_chars_ratio (float): Minimum ratio of unique characters to total characters.
    """
    if len(text) > max_length:
        return True
    
    # Check for excessive repetition (e.g., "aaaaaaaaaaa")
    if len(text) > 50: # Only check for longer messages
        unique_chars = set(text)
        if len(unique_chars) / len(text) < min_unique_chars_ratio:
            return True
        
    return False

async def has_bio_link(client, user_id: int) -> bool:
    """Checks if a user's bio (description) contains a link.
    This requires the bot to be able to get user's full profile which might not always be possible
    or publicly exposed via get_users() unless the bot is an admin in a common chat.
    For simplicity, this function attempts to get user details and check their bio.
    """
    try:
        user_info = await client.get_users(user_id)
        if user_info and user_info.bio:
            return bool(LINK_PATTERN.search(user_info.bio))
    except Exception as e:
        print(f"Error checking bio for user {user_id}: {e}")
        return False
    return False

def contains_usernames(text: str) -> bool:
    """Checks if the text contains Telegram usernames (e.g., @channel, @bot)."""
    return bool(USERNAME_PATTERN.search(text))
