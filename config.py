# config.py

import os
from dotenv import load_dotenv
import logging
import sys

# .env फ़ाइल से पर्यावरण चर (environment variables) लोड करें
load_dotenv()

# --- Core Bot Settings ---
# Telegram बॉट टोकन
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Telegram API ID (integer)
API_ID = int(os.getenv("API_ID"))
# Telegram API Hash
API_HASH = os.getenv("API_HASH")

# --- Log Channel IDs ---
# इन IDs को अपनी वास्तविक Telegram चैनल ID से बदलें।
# ये हमेशा नकारात्मक संख्याएँ होनी चाहिए, जैसे -1001234567890
# सुनिश्चित करें कि बॉट इन चैनलों का सदस्य है और संदेश भेजने की अनुमति है।
CASE_LOG_CHANNEL_ID = int(os.getenv("CASE_LOG_CHANNEL_ID")) 
NEW_USER_GROUP_LOG_CHANNEL_ID = int(os.getenv("NEW_USER_GROUP_LOG_CHANNEL_ID"))

# --- Owner and Support Info ---
# आपका Telegram यूज़र ID (integer)। यह बॉट के मालिक को कमांड एक्सेस देता है।
OWNER_ID = int(os.getenv("OWNER_ID")) 
# आपके अपडेट चैनल का यूज़रनेम (बिना '@' के)।
UPDATE_CHANNEL_USERNAME = os.getenv("UPDATE_CHANNEL_USERNAME", "asbhai_bsr")
# आपके व्यक्तिगत यूज़रनेम का लिंक/नाम (बिना '@' के) संपर्क के लिए।
ASBHAI_USERNAME = os.getenv("ASBHAI_USERNAME", "asbhaibsr") 

# --- Default Messages & URLs ---
# नए सदस्यों के लिए डिफ़ॉल्ट वेलकम मैसेज।
# {username} और {groupname} प्लेसहोल्डर्स को बॉट द्वारा बदल दिया जाएगा।
WELCOME_MESSAGE_DEFAULT = "👋 नमस्ते {username}! {groupname} में आपका स्वागत है।"
# आपकी बॉट फोटो का सीधा लिंक (जैसे .jpg, .png)। इसे .env में भी सेट किया जा सकता है।
BOT_PHOTO_URL = os.getenv("BOT_PHOTO_URL", "https://envs.sh/PX8.jpg")
# आपके GitHub रिपॉजिटरी का लिंक। इसे अपडेट करना न भूलें!
REPO_LINK = "https://github.com/your-github-username/your-repo-name" 

# --- Cooldowns ---
# कमांड के बीच न्यूनतम समय (सेकंड में) ताकि स्पैम को रोका जा सके।
COMMAND_COOLDOWN_TIME = int(os.getenv("COMMAND_COOLDOWN_TIME", 5))

# --- Logging Configuration ---
# Pyrogram लाइब्रेरी के लिए लॉगिंग स्तर सेट करें।
# DEBUG अधिक विस्तृत लॉगिंग के लिए, INFO सामान्य जानकारी के लिए।
logging.getLogger("pyrogram").setLevel(logging.INFO) 

# आपके एप्लिकेशन के लिए सामान्य लॉगिंग कॉन्फ़िगरेशन।
logging.basicConfig(
    level=logging.INFO, # डिफ़ॉल्ट स्तर आपके एप्लिकेशन लॉग के लिए
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_logs.log"), # लॉग को 'bot_logs.log' नामक फाइल में सेव करें
        logging.StreamHandler(sys.stdout) # लॉग को कंसोल (टर्मिनल) में प्रिंट करें
    ]
)
# एक लॉगर इंस्टेंस प्राप्त करें जिसका उपयोग आपके कोड में लॉग संदेशों को लिखने के लिए किया जा सके।
logger = logging.getLogger(__name__)

# --- Configuration Validation ---
# यह सुनिश्चित करता है कि सभी आवश्यक पर्यावरण चर सेट हैं।
# यदि कोई भी आवश्यक चर मिसिंग है, तो बॉट शुरू नहीं होगा और एक गंभीर त्रुटि लॉग करेगा।
if not all([BOT_TOKEN, API_ID, API_HASH, CASE_LOG_CHANNEL_ID, NEW_USER_GROUP_LOG_CHANNEL_ID, OWNER_ID]):
    logger.critical("आवश्यक पर्यावरण चर (`BOT_TOKEN`, `API_ID`, `API_HASH`, `CASE_LOG_CHANNEL_ID`, `NEW_USER_GROUP_LOG_CHANNEL_ID`, `OWNER_ID`) सेट नहीं हैं। कृपया अपनी `.env` फ़ाइल जांचें और उन्हें प्रदान करें।")
    sys.exit(1) # यदि आवश्यक कॉन्फ़िगरेशन नहीं है तो बॉट को तुरंत बंद करें
