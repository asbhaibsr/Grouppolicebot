# config.py

import os
from dotenv import load_dotenv
import logging
import sys

load_dotenv()

# --- Core Bot Settings ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# --- Log Channel IDs ---
# इन्हें अपनी वास्तविक Telegram चैनल ID से बदलें।
# ये नकारात्मक संख्याएँ होनी चाहिए, जैसे -1001234567890
# हमने डिफ़ॉल्ट मान हटा दिए हैं ताकि आप .env में इन्हें सेट करें।
# यदि ये सेट नहीं होते हैं तो बॉट शुरू नहीं होगा।
CASE_LOG_CHANNEL_ID = int(os.getenv("CASE_LOG_CHANNEL_ID")) # <-- अपनी वास्तविक ID डालें (उदाहरण: -1001234567890)
NEW_USER_GROUP_LOG_CHANNEL_ID = int(os.getenv("NEW_USER_GROUP_LOG_CHANNEL_ID")) # <-- अपनी वास्तविक ID डालें (उदाहरण: -1001987654321)

# --- Owner and Support Info ---
OWNER_ID = int(os.getenv("OWNER_ID")) # <-- अपनी वास्तविक Telegram यूज़र ID को यहाँ डालें
UPDATE_CHANNEL_USERNAME = os.getenv("UPDATE_CHANNEL_USERNAME", "asbhai_bsr") # <-- अपने अपडेट चैनल का यूज़रनेम डालें (बिना @ के)
ASBHAI_USERNAME = os.getenv("ASBHHAI_USERNAME", "asbhaibsr") # <-- 'H' हटा दिया, अब यह bot.py से मेल खाता है

# --- Default Messages & URLs ---
WELCOME_MESSAGE_DEFAULT = "👋 नमस्ते {username}! {groupname} में आपका स्वागत है।"
# यहाँ अपनी बॉट फोटो का लिंक डालें। यह एक सीधा इमेज लिंक होना चाहिए (जैसे .jpg, .png)!
BOT_PHOTO_URL = os.getenv("BOT_PHOTO_URL", "https://envs.sh/PX8.jpg")
REPO_LINK = "https://github.com/your-github-username/your-repo-name" # <-- अपने GitHub रेपो का लिंक डालें (इसे अपडेट करना न भूलें!)

# --- Cooldowns ---
COMMAND_COOLDOWN_TIME = int(os.getenv("COMMAND_COOLDOWN_TIME", 5)) # सेकंड में

# --- Logging Configuration ---
# Pyrogram logging level set karein
logging.getLogger("pyrogram").setLevel(logging.INFO) # DEBUG या INFO कर सकते हैं

logging.basicConfig(
    level=logging.INFO, # Default level for your application logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_logs.log"), # लॉग फाइल में सेव करें
        logging.StreamHandler(sys.stdout) # कंसोल में प्रिंट करें
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration Validation ---
# यह सुनिश्चित करता है कि आवश्यक पर्यावरण चर सेट हैं
if not all([BOT_TOKEN, API_ID, API_HASH, CASE_LOG_CHANNEL_ID, NEW_USER_GROUP_LOG_CHANNEL_ID, OWNER_ID]):
    logger.critical("आवश्यक पर्यावरण चर (`BOT_TOKEN`, `API_ID`, `API_HASH`, `CASE_LOG_CHANNEL_ID`, `NEW_USER_GROUP_LOG_CHANNEL_ID`, `OWNER_ID`) सेट नहीं हैं। कृपया अपनी `.env` फ़ाइल जांचें और उन्हें प्रदान करें।")
    sys.exit(1) # बॉट को तुरंत बंद करें यदि आवश्यक कॉन्फ़िगरेशन नहीं है
