from flask import Flask, jsonify
import threading
import asyncio
import time
import os
import sys # sys module import karein

# bot.py से Pyrogram app और main async task को import करें
from bot import app as bot_app, main as bot_main_task
# database.py से MongoDB client को import करें
from database import client as db_client, logger as db_logger # database logger bhi import karein

# Flask app initialize karein
app = Flask(__name__)

# Pyrogram bot को चलाने के लिए एक global variable
# हम इसे सीधे main execution block में शुरू करेंगे
bot_loop = None
bot_task = None

# Health check route
@app.route('/health')
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
        db_logger.error(f"Health check: MongoDB connection failed: {e}") # Log database errors

    # Pyrogram client status (basic check if it's connected/running)
    bot_status = "UNKNOWN"
    if bot_app.is_connected:
        bot_status = "OK"
    else:
        bot_status = "FAIL"
    
    # Check if the bot's asyncio task is running
    # यह जांचने का अधिक सटीक तरीका है कि बॉट का async task चल रहा है या नहीं
    task_status = "UNKNOWN"
    if bot_task:
        if not bot_task.done() and not bot_task.cancelled():
            task_status = "OK"
        else:
            task_status = f"FAIL - Task {'Done' if bot_task.done() else 'Cancelled'}"
    else:
        task_status = "FAIL - Task Not Started"


    status = {
        "status": "UP",
        "timestamp": time.time(),
        "database_status": {
            "status": db_status,
            "error": db_error
        },
        "bot_client_status": bot_status,
        "bot_async_task_status": task_status
    }
    
    # Agar koi bhi critical component fail ho, toh HTTP 500 status code return karein
    if db_status == "FAIL" or bot_status == "FAIL" or task_status != "OK":
        return jsonify(status), 500
    
    return jsonify(status), 200

# Root route
@app.route('/')
def home():
    return "Group Police Bot is running! Go to /health to check status."

# Flask app को एक अलग थ्रेड में चलाने के लिए फ़ंक्शन
def run_flask():
    port = int(os.getenv("PORT", 8000)) # Koyeb PORT environment variable use karein
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Main execution block
if __name__ == '__main__':
    # Flask सर्वर को एक अलग थ्रेड में शुरू करें
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True # Main program exit hone par flask thread bhi exit ho jayega
    flask_thread.start()
    db_logger.info("Flask server started in a separate thread.")

    # Pyrogram bot को main asyncio event loop में शुरू करें
    # यह सुनिश्चित करने के लिए कि Pyrogram सही ढंग से शुरू हो, हम एक नया asyncio loop बनाएंगे
    # और उसे चलाएंगे.
    try:
        db_logger.info("Starting Pyrogram bot in main thread...")
        # Pyrogram को चलाने के लिए एक नया asyncio event loop बनाएं
        # यह सुनिश्चित करता है कि Pyrogram का अपना event loop है जो Flask के thread को ब्लॉक नहीं करता
        bot_loop = asyncio.get_event_loop()
        # bot_main_task एक async function है जो app.start() को कॉल करता है
        bot_task = bot_loop.create_task(bot_main_task())
        
        # event loop को तब तक चलाएं जब तक bot_task पूरा न हो जाए
        # या जब तक कोई बाहरी सिग्नल न मिले (जैसे Koyeb का shutdown)
        bot_loop.run_forever() 
        
    except KeyboardInterrupt:
        db_logger.info("Bot stopped by KeyboardInterrupt.")
    except Exception as e:
        db_logger.error(f"Error running bot: {e}")
        sys.exit(1) # Error hone par exit karein
    finally:
        if bot_loop and not bot_loop.is_running():
            db_logger.info("Closing bot event loop.")
            bot_loop.close()
        db_logger.info("Application exiting.")
