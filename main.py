# main.py

from bot import app
from server import run_flask_server
import threading
import os
import asyncio
from config import logger

async def start_pyrogram():
    """Pyrogram क्लाइंट को शुरू करता है।"""
    logger.info("Starting Pyrogram client...")
    try:
        await app.start()
        logger.info("Pyrogram client started.")
        # यह बॉट को तब तक चालू रखेगा जब तक प्रोग्राम बंद न हो जाए
        await asyncio.Event().wait() # बॉट को चालू रखने के लिए
    except Exception as e:
        logger.error(f"Error starting Pyrogram client: {e}")
        # यहां कुछ रिकवरी लॉजिक या एग्जिट हो सकता है
        sys.exit(1)


def main():
    # Flask सर्वर को एक अलग थ्रेड में चलाएं (Koyeb हेल्थ चेक के लिए)
    logger.info("Starting Flask server for health check...")
    flask_thread = threading.Thread(target=run_flask_server)
    flask_thread.daemon = True # मुख्य प्रोग्राम बंद होने पर थ्रेड भी बंद हो जाएगा
    flask_thread.start()

    # Pyrogram क्लाइंट को asyncio इवेंट लूप में शुरू करें
    asyncio.run(start_pyrogram())


if __name__ == "__main__":
    main()

