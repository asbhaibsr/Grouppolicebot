# server.py

from flask import Flask, jsonify
import os
from config import FLASK_PORT, logger

app = Flask(__name__)

@app.route("/")
def health_check():
    """Koyeb हेल्थ चेक के लिए एक साधारण एंडपॉइंट।"""
    return jsonify({"status": "ok", "message": "Bot is running!"}), 200

def run_flask_server():
    """Flask सर्वर को चलाता है।"""
    # Flask को एक अलग पोर्ट पर चलाएं ताकि Pyrogram अपने वेबहुक को हैंडल कर सके।
    # Koyeb पर, आपको इस FLASK_PORT को भी एक्सपोज करना होगा।
    port = FLASK_PORT
    logger.info(f"Flask server running on port {port}")
    try:
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Error starting Flask server: {e}")

