# filters.py

import re
from config import URL_PATTERN_REGEX
from pyrogram import Client # get_users के लिए


# गाली-गलौज और पॉर्नोग्राफिक शब्दों की लिस्ट
# इन्हें और व्यापक बनाने की आवश्यकता हो सकती है
ABUSIVE_WORDS = [
    "gali", "gandu", "bsdk", "madarchod", "behenchod", "kutte", "harami", "fuck", "shit",
    "asshole", "bitch", "cunt", "chutiya", "randi", "tera baap", "teri maa ka", "lodu",
    "bhadwa", "chutiye", "haraami", "kamine", "lavde", "saala", "saali", "चूतिया", "मादरचोद", "बहनचोद"
]
PORNOGRAPHIC_WORDS = [
    "sex", "porn", "nude", "boobs", "pussy", "dick", "c**k", "vagina", "ass", "naked",
    "erotic", "xxx", "fuck", "cum", "masturbate", "gangbang", "hentai", "s*x", "n**d",
    "नंगा", "अश्लील", "चोद", "लंड", "गांड"
]

def _is_word_present(text, word_list):
    """सहायक फंक्शन: टेक्स्ट में किसी भी शब्द की उपस्थिति की जांच करता है।"""
    text_lower = text.lower()
    for word in word_list:
        # Regex का उपयोग करके पूरे शब्द का मिलान करें (boundary checks)
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            return True
    return False

def is_abusive(text):
    """चेक करता है कि टेक्स्ट में गाली-गलौज है या नहीं।"""
    if not text: return False
    return _is_word_present(text, ABUSIVE_WORDS)

def is_pornographic_text(text):
    """चेक करता है कि टेक्स्ट में पॉर्नोग्राफिक शब्द हैं या नहीं।"""
    if not text: return False
    return _is_word_present(text, PORNOGRAPHIC_WORDS)

def contains_links(text):
    """चेक करता है कि टेक्स्ट में कोई लिंक है या नहीं।"""
    if not text: return False
    return bool(URL_PATTERN_REGEX.search(text))

def is_spam(text):
    """चेक करता है कि टेक्स्ट स्पैम है या नहीं (सरल लॉजिक)।"""
    if not text: return False
    # यह एक बहुत ही सरल स्पैम डिटेक्शन है। आप इसे और परिष्कृत कर सकते हैं।
    if len(text) > 1000 or text.count('!') > 15 or text.count('?') > 15:
        return True
    return False

async def has_bio_link(client: Client, user_id: int):
    """
    यूज़र के बायो में लिंक है या नहीं, यह चेक करता है।
    Pyrogram बॉट क्लाइंट का उपयोग करके यूज़र ऑब्जेक्ट को फ़ेच करने का प्रयास करता है।
    """
    try:
        user_info = await client.get_users(user_id)
        if user_info and user_info.bio:
            return contains_links(user_info.bio)
    except Exception as e:
        # यदि बॉट के पास बायो तक पहुंचने की अनुमति नहीं है, तो यह यहां फेल हो सकता है।
        # सामान्यत: बॉट क्लाइंट के पास सार्वजनिक बायो तक पहुंच होती है।
        print(f"Error fetching user bio for {user_id}: {e}")
    return False

# यूज़रनेम डिटेक्शन (आपके स्निपेट के आधार पर)
def contains_usernames(text):
    """चेक करता है कि टेक्स्ट में Telegram यूजरनेम (@username) है या नहीं।"""
    if not text: return False
    return bool(re.search(r"@[\w_]{5,}", text)) # @ के बाद कम से कम 5 अक्षर/अंडरस्कोर


