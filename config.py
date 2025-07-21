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
CASE_LOG_CHANNEL_ID = int(os.getenv("CASE_LOG_CHANNEL_ID", "-1002717243409")) # <-- अपनी वास्तविक ID डालें
NEW_USER_GROUP_LOG_CHANNEL_ID = int(os.getenv("NEW_USER_GROUP_LOG_CHANNEL_ID", "-1002352329534")) # <-- अपनी वास्तविक ID डालें

# --- Owner and Support Info ---
OWNER_ID = int(os.getenv("OWNER_ID", "7315805581")) # <-- अपनी वास्तविक Telegram यूज़र ID को यहाँ डालें
UPDATE_CHANNEL_USERNAME = os.getenv("UPDATE_CHANNEL_USERNAME", "asbhai_bsr") # <-- अपने अपडेट चैनल का यूज़रनेम डालें (बिना @ के)
ASBHHAI_USERNAME = os.getenv("ASBHHAI_USERNAME", "asbhaibsr") # <-- अपने सपोर्ट यूजरनेम को यहाँ डालें

# --- Default Messages & URLs ---
WELCOME_MESSAGE_DEFAULT = "👋 नमस्ते {username}! {groupname} में आपका स्वागत है।"
# यहाँ अपनी बॉट फोटो का लिंक डालें। यह एक सीधा इमेज लिंक होना चाहिए (जैसे .jpg, .png)!
BOT_PHOTO_URL = os.getenv("BOT_PHOTO_URL", "https://envs.sh/PX8.jpg")
REPO_LINK = "https://github.com/your-github-username/your-repo-name" # <-- अपने GitHub रेपो का लिंक डालें

# --- Cooldowns ---
COMMAND_COOLDOWN_TIME = int(os.getenv("COMMAND_COOLDOWN_TIME", 5)) # सेकंड में

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_logs.log"), # लॉग फाइल में सेव करें
        logging.StreamHandler(sys.stdout) # कंसोल में प्रिंट करें
    ]
)
logger = logging.getLogger(__name__)
