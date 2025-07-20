from flask import Flask, jsonify
import threading
import asyncio
import time
from bot import app as bot_app, main as bot_main_task # bot.py से app और main task import करें
from database import client as db_client # Database connection check ke liye
import os # To get PORT environment variable

# Flask app initialize karein
app = Flask(__name__)

# Bot ko run karne ke liye ek separate thread
bot_thread = None

@app.route('/')
def home():
    return "Group Police Bot is running! Go to /health to check status."

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

    # Pyrogram client status (basic check if it's connected/running)
    bot_status = "UNKNOWN"
    if bot_app.is_connected:
        bot_status = "OK"
    else:
        bot_status = "FAIL"
    
    # Check if the bot thread is alive
    thread_status = "UNKNOWN"
    if bot_thread and bot_thread.is_alive():
        thread_status = "OK"
    elif bot_thread and not bot_thread.is_alive():
        thread_status = "FAIL - Thread Dead"
    else:
        thread_status = "FAIL - Thread Not Started"


    status = {
        "status": "UP",
        "timestamp": time.time(),
        "database_status": {
            "status": db_status,
            "error": db_error
        },
        "bot_client_status": bot_status,
        "bot_thread_status": thread_status
    }
    
    # Agar koi bhi critical component fail ho, toh HTTP 500 status code return karein
    if db_status == "FAIL" or bot_status == "FAIL" or thread_status != "OK":
        return jsonify(status), 500
    
    return jsonify(status), 200

def run_bot():
    """Bot application ko asyncio event loop mein run karein."""
    asyncio.run(bot_main_task())

if __name__ == '__main__':
    # Bot ko ek separate thread mein start karein
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True # Main thread exit hone par bot thread bhi exit ho jayega
    bot_thread.start()

    # Flask app ko run karein
    # Production deployment ke liye Gunicorn ya uWSGI use karein
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
