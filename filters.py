import re
from pyrogram import Client
from pyrogram.enums import ChatType
from config import logger

# --- Text Content Filters ---

def is_abusive(text: str) -> bool:
    """गाली-गलौज वाले शब्दों का पता लगाता है।"""
    # यहाँ कुछ सामान्य गाली-गलौज वाले शब्द जोड़ें (केस-असंवेदनशील)
    abusive_words = [
        r'\bchutiya\b', r'\bmadarchod\b', r'\bbehenchod\b', r'\bkutta\b',
        r'\bharami\b', r'\bsale\b', r'\bbhosdike\b', r'\blund\b',
        r'\bfuck\b', r'\basshole\b', r'\bdick\b', r'\bcock\b', r'\bsht\b',
        r'\bgaandu\b', r'\bsala\b', r'\bterimaaki\b', r'\bpenchod\b',
        r'\bchod\b', r'\bjhant\b', r'\bkutiya\b', r'\bchinal\b',
        r'\bsaad\b', r'\bharaamzaada\b'
    ]
    # रेगुलर एक्सप्रेशन को केस-असंवेदनशील बनाने के लिए re.IGNORECASE का उपयोग करें
    for word in abusive_words:
        if re.search(word, text, re.IGNORECASE):
            logger.debug(f"Abusive word '{word}' detected in text.")
            return True
    return False

def is_pornographic_text(text: str) -> bool:
    """पॉर्नोग्राफिक सामग्री वाले शब्दों का पता लगाता है।"""
    porn_words = [
        r'\bsex\b', r'\bnude\b', r'\bporn\b', r'\bxxx\b', r'\bbdsm\b',
        r'\bhot\b', r'\bboobs\b', r'\btits\b', r'\bvagina\b', r'\bpenis\b',
        r'\brape\b', r'\bincest\b', r'\bhijabporno\b', r'\bfemdom\b',
        r'\bnaked\b', r'\bslut\b', r'\bwhore\b', r'\bbitch\b',
        r'\bmasterbation\b', r'\bintercourse\b', r'\borgy\b',
        r'\bgangbang\b', r'\bthreesome\b', r'\borgasm\b'
    ]
    for word in porn_words:
        if re.search(word, text, re.IGNORECASE):
            logger.debug(f"Pornographic word '{word}' detected in text.")
            return True
    return False

def contains_links(text: str) -> bool:
    """लिंक का पता लगाता है (http/https, t.me, Telegram, etc.)।"""
    # इसमें Telegram t.me लिंक्स भी शामिल हैं
    link_pattern = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    telegram_link_pattern = r"(?i)\b(t\.me|telegram\.me|telegram\.dog)/[a-zA-Z0-9_]+"
    
    if re.search(link_pattern, text) or re.search(telegram_link_pattern, text):
        logger.debug(f"Link detected in text: '{text}'")
        return True
    return False

def is_spam(text: str) -> bool:
    """
    स्पैम (अत्यधिक लंबा, अत्यधिक दोहराव) का पता लगाता है।
    यह एक बुनियादी कार्यान्वयन है; इसे अधिक परिष्कृत किया जा सकता है।
    """
    # यदि संदेश बहुत लंबा है (उदाहरण के लिए, 500 वर्णों से अधिक)
    if len(text) > 500:
        logger.debug(f"Text is too long ({len(text)} chars), considered spam.")
        return True
    
    # यदि संदेश में एक ही शब्द बहुत बार दोहराया गया है
    words = text.lower().split()
    if len(words) > 10: # यदि पर्याप्त शब्द हैं
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        for word, count in word_counts.items():
            if count / len(words) > 0.4: # यदि एक ही शब्द 40% से अधिक बार दोहराया गया है
                logger.debug(f"Word '{word}' repeated excessively, considered spam.")
                return True
    
    return False

def contains_usernames(text: str) -> bool:
    """अन्य चैनल या बॉट के यूज़रनेम का पता लगाता है (जैसे @username)."""
    # @username पैटर्न का पता लगाता है, लेकिन बॉट के खुद के यूज़रनेम को छोड़ देता है।
    # Pyrogram क्लाइंट का उपयोग करने के लिए इसे Client और Message ऑब्जेक्ट की आवश्यकता होगी
    # इसलिए यह सीधे `filters.py` में नहीं हो सकता है जैसा कि `server.py` से कॉल किया जाता है।
    # इसके बजाय, यह लॉजिक `server.py` में होना चाहिए जहाँ `client.me.username` उपलब्ध हो।
    # हालाँकि, एक सामान्य `@` पैटर्न अभी भी पता लगाया जा सकता है।
    
    # एक बुनियादी यूज़रनेम पैटर्न
    username_pattern = r"@[\w]+"
    
    if re.search(username_pattern, text):
        logger.debug(f"Username detected in text: '{text}'")
        return True
    return False


# --- User Profile Filters (async for API calls) ---

async def has_bio_link(client: Client, user_id: int) -> bool:
    """चेक करता है कि यूज़र के बायो में कोई लिंक है या नहीं।"""
    try:
        user_info = await client.get_users(user_id)
        if user_info.bio:
            if contains_links(user_info.bio):
                logger.debug(f"Bio link detected for user {user_id}: '{user_info.bio}'")
                return True
    except Exception as e:
        logger.error(f"Error checking bio link for user {user_id}: {e}", exc_info=True)
    return False

# नोट: Pyrogram फिल्टर्स जो `filters.create` का उपयोग करते हैं, उन्हें `(client, update)` सिग्नेचर लेना चाहिए।
# ऊपर के फंक्शन्स सीधे `handle_group_message` जैसे फंक्शन्स द्वारा कॉल किए जाते हैं,
# इसलिए उन्हें Pyrogram के फिल्टर ऑब्जेक्ट्स की आवश्यकता नहीं होती है जब तक कि उन्हें सीधे `@pyrogram_app.on_message(filters.create(...))` में उपयोग न किया जाए।
# `server.py` में `awaiting_welcome_message_input_filter` एक कस्टम फिल्टर का उदाहरण है।
