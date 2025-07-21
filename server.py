from flask import Flask, jsonify
import threading
import asyncio
import time
import os
import sys

# config से logger इम्पोर्ट करें
from config import logger

# bot.py से Pyrogram app और main async task को इम्पोर्ट करें
from bot import app as bot_app, main as bot_main_task # <-- यहाँ बदलाव है

# database.py से MongoDB client को import करें
from database import client as db_client # database logger की अब सीधे यहाँ ज़रूरत नहीं, config logger बेहतर है

# Flask app initialize karein
flask_app = Flask(__name__) # Flask app का नाम app से बदलकर flask_app किया ताकि Pyrogram app से conflict न हो

# Pyrogram bot को चलाने के लिए एक global variable
# हम इसे Flask thread से अलग एक asyncio event loop में चलाएंगे
bot_async_loop = None
bot_async_task = None

# Health check route
@flask_app.route('/health') # app से बदलकर flask_app किया
def health_check():
    # Database connection check
    db_status = "OK"
    db_error = None
    try:
        if db_client:
            # Ping the database to check connection
            db_client.admin.command('ping')
        else:
            db_status = "FAIL"
            db_error = "MongoDB client not initialized."
    except Exception as e:
        db_status = "FAIL"
        db_error = str(e)
        logger.error(f"Health check: MongoDB connection failed: {e}") # config logger का उपयोग करें

    # Pyrogram client status (basic check if it's connected/running)
    bot_connection_status = "UNKNOWN"
    if bot_app.is_connected:
        bot_connection_status = "OK"
    else:
        bot_connection_status = "FAIL"
    
    # Check if the bot's asyncio task is running
    task_status = "UNKNOWN"
    if bot_async_task: # global bot_async_task का उपयोग करें
        if not bot_async_task.done() and not bot_async_task.cancelled():
            task_status = "OK"
        else:
            task_status = f"FAIL - Task {'Done' if bot_async_task.done() else 'Cancelled'}"
    else:
        task_status = "FAIL - Task Not Started"

    status = {
        "status": "UP",
        "timestamp": time.time(),
        "database_status": {
            "status": db_status,
            "error": db_error
        },
        "bot_client_status": bot_connection_status,
        "bot_async_task_status": task_status
    }
    
    # Agar koi bhi critical component fail ho, toh HTTP 500 status code return karein
    if db_status == "FAIL" or bot_connection_status == "FAIL" or task_status != "OK":
        return jsonify(status), 500
    
    return jsonify(status), 200

# Root route
@flask_app.route('/') # app से बदलकर flask_app किया
def home():
    return "Group Police Bot is running! Go to /health to check status."

# Flask app को एक अलग थ्रेड में चलाने के लिए फ़ंक्शन
def run_flask_app_thread():
    port = int(os.getenv("PORT", 8000)) # Koyeb PORT environment variable use karein
    logger.info(f"Flask app starting on port {port}")
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Pyrogram bot को main asyncio event loop में शुरू करें
async def run_pyrogram_bot_async():
    global bot_async_task # global variable को अपडेट करने के लिए
    logger.info("Starting Pyrogram bot in its own asyncio task...")
    # main() Pyrogram client को शुरू करेगा और उसे idle() पर रखेगा
    # यह तब तक चलता रहेगा जब तक इसे बाहरी रूप से रोका न जाए
    await bot_main_task() # bot.py से main() को कॉल करें
    logger.info("Pyrogram bot finished its execution.")


# Main execution block
if __name__ == '__main__':
    logger.info("Starting application (Flask and Pyrogram Bot)...")

    # Flask सर्वर को एक अलग थ्रेड में शुरू करें
    flask_thread = threading.Thread(target=run_flask_app_thread)
    flask_thread.daemon = True # Main program exit hone par flask thread bhi exit ho jayega
    flask_thread.start()
    logger.info("Flask server started in a separate thread.")

    # Pyrogram bot को main asyncio event loop में शुरू करें
    # यह सुनिश्चित करने के लिए कि Pyrogram सही ढंग से शुरू हो, हम एक नया asyncio loop बनाएंगे
    # और उसे चलाएंगे.
    try:
        bot_async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_async_loop) # इस थ्रेड के लिए लूप सेट करें

        bot_async_task = bot_async_loop.create_task(run_pyrogram_bot_async())
        
        logger.info("Pyrogram bot asyncio task created. Running event loop forever...")
        bot_async_loop.run_forever()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"Error running bot in main thread: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if bot_async_loop and bot_async_loop.is_running():
            logger.info("Stopping bot asyncio event loop.")
            bot_async_loop.stop()
            bot_async_loop.close()
        logger.info("Application exiting.")
