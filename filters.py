import re
import os
from dotenv import load_dotenv

# Load environment variables for sensitive keywords (optional)
load_dotenv()

# --- Keyword Lists (आप इन्हें अपनी ज़रूरत के हिसाब से अपडेट कर सकते हैं) ---
# Environment variable से भी लोड कर सकते हैं
ABUSIVE_WORDS = os.getenv("ABUSIVE_WORDS", "fuck,bitch,asshole,madarchod,behenchod,randi").split(',')
PORNOGRAPHIC_KEYWORDS = os.getenv("PORNOGRAPHIC_KEYWORDS", "porn,sex,nude,xxx,boobs,bobs,chudai,lund,chut").split(',')

# Regular expression for common link patterns
LINK_PATTERN = re.compile(r'https?://[^\s]+|www\.[^\s]+|\b\w+\.(com|org|net|in|co|gov|edu)\b')

# Regular expression for Telegram usernames (e.g., @channel, @bot)
USERNAME_PATTERN = re.compile(r'@[\w\d_]{5,32}')


def is_abusive(text: str) -> bool:
    """Checks if the text contains abusive words."""
    text_lower = text.lower()
    for word in ABUSIVE_WORDS:
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
        # If bot cannot access user's full profile (e.g., user is private or not in a common chat)
        # It's better to log and return False rather than crash.
        print(f"Error checking bio for user {user_id}: {e}")
        return False
    return False

def contains_usernames(text: str) -> bool:
    """Checks if the text contains Telegram usernames (e.g., @channel, @bot)."""
    return bool(USERNAME_PATTERN.search(text))

