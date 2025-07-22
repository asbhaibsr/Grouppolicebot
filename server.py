# server.py

import os
import asyncio
import re
import html
import time
import requests
import logging
import threading

from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ChatMemberUpdated, CallbackQuery
)
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from datetime import timedelta, datetime

# Assuming config and database are in the same directory or accessible
try:
    from config import (
        BOT_TOKEN, API_ID, API_HASH, CASE_LOG_CHANNEL_ID, NEW_USER_GROUP_LOG_CHANNEL_ID,
        OWNER_ID, UPDATE_CHANNEL_USERNAME, ASBHAI_USERNAME,
        WELCOME_MESSAGE_DEFAULT, BOT_PHOTO_URL, REPO_LINK,
        COMMAND_COOLDOWN_TIME, logger # Import logger from config
    )
except ImportError as e:
    print(f"Error importing from config.py: {e}")
    print("Please ensure config.py exists and contains all required variables.")
    exit(1) # यदि कॉन्फ़िग फ़ाइल लोड नहीं हो पाती है तो एग्जिट करें

try:
    from database import (
        add_or_update_user, get_user, add_or_update_group, get_group,
        update_group_settings, get_all_groups, delete_group,
        add_warn, get_warns, delete_warns,
        add_command_cooldown, get_command_cooldown, reset_command_cooldown
    )
except ImportError as e:
    print(f"Error importing from database.py: {e}")
    print("Please ensure database.py exists and contains all required functions.")
    exit(1)

try:
    from filters import (
        is_abusive, is_pornographic_text, contains_links, is_spam, has_bio_link, contains_usernames
    )
except ImportError as e:
    print(f"Error importing from filters.py: {e}")
    print("Please ensure filters.py exists and contains all required functions.")
    exit(1)

from flask import Flask, jsonify

# --- Flask Server for Health Checks (Koyeb specific) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify(
        status="running",
        bot_name=pyrogram_app.me.first_name if pyrogram_app.me else "N/A",
        bot_id=pyrogram_app.me.id if pyrogram_app.me else "N/A"
    )

def run_flask_app():
    # Use 0.0.0.0 for Koyeb deployment
    app.run(host='0.0.0.0', port=os.getenv("PORT", 8000), debug=False)

# Start Flask app in a separate thread
flask_thread = threading.Thread(target=run_flask_app)
flask_thread.daemon = True # Daemonize thread so it exits when main program exits
logger.info("Flask app starting on port 8000")
flask_thread.start()
logger.info("Flask server started in a separate thread.")

# Give Flask server a few seconds to warm up for health checks
time.sleep(5)
logger.info("Giving Flask server 5 seconds to warm up for health checks.")


# --- Pyrogram Client Initialization ---
pyrogram_app = Client(
    "GroupPoliceBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins") # This assumes you have a 'plugins' folder
)

# --- Helper Functions ---
async def is_user_admin_in_chat(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        logger.error(f"Error checking admin status for user {user_id} in chat {chat_id}: {e}")
        return False

async def is_bot_admin_in_chat(client: Client, chat_id: int) -> bool:
    try:
        bot_member = await client.get_chat_member(chat_id, client.me.id)
        return bot_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        logger.error(f"Error checking bot admin status in chat {chat_id}: {e}")
        return False

def check_cooldown(user_id: int, command_name: str) -> bool:
    last_use_time = get_command_cooldown(user_id, command_name)
    if last_use_time:
        elapsed_time = (datetime.now() - last_use_time).total_seconds()
        if elapsed_time < COMMAND_COOLDOWN_TIME:
            return False
    add_command_cooldown(user_id, command_name, datetime.now())
    logger.info(f"User {user_id} cooldown updated for command.")
    return True

# --- Custom Filters ---
# New function for the 'not edited' filter
def is_not_edited_message(_, m: Message):
    return not m.edit_date

# --- Message Handlers ---

@pyrogram_app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    logger.info(f"[{message.chat.id}] Received /start command from user {message.from_user.id} ({message.from_user.first_name}).")
    if not check_cooldown(message.from_user.id, "command"):
        return

    user = message.from_user
    add_or_update_user(user.id, user.username, user.first_name, user.last_name, user.is_bot)
    logger.info(f"User {user.id} data added/updated on /start.")
    
    keyboard = [
        [InlineKeyboardButton("➕ ग्रुप में ऐड करें", url=f"https://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("❓ सहायता", callback_data="help_menu")],
        [InlineKeyboardButton("📢 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")],
        [InlineKeyboardButton("🔗 सोर्स कोड", url=REPO_LINK)],
        [InlineKeyboardButton("📞 मुझसे संपर्क करें", url=f"https://t.me/{ASBHAI_USERNAME}")]
    ]

    is_connected_group_admin = False
    all_current_groups = get_all_groups()
    for group_data in all_current_groups:
        try:
            bot_member = await client.get_chat_member(group_data["_id"], client.me.id) # Use _id from database
            if bot_member.status != ChatMemberStatus.LEFT:
                if await is_user_admin_in_chat(client, group_data["_id"], user.id):
                    is_connected_group_admin = True
                    break
        except Exception as e:
            logger.warning(f"Error checking admin status for group {group_data.get('title', group_data['_id'])}: {e}")

    if is_connected_group_admin:
        keyboard.append([InlineKeyboardButton("⚙️ सेटिंग्स", callback_data="settings_menu")])
        logger.info(f"Settings button added for user {user.id}.")

    reply_markup = InlineKeyboardMarkup(keyboard)

    start_message_text = (
        f"👋 नमस्ते {user.first_name}! मैं आपका ग्रुप पुलिस बॉट हूँ, {client.me.first_name}.\n\n"
        "मैं ग्रुप चैट को मॉडरेट करने, स्पैम, अनुचित सामग्री और अवांछित लिंक को फ़िल्टर करने में मदद करता हूँ।\n"
        "आपकी मदद कैसे कर सकता हूँ?"
    )

    try:
        await message.reply_photo(
            photo=BOT_PHOTO_URL,
            caption=start_message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Start message with photo sent to user {user.id}.")
    except Exception as e:
        logger.error(f"Error sending start message with photo to user {user.id}: {e}. Sending text only.", exc_info=True)
        await message.reply_text(
            start_message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Start message (text only) sent to user {user.id}.")


@pyrogram_app.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    logger.info(f"[{message.chat.id}] Received /help command from user {message.from_user.id}.")
    if not check_cooldown(message.from_user.id, "command"):
        return

    help_text = (
        "🤖 **बॉट कमांड्स:**\n\n"
        "**प्राइवेट में:**\n"
        "  • `/start` - बॉट शुरू करें और मुख्य मेनू देखें।\n"
        "  • `/help` - यह सहायता मैसेज देखें।\n"
        "  • `/settings` - अपने ग्रुप्स की सेटिंग्स प्रबंधित करें। (केवल उन ग्रुप्स के लिए जहाँ आप एडमिन हैं और बॉट है)\n"
        "  • `/connectgroup <group_id>` - एक ग्रुप को मैन्युअल रूप से कनेक्ट करें।\n\n"
        "**ग्रुप में:**\n"
        "  • `/ban <reply_to_user>` - यूज़र को ग्रुप से बैन करें।\n"
        "  • `/unban <reply_to_user>` - यूज़र को ग्रुप से अनबैन करें।\n"
        "  • `/kick <reply_to_user>` - यूज़र को ग्रुप से किक करें।\n"
        "  • `/mute <reply_to_user>` - यूज़र को ग्रुप में मैसेज भेजने से म्यूट करें।\n"
        "  • `/unmute <reply_to_user>` - यूज़र को ग्रुप में मैसेज भेजने से अनम्यूट करें।\n"
        "  • `/warn <reply_to_user>` - यूज़र को चेतावनी दें। 3 चेतावनियों के बाद बैन।\n"
        "  • `/warnings <reply_to_user>` - यूज़र की चेतावनियाँ देखें।\n"
        "  • `/resetwarns <reply_to_user>` - यूज़र की चेतावनियाँ रीसेट करें।\n"
        "  • `/info <reply_to_user>` - यूज़र की जानकारी देखें।\n"
        "  • `/setwelcome [message]` - ग्रुप के लिए कस्टम वेलकम मैसेज सेट करें। (`{username}`, `{groupname}` का उपयोग करें)\n"
        "  • `/welcomesettings` - वेलकम मैसेज सेटिंग्स प्रबंधित करें।\n"
        "  • `/clean [count]` - पिछली 'count' संख्या में मैसेज डिलीट करें।\n"
        "  • `/settings` - ग्रुप की सेटिंग्स प्रबंधित करें।\n\n"
        "**⚙️ सेटिंग्स को एक्सेस करने के लिए, आपको ग्रुप में एडमिन होना चाहिए और बॉट भी ग्रुप में एडमिन होना चाहिए।**"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


@pyrogram_app.on_callback_query()
async def callback_query_handler(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.id

    logger.info(f"[{chat_id}] Callback query received: {data} from user {user_id}.")

    if data == "help_menu":
        help_text = (
            "🤖 **बॉट कमांड्स:**\n\n"
            "**प्राइवेट में:**\n"
            "  • `/start` - बॉट शुरू करें और मुख्य मेनू देखें।\n"
            "  • `/help` - यह सहायता मैसेज देखें।\n"
            "  • `/settings` - अपने ग्रुप्स की सेटिंग्स प्रबंधित करें। (केवल उन ग्रुप्स के लिए जहाँ आप एडमिन हैं और बॉट है)\n"
            "  • `/connectgroup <group_id>` - एक ग्रुप को मैन्युअल रूप से कनेक्ट करें।\n\n"
            "**ग्रुप में:**\n"
            "  • `/ban <reply_to_user>` - यूज़र को ग्रुप से बैन करें।\n"
            "  • `/unban <reply_to_user>` - यूज़र को ग्रुप से अनबैन करें।\n"
            "  • `/kick <reply_to_user>` - यूज़र को ग्रुप से किक करें।\n"
            "  • `/mute <reply_to_user>` - यूज़र को ग्रुप में मैसेज भेजने से म्यूट करें।\n"
            "  • `/unmute <reply_to_user>` - यूज़र को ग्रुप में मैसेज भेजने से अनम्यूट करें।\n"
            "  • `/warn <reply_to_user>` - यूज़र को चेतावनी दें। 3 चेतावनियों के बाद बैन।\n"
            "  • `/warnings <reply_to_user>` - यूज़र की चेतावनियाँ देखें।\n"
            "  • `/resetwarns <reply_to_user>` - यूज़र की चेतावनियाँ रीसेट करें।\n"
            "  • `/info <reply_to_user>` - यूज़र की जानकारी देखें।\n"
            "  • `/setwelcome [message]` - ग्रुप के लिए कस्टम वेलकम मैसेज सेट करें। (`{username}`, `{groupname}` का उपयोग करें)\n"
            "  • `/welcomesettings` - वेलकम मैसेज सेटिंग्स प्रबंधित करें।\n"
            "  • `/clean [count]` - पिछली 'count' संख्या में मैसेज डिलीट करें।\n"
            "  • `/settings` - ग्रुप की सेटिंग्स प्रबंधित करें।\n\n"
            "**⚙️ सेटिंग्स को एक्सेस करने के लिए, आपको ग्रुप में एडमिन होना चाहिए और बॉट भी ग्रुप में एडमिन होना चाहिए।**"
        )
        keyboard = [[InlineKeyboardButton("🔙 वापस", callback_data="start_menu")]]
        await callback_query.message.edit_caption(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        await callback_query.answer()

    elif data == "start_menu":
        user = callback_query.from_user
        keyboard = [
            [InlineKeyboardButton("➕ ग्रुप में ऐड करें", url=f"https://t.me/{client.me.username}?startgroup=true")],
            [InlineKeyboardButton("❓ सहायता", callback_data="help_menu")],
            [InlineKeyboardButton("📢 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")],
            [InlineKeyboardButton("🔗 सोर्स कोड", url=REPO_LINK)],
            [InlineKeyboardButton("📞 मुझसे संपर्क करें", url=f"https://t.me/{ASBHAI_USERNAME}")]
        ]

        is_connected_group_admin = False
        all_current_groups = get_all_groups()
        for group_data in all_current_groups:
            try:
                bot_member = await client.get_chat_member(group_data["_id"], client.me.id)
                if bot_member.status != ChatMemberStatus.LEFT:
                    if await is_user_admin_in_chat(client, group_data["_id"], user_id):
                        is_connected_group_admin = True
                        break
            except Exception as e:
                logger.warning(f"Error checking admin status for group {group_data.get('title', group_data['_id'])} during start menu for user {user_id}: {e}")

        if is_connected_group_admin:
            keyboard.append([InlineKeyboardButton("⚙️ सेटिंग्स", callback_data="settings_menu")])
            logger.info(f"Settings button added for user {user_id} via callback.")

        reply_markup = InlineKeyboardMarkup(keyboard)

        start_message_text = (
            f"👋 नमस्ते {user.first_name}! मैं आपका ग्रुप पुलिस बॉट हूँ, {client.me.first_name}.\n\n"
            "मैं ग्रुप चैट को मॉडरेट करने, स्पैम, अनुचित सामग्री और अवांछित लिंक को फ़िल्टर करने में मदद करता हूँ।\n"
            "आपकी मदद कैसे कर सकता हूँ?"
        )
        await callback_query.message.edit_caption(start_message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await callback_query.answer()

    elif data == "settings_menu":
        if chat_id < 0: # If accessed from a group
            group_id = chat_id
            if not await is_user_admin_in_chat(client, group_id, user_id):
                await callback_query.answer("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए!", show_alert=True)
                return
            if not await is_bot_admin_in_chat(client, group_id):
                await callback_query.answer("मैं इस ग्रुप में एडमिन नहीं हूँ। कृपया मुझे एडमिन अनुमति दें।", show_alert=True)
                return
            await show_group_settings(client, callback_query.message, group_id)
        else: # If accessed from private chat
            await show_private_settings_menu(client, callback_query.message, user_id)
        await callback_query.answer()

    elif data.startswith("select_group_"):
        group_id = int(data.split("_")[2])
        if not await is_user_admin_in_chat(client, group_id, user_id):
            await callback_query.answer("आपको इस ग्रुप में एडमिन होना चाहिए।", show_alert=True)
            return
        if not await is_bot_admin_in_chat(client, group_id):
            await callback_query.answer("मैं इस ग्रुप में एडमिन नहीं हूँ। कृपया मुझे एडमिन अनुमति दें।", show_alert=True)
            return
        await show_group_settings(client, callback_query.message, group_id)
        await callback_query.answer()

    elif data.startswith("toggle_"):
        parts = data.split("_")
        setting_name = "_".join(parts[1:-1]) # Handles names like 'anti_link_enabled'
        group_id = int(parts[-1])

        if not await is_user_admin_in_chat(client, group_id, user_id):
            await callback_query.answer("आपको यह सेटिंग बदलने के लिए एडमिन होना चाहिए!", show_alert=True)
            return
        if not await is_bot_admin_in_chat(client, group_id):
            await callback_query.answer("मैं इस ग्रुप में एडमिन नहीं हूँ। कृपया मुझे एडमिन अनुमति दें।", show_alert=True)
            return

        group_data = get_group(group_id)
        if group_data:
            current_value = group_data.get(setting_name, False)
            new_value = not current_value
            update_group_settings(group_id, {setting_name: new_value})
            logger.info(f"Group {group_id}: Setting '{setting_name}' toggled to {new_value} by user {user_id}.")
            await show_group_settings(client, callback_query.message, group_id)
        else:
            await callback_query.answer("ग्रुप की सेटिंग्स नहीं मिलीं।", show_alert=True)
        await callback_query.answer()

    elif data.startswith("welcome_"):
        parts = data.split("_")
        action = parts[1]
        group_id = int(parts[2])

        if not await is_user_admin_in_chat(client, group_id, user_id):
            await callback_query.answer("आपको यह सेटिंग बदलने के लिए एडमिन होना चाहिए!", show_alert=True)
            return
        if not await is_bot_admin_in_chat(client, group_id):
            await callback_query.answer("मैं इस ग्रुप में एडमिन नहीं हूँ। कृपया मुझे एडमिन अनुमति दें।", show_alert=True)
            return
        
        group_data = get_group(group_id)
        if not group_data:
            await callback_query.answer("ग्रुप की सेटिंग्स नहीं मिलीं।", show_alert=True)
            return

        if action == "toggle":
            current_value = group_data.get("welcome_enabled", False)
            new_value = not current_value
            update_group_settings(group_id, {"welcome_enabled": new_value})
            logger.info(f"Group {group_id}: Welcome enabled toggled to {new_value} by user {user_id}.")
            await show_group_settings(client, callback_query.message, group_id)
        elif action == "set_custom":
            await callback_query.message.edit_text("कृपया नया वेलकम मैसेज भेजें। आप `{username}` और `{groupname}` का उपयोग कर सकते हैं।",
                                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस", callback_data=f"back_to_settings_{group_id}")]])
                                                 )
            # Set a temporary state for the user to wait for the next message
            client.waiting_for_welcome_message = user_id 
            client.waiting_for_welcome_group = group_id
        elif action == "reset_default":
            update_group_settings(group_id, {"welcome_message": WELCOME_MESSAGE_DEFAULT})
            logger.info(f"Group {group_id}: Welcome message reset to default by user {user_id}.")
            await show_group_settings(client, callback_query.message, group_id)
        
        await callback_query.answer()

    elif data.startswith("back_to_settings_"):
        group_id = int(data.split("_")[3])
        if not await is_user_admin_in_chat(client, group_id, user_id):
            await callback_query.answer("आपको इस ग्रुप में एडमिन होना चाहिए।", show_alert=True)
            return
        if not await is_bot_admin_in_chat(client, group_id):
            await callback_query.answer("मैं इस ग्रुप में एडमिन नहीं हूँ। कृपया मुझे एडमिन अनुमति दें।", show_alert=True)
            return
        await show_group_settings(client, callback_query.message, group_id)
        await callback_query.answer()

    elif data.startswith("take_action_"):
        user_id_to_act = int(parts[2])
        group_id = int(parts[3])
        logger.info(f"User {callback_query.from_user.id} attempting to take action on user {user_id_to_act} in group {group_id}.")
        if not await is_user_admin_in_chat(client, group_id, callback_query.from_user.id):
            await callback_query.answer("आपको इस यूज़र पर कार्रवाई करने की अनुमति नहीं है।", show_alert=True)
            return
            
        action_keyboard = [
            [InlineKeyboardButton("🔇 म्यूट करें (1 घंटा)", callback_data=f"mute_user_{user_id_to_act}_{group_id}_3600")],
            [InlineKeyboardButton("👢 किक करें", callback_data=f"kick_user_{user_id_to_act}_{group_id}")],
            [InlineKeyboardButton("🚫 बैन करें", callback_data=f"ban_user_{user_id_to_act}_{group_id}")],
            [InlineKeyboardButton("⚠️ चेतावनी दें", callback_data=f"warn_user_{user_id_to_act}_{group_id}")],
            [InlineKeyboardButton("❌ रद्द करें", callback_data=f"cancel_action_{user_id_to_act}_{group_id}")]
        ]
        await callback_query.message.edit_text(
            f"[{user_id_to_act}](tg://user?id={user_id_to_act}) पर क्या कार्रवाई करनी है?",
            reply_markup=InlineKeyboardMarkup(action_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Action menu sent for user {user_id_to_act} in group {group_id}.")

    elif data.startswith("manage_permission_"):
        user_id_to_manage = int(parts[2])
        group_id = int(parts[3]) # Assuming group_id is always passed for admin check
        logger.info(f"User {callback_query.from_user.id} attempting to manage bio link permission for user {user_id_to_manage} in group {group_id}.")
        if not await is_user_admin_in_chat(client, group_id, callback_query.from_user.id):
            await callback_query.answer("आपको इस यूज़र की अनुमति प्रबंधित करने की अनुमति नहीं है।", show_alert=True)
            return

        # get_user_biolink_exception is not in database.py. Assuming it's a user setting.
        # For now, let's assume it's part of user_data or a separate collection.
        # If it's not in database.py, you'll need to add it.
        # For demonstration, I'll use a placeholder for get_user_biolink_exception.
        # You need to implement get_user_biolink_exception and set_user_biolink_exception in database.py
        # or remove this feature if not needed.
        # current_permission = get_user_biolink_exception(user_id_to_manage) # This function is missing
        current_permission = False # Placeholder
        permission_status_text = "अनुमति मिली है" if current_permission else "अनुमति नहीं मिली है"
        logger.info(f"Current bio link permission for user {user_id_to_manage}: {permission_status_text}")

        permission_keyboard = [
            [InlineKeyboardButton("✅ अनुमति दें", callback_data=f"set_bio_permission_{user_id_to_manage}_true")],
            [InlineKeyboardButton("❌ अनुमति न दें", callback_data=f"set_bio_permission_{user_id_to_manage}_false")]
        ]
        await callback_query.message.edit_text(
            f"[{user_id_to_manage}](tg://user?id={user_id_to_manage}) को बायो लिंक की अनुमति वर्तमान में: **{permission_status_text}**\n\n"
            f"अनुमति दें या नहीं दें?",
            reply_markup=InlineKeyboardMarkup(permission_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Bio link permission menu sent for user {user_id_to_manage}.")

    elif data.startswith("set_bio_permission_"):
        user_id = int(parts[2])
        permission_status = parts[3] == 'true'
        # set_user_biolink_exception(user_id, permission_status) # This function is missing
        await callback_query.message.edit_text(f"[{user_id}](tg://user?id={user_id}) को बायो लिंक की अनुमति {'मिल गई है' if permission_status else 'नहीं मिली है'}।", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"Bio link permission for user {user_id} set to {permission_status}.")


    elif data.startswith("mute_user_") or data.startswith("kick_user_") or data.startswith("ban_user_") or data.startswith("warn_user_"):
        action_type = parts[0]
        user_id_target = int(parts[1])
        group_id = int(parts[2])
        duration = int(parts[3]) if len(parts) > 3 else None # For mute action

        if not await is_user_admin_in_chat(client, group_id, user_id):
            await callback_query.answer("आपको यह कार्रवाई करने की अनुमति नहीं है।", show_alert=True)
            return
        if not await is_bot_admin_in_chat(client, group_id):
            await callback_query.answer("मैं इस ग्रुप में एडमिन नहीं हूँ। कृपया मुझे एडमिन अनुमति दें।", show_alert=True)
            return

        try:
            target_user_info = await client.get_users(user_id_target)
            
            if action_type == "mute_user":
                await client.restrict_chat_member(
                    chat_id=group_id,
                    user_id=user_id_target,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=datetime.now() + timedelta(seconds=duration)
                )
                await callback_query.message.edit_text(f"✅ {target_user_info.mention} को {duration/60} मिनट के लिए म्यूट कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
                logger.info(f"User {user_id_target} muted for {duration/60} mins in group {group_id}.")
            elif action_type == "kick_user":
                await client.ban_chat_member(chat_id=group_id, user_id=user_id_target)
                await client.unban_chat_member(chat_id=group_id, user_id=user_id_target)
                await callback_query.message.edit_text(f"✅ {target_user_info.mention} को ग्रुप से किक कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
                logger.info(f"User {user_id_target} kicked from group {group_id}.")
            elif action_type == "ban_user":
                await client.ban_chat_member(chat_id=group_id, user_id=user_id_target)
                await callback_query.message.edit_text(f"✅ {target_user_info.mention} को ग्रुप से बैन कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
                logger.info(f"User {user_id_target} banned from group {group_id}.")
            elif action_type == "warn_user":
                current_warns = add_warn(group_id, user_id_target)
                group_data = get_group(group_id)
                warn_limit = group_data.get("warn_limit", 3)
                warn_message = f"⚠️ {target_user_info.mention} को {current_warns}/{warn_limit} चेतावनी मिली है।"
                if current_warns >= warn_limit:
                    await client.ban_chat_member(group_id, user_id_target)
                    warn_message += f"\n{target_user_info.mention} को {warn_limit} चेतावनियों के बाद ग्रुप से बैन कर दिया गया है।"
                    delete_warns(group_id, user_id_target)
                await callback_query.message.edit_text(warn_message, parse_mode=ParseMode.MARKDOWN)
                logger.info(f"User {user_id_target} warned in group {group_id}. Total warns: {current_warns}.")

            # Log to case log channel
            if CASE_LOG_CHANNEL_ID:
                await client.send_message(
                    CASE_LOG_CHANNEL_ID,
                    f"🚨 **कार्रवाई:** `{action_type.replace('_user', '').capitalize()}`\n"
                    f"ग्रुप: `{callback_query.message.chat.title}` (ID: `{group_id}`)\n"
                    f"यूज़र: [{target_user_info.first_name}](tg://user?id={user_id_target}) (ID: `{user_id_target}`)\n"
                    f"एडमिन: [{callback_query.from_user.first_name}](tg://user?id={user_id}) (ID: `{user_id}`)"
                )
        except Exception as e:
            logger.error(f"Error performing action {action_type} for user {user_id_target} in group {group_id}: {e}", exc_info=True)
            await callback_query.message.edit_text(f"कार्रवाई करने में त्रुटि आई: `{e}`")

    elif data.startswith("cancel_action_"):
        user_id_target = int(parts[2])
        group_id = int(parts[3])
        await callback_query.message.edit_text(f"[{user_id_target}](tg://user?id={user_id_target}) पर कार्रवाई रद्द कर दी गई।", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"Action cancelled for user {user_id_target} in group {group_id} by {user_id}.")

    elif data == "close_settings":
        await callback_query.message.edit_text("सेटिंग्स बंद कर दी गईं।")
        logger.info(f"Settings closed by user {user_id}.")


async def show_group_settings(client: Client, message: Message, group_id: int):
    group_data = get_group(group_id)
    if not group_data:
        await message.edit_text("इस ग्रुप की सेटिंग्स नहीं मिलीं। शायद यह बॉट से कनेक्टेड नहीं है।")
        return

    group_title = group_data.get("title", f"Group ID: {group_id}")

    # Default values if settings not explicitly found
    welcome_enabled = group_data.get("welcome_enabled", False)
    welcome_message = group_data.get("welcome_message", WELCOME_MESSAGE_DEFAULT)
    anti_link_enabled = group_data.get("anti_link_enabled", False)
    anti_flood_enabled = group_data.get("anti_flood_enabled", False)
    
    settings_text = (
        f"⚙️ **{group_title}** सेटिंग्स:\n\n"
        f"➡️ वेलकम मैसेज: {'✅ चालू' if welcome_enabled else '❌ बंद'}\n"
        f"➡️ एंटी-लिंक: {'✅ चालू' if anti_link_enabled else '❌ बंद'}\n"
        f"➡️ एंटी-फ्लड: {'✅ चालू' if anti_flood_enabled else '❌ बंद'}\n"
        f"\n**वर्तमान वेलकम मैसेज:**\n`{html.escape(welcome_message)}`"
    )

    keyboard = [
        [
            InlineKeyboardButton(f"वेलकम मैसेज: {'❌ बंद' if welcome_enabled else '✅ चालू'}", callback_data=f"welcome_toggle_{group_id}"),
            InlineKeyboardButton("वेलकम सेटिंग्स", callback_data=f"welcome_set_custom_{group_id}") # Changed to set_custom directly
        ],
        [InlineKeyboardButton(f"एंटी-लिंक: {'❌ बंद' if anti_link_enabled else '✅ चालू'}", callback_data=f"toggle_anti_link_enabled_{group_id}")],
        [InlineKeyboardButton(f"एंटी-फ्लड: {'❌ बंद' if anti_flood_enabled else '✅ चालू'}", callback_data=f"toggle_anti_flood_enabled_{group_id}")],
        [InlineKeyboardButton("🔙 सभी ग्रुप्स पर वापस", callback_data="settings_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.edit_caption(settings_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


async def show_private_settings_menu(client: Client, message: Message, user_id: int):
    user_admin_groups = []
    all_known_groups = get_all_groups()

    for group_data in all_known_groups:
        try:
            bot_member = await client.get_chat_member(group_data["_id"], client.me.id)
            if bot_member.status != ChatMemberStatus.LEFT:
                if await is_user_admin_in_chat(client, group_data["_id"], user_id):
                    user_admin_groups.append(group_data)
        except Exception as e:
            logger.warning(f"Could not verify bot/user admin status for group {group_data.get('title', group_data['_id'])}: {e}")

    if not user_admin_groups:
        await message.edit_text(
            "आप किसी भी ऐसे ग्रुप में एडमिन नहीं हैं जहाँ मैं मौजूद हूँ। "
            "कृपया मुझे अपने ग्रुप में एडमिन के रूप में ऐड करें।"
        )
        return

    keyboard = []
    for group in user_admin_groups:
        keyboard.append([InlineKeyboardButton(group["title"], callback_data=f"select_group_{group['_id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 वापस", callback_data="start_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.edit_text("कृपया उस ग्रुप का चयन करें जिसकी आप सेटिंग्स प्रबंधित करना चाहते हैं:", reply_markup=reply_markup)


@pyrogram_app.on_message(filters.command("connectgroup") & filters.private)
async def connect_group_command(client: Client, message: Message):
    logger.info(f"[{message.chat.id}] Received /connectgroup command from user {message.from_user.id} ({message.from_user.first_name}).")
    if not check_cooldown(message.from_user.id, "command"):
        return

    if not message.text or len(message.command) < 2:
        await message.reply_text("कृपया ग्रुप ID प्रदान करें। उदाहरण: `/connectgroup -1001234567890`\n"
                                 "**नोट:** ग्रुप ID आमतौर पर `-100` से शुरू होती है।")
        logger.warning(f"User {message.from_user.id} did not provide group ID for /connectgroup.")
        return

    try:
        group_id = int(message.command[1])
        if group_id >= 0: # Telegram group IDs are usually negative
            raise ValueError("Group ID must be a negative integer (e.g., -100...).")
        logger.info(f"Attempting to connect group with ID: {group_id}")
    except ValueError as ve:
        await message.reply_text(f"अमान्य ग्रुप ID। कृपया एक संख्यात्मक ID प्रदान करें, जो `-100` से शुरू हो सकती है। एरर: `{ve}`")
        logger.warning(f"Invalid group ID provided by user {message.from_user.id}: '{message.command[1]}'. Error: {ve}")
        return

    chat_info = None
    try:
        chat_info = await client.get_chat(group_id)
        if chat_info.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.reply_text("प्रदान की गई ID एक वैध ग्रुप ID नहीं है।")
            logger.warning(f"Provided ID {group_id} is not a group/supergroup for user {message.from_user.id}.")
            return
        logger.info(f"Found chat info for group {group_id}: {chat_info.title}")
    except Exception as e:
        error_message = str(e)
        reply_msg = f"ग्रुप ढूंढने में असमर्थ। सुनिश्चित करें कि बॉट उस ग्रुप का सदस्य है और ID सही है।"
        if "Peer id invalid" in error_message or "chat not found" in error_message.lower():
            reply_msg += "\n\n**संभव कारण:** बॉट इस ग्रुप का सदस्य नहीं है या आपने गलत ग्रुप ID दी है। बॉट को पहले ग्रुप में जोड़ें।"
        
        await message.reply_text(f"{reply_msg} एरर: `{e}`")
        logger.error(f"Failed to get chat info for group {group_id} for user {message.from_user.id}: {e}", exc_info=True)
        return

    try:
        bot_member = await client.get_chat_member(group_id, client.me.id)
        if bot_member.status == ChatMemberStatus.LEFT:
            await message.reply_text("बॉट इस ग्रुप का सदस्य नहीं है। कृपया पहले बॉट को ग्रुप में जोड़ें।")
            logger.warning(f"Bot is not a member of group {group_id} for user {message.from_user.id}.")
            return
    except Exception as e:
        await message.reply_text(f"बॉट की ग्रुप सदस्यता जांचने में असमर्थ: `{e}`")
        logger.error(f"Error checking bot's membership in group {group_id}: {e}", exc_info=True)
        return

    if not await is_user_admin_in_chat(client, group_id, message.from_user.id):
        await message.reply_text("आप इस ग्रुप के एडमिन नहीं हैं, इसलिए इसे कनेक्ट नहीं कर सकते।")
        logger.warning(f"User {message.from_user.id} tried to connect group {group_id} but is not an admin.")
        return

    add_or_update_group(group_id, chat_info.title, message.from_user.id)
    await message.reply_text(f"ग्रुप '{chat_info.title}' सफलतापूर्वक कनेक्ट हो गया है! अब आप यहाँ से सेटिंग्स प्रबंधित कर सकते हैं।")
    logger.info(f"Group '{chat_info.title}' ({group_id}) connected by user {message.from_user.id}.")

    # Log to new user/group log channel
    if NEW_USER_GROUP_LOG_CHANNEL_ID:
        try:
            await client.send_message(
                NEW_USER_GROUP_LOG_CHANNEL_ID,
                f"➕ **नया ग्रुप मैन्युअल रूप से जोड़ा गया:**\n"
                f"नाम: `{chat_info.title}`\n"
                f"ID: `{group_id}`\n"
                f"जोड़ने वाला: {message.from_user.mention} (ID: `{message.from_user.id}`)"
            )
        except Exception as e:
            logger.error(f"Error logging manual group add to channel: {e}")


@pyrogram_app.on_message(filters.command("settings") & filters.private)
async def settings_menu_command(client: Client, message: Message):
    logger.info(f"[{message.chat.id}] Received /settings command from user {message.from_user.id} ({message.from_user.first_name}).")
    if not check_cooldown(message.from_user.id, "command"):
        return

    user_id = message.from_user.id
    await show_private_settings_menu(client, message, user_id)


# Custom filter for awaiting input
def awaiting_welcome_message_input_filter(_, message: Message):
    return hasattr(pyrogram_app, 'waiting_for_welcome_message') and \
           pyrogram_app.waiting_for_welcome_message == message.from_user.id and \
           not message.text.startswith('/') and not message.text.startswith('!')

@pyrogram_app.on_message(filters.private & filters.create(awaiting_welcome_message_input_filter))
async def handle_welcome_message_input(client: Client, message: Message):
    logger.info(f"Received potential welcome message input from user {message.from_user.id}. Message: '{message.text}'")

    if message.text == "/cancel":
        if hasattr(pyrogram_app, 'waiting_for_welcome_message') and pyrogram_app.waiting_for_welcome_message == message.from_user.id:
            del pyrogram_app.waiting_for_welcome_message
            if hasattr(pyrogram_app, 'waiting_for_welcome_group'):
                del pyrogram_app.waiting_for_welcome_group
            await message.reply_text("वेलकम मैसेज सेट करना रद्द कर दिया गया है।")
            logger.info(f"Welcome message input cancelled by user {message.from_user.id}.")
        return

    if hasattr(pyrogram_app, 'waiting_for_welcome_message') and pyrogram_app.waiting_for_welcome_message == message.from_user.id:
        group_id = pyrogram_app.waiting_for_welcome_group
        
        if not await is_user_admin_in_chat(client, group_id, message.from_user.id):
            await message.reply_text("आपको इस ग्रुप का वेलकम मैसेज सेट करने की अनुमति नहीं है।")
            logger.warning(f"Unauthorized user {message.from_user.id} tried to set welcome message for group {group_id}.")
            return

        new_welcome_message = message.text
        update_group_settings(group_id, {"welcome_message": new_welcome_message})
        logger.info(f"Welcome message updated for group {group_id} by user {message.from_user.id}.")
        
        await message.reply_text(
            f"✅ वेलकम मैसेज सफलतापूर्वक अपडेट किया गया है।\nनया मैसेज: `{html.escape(new_welcome_message)}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस सेटिंग्स", callback_data=f"select_group_{group_id}")]])
        )
        del pyrogram_app.waiting_for_welcome_message
        del pyrogram_app.waiting_for_welcome_group
    else:
        logger.warning(f"User {message.from_user.id} sent message while not in awaiting input state for welcome message. Ignoring.")


# --- मुख्य मैसेज हैंडलर (ग्रुप में) ---
@pyrogram_app.on_message(filters.text & filters.group & filters.create(is_not_edited_message) & ~filters.via_bot)
async def handle_group_messages(client: Client, message: Message):
    group_id = message.chat.id
    group_data = get_group(group_id)

    if not group_data:
        add_or_update_group(group_id, message.chat.title, OWNER_ID) # Owner_ID as placeholder
        group_data = get_group(group_id) # Fetch newly added data
        logger.info(f"Group {message.chat.title} ({group_id}) auto-added to database on first message.")

    if not group_data.get('bot_enabled', True):
        logger.info(f"[{group_id}] Bot is disabled for this group. Ignoring message from {message.from_user.id}.")
        return

    if message.from_user.is_bot and message.from_user.id != client.me.id:
        logger.info(f"[{group_id}] Ignoring message from other bot {message.from_user.id}.")
        return
    
    if message.from_user.id == client.me.id:
        logger.debug(f"[{group_id}] Ignoring message from self bot {message.from_user.id}.")
        return

    add_or_update_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name, message.from_user.is_bot)
    logger.info(f"[{group_id}] User {message.from_user.id} data updated in DB.")

    violation_detected = False
    violation_type = None
    original_content = message.text
    case_name = None

    if group_data.get('filter_abusive', False) and is_abusive(message.text):
        violation_detected = True
        violation_type = "गाली-गलौज"
        case_name = "आपत्तिजनक भाषा का प्रयोग"
    elif group_data.get('filter_pornographic_text', False) and is_pornographic_text(message.text):
        violation_detected = True
        violation_type = "पॉर्नोग्राफिक टेक्स्ट"
        case_name = "पॉर्नोग्राफिक सामग्री"
    elif group_data.get('filter_spam', False) and is_spam(message.text):
        violation_detected = True
        violation_type = "स्पैम"
        case_name = "संदिग्ध स्पैम"
    elif group_data.get('anti_link_enabled', False) and contains_links(message.text):
        violation_detected = True
        violation_type = "लिंक"
        case_name = "अनधिकृत लिंक"
    elif group_data.get('filter_bio_links', False):
        # This filter needs to be async and call database.py functions
        # For now, assuming has_bio_link is in filters.py and uses database.py
        # If get_user_biolink_exception is needed, it must be in database.py
        # For now, I'm removing the biolink exception check as it's not fully implemented in database.py
        # You'll need to add get_user_biolink_exception and set_user_biolink_exception to database.py
        # if you want to use this feature with exceptions.
        if await has_bio_link(client, message.from_user.id):
            # Assuming no exception system for now, or it's handled inside has_bio_link
            violation_detected = True
            violation_type = "बायो_लिंक_उल्लंघन"
            case_name = "बायो में अनधिकृत लिंक"

    elif group_data.get('usernamedel_enabled', False) and contains_usernames(message.text):
        bot_username = client.me.username
        if bot_username and f"@{bot_username.lower()}" in message.text.lower():
            logger.debug(f"[{group_id}] Ignoring bot's own username mention in message from {message.from_user.id}.")
            pass
        else:
            violation_detected = True
            violation_type = "यूज़रनेम"
            case_name = "यूज़रनेम प्रचार"

    if violation_detected:
        logger.info(f"[{group_id}] Violation '{violation_type}' detected from user {message.from_user.id}. Attempting to delete message.")
        try:
            bot_member_in_chat = await client.get_chat_member(group_id, client.me.id)
            if not bot_member_in_chat.can_delete_messages:
                logger.warning(f"[{group_id}] Bot does not have 'can_delete_messages' permission. Cannot delete message.")
                await client.send_message(group_id, "⚠️ **चेतावनी:** मुझे संदेश हटाने की अनुमति नहीं है। कृपया मुझे 'संदेश हटाएँ' (Delete Messages) की अनुमति दें।")
                return

            await message.delete()
            logger.info(f"[{group_id}] Message from {message.from_user.id} deleted successfully.")

            log_data = {
                'username': message.from_user.username or message.from_user.first_name,
                'user_id': message.from_user.id,
                'group_name': message.chat.title,
                'group_id': group_id,
                'violation_type': violation_type,
                'original_content': original_content,
                'case_name': case_name
            }
            # add_violation is not in database.py, assuming it's a separate logging function
            # For now, I'll log to the CASE_LOG_CHANNEL_ID directly
            if CASE_LOG_CHANNEL_ID:
                await client.send_message(
                    CASE_LOG_CHANNEL_ID,
                    f"🚨 **उल्लंघन:** `{violation_type}`\n"
                    f"ग्रुप: `{message.chat.title}` (ID: `{group_id}`)\n"
                    f"यूज़र: [{message.from_user.first_name}](tg://user?id={message.from_user.id}) (ID: `{message.from_user.id}`)\n"
                    f"मैसेज: `{original_content}`"
                )

            warning_text = (
                f"⚠️ **आपत्तिजनक सामग्री का पता चला** ⚠️\n\n"
                f"[{message.from_user.first_name}](tg://user?id={message.from_user.id}) ने नियमों का उल्लंघन किया है।\n"
                f"यह संदेश स्वचालित रूप से हटा दिया गया है।"
            )

            keyboard = [
                [InlineKeyboardButton("👤 यूज़र प्रोफ़ाइल देखें", url=f"tg://user?id={message.from_user.id}")],
                [InlineKeyboardButton("🔨 कार्रवाई करें", callback_data=f"take_action_{message.from_user.id}_{group_id}")],
                [InlineKeyboardButton("📋 केस देखें", url=f"https://t.me/c/{str(CASE_LOG_CHANNEL_ID)[4:]}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await client.send_message(
                chat_id=group_id,
                text=warning_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"[{group_id}] Warning message sent to group for user {message.from_user.id}.")

        except Exception as e:
            logger.error(f"[{group_id}] FATAL ERROR: Error handling violation for {message.from_user.id}: {e}", exc_info=True)
    else:
        logger.info(f"[{group_id}] No violation detected for message from user {message.from_user.id}.")


# --- नए मेंबर/ग्रुप इवेंट्स हैंडलर ---
@pyrogram_app.on_message(filters.new_chat_members | filters.left_chat_member & filters.group)
async def handle_new_chat_members(client: Client, message: Message):
    logger.info(f"[{message.chat.id}] New/Left chat members event in chat '{message.chat.title}'.")

    if message.new_chat_members and client.me.id in [member.id for member in message.new_chat_members]:
        logger.info(f"[{message.chat.id}] Bot was added to group.")
        inviter_info = None
        if message.from_user:
            inviter_info = {"id": message.from_user.id, "username": message.from_user.username or message.from_user.first_name}
        
        add_or_update_group(message.chat.id, message.chat.title, inviter_info['id'] if inviter_info else OWNER_ID)
        logger.info(f"[{message.chat.id}] Group {message.chat.id} added/updated in DB (on bot join).")

        thank_you_message = (
            f"🤖 **नमस्ते!** मैं `{client.me.first_name}` हूँ, आपके ग्रुप का नया पुलिस बॉट।\n\n"
            "मुझे जोड़ने के लिए धन्यवाद! मैं इस ग्रुप को स्पैम और अवांछित सामग्री से सुरक्षित रखने में मदद करूँगा।"
            "\n\nकृपया मुझे ग्रुप में **एडमिन** बना दें ताकि मैं ठीक से काम कर सकूँ!"
        )

        thank_you_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")],
            [InlineKeyboardButton("⚙️ सेटिंग्स प्रबंधित करें (PM)", url=f"https://t.me/{client.me.username}?start=settings")]
        ])

        try:
            await client.send_message(
                chat_id=message.chat.id,
                text=thank_you_message,
                reply_markup=thank_you_keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"[{message.chat.id}] 'Thank you for adding me' message sent to group.")
        except Exception as e:
            logger.error(f"[{message.chat.id}] Error sending 'Thank you for adding me' message: {e}", exc_info=True)

        if NEW_USER_GROUP_LOG_CHANNEL_ID:
            try:
                await client.send_message(
                    NEW_USER_GROUP_LOG_CHANNEL_ID,
                    f"➕ **नया ग्रुप जोड़ा गया:**\n"
                    f"नाम: `{message.chat.title}`\n"
                    f"ID: `{message.chat.id}`\n"
                    f"जोड़ने वाला: {message.from_user.mention if message.from_user else 'अज्ञात'}"
                )
            except Exception as e:
                logger.error(f"Error logging new group to channel: {e}")
        return

    group_settings = get_group(message.chat.id)
    if not group_settings or not group_settings.get('bot_enabled', True):
        logger.info(f"[{message.chat.id}] Bot disabled or no settings for this group. Ignoring new/left member event (after bot join).")
        return

    if message.new_chat_members:
        for member in message.new_chat_members:
            if member.is_bot and member.id != client.me.id:
                logger.info(f"[{message.chat.id}] New member is a bot: {member.id} ({member.first_name}). Attempting to kick.")
                try:
                    bot_member_in_chat = await client.get_chat_member(message.chat.id, client.me.id)
                    if not bot_member_in_chat.can_restrict_members:
                        logger.warning(f"[{message.chat.id}] Bot does not have 'can_restrict_members' permission. Cannot kick bot {member.id}.")
                        await client.send_message(message.chat.id, f"⚠️ **चेतावनी:** मैं नए बॉट [{member.first_name}](tg://user?id={member.id}) को हटा नहीं सकता क्योंकि मेरे पास 'सदस्यों को प्रतिबंधित करें' (Restrict Members) की अनुमति नहीं है।")
                        continue
                        
                    await client.ban_chat_member(message.chat.id, member.id)
                    await client.unban_chat_member(message.chat.id, member.id)
                    await client.send_message(
                        message.chat.id,
                        f"🤖 नया बॉट [{member.first_name}](tg://user?id={member.id}) पाया गया और हटा दिया गया।"
                    )
                    logger.info(f"[{message.chat.id}] Bot {member.id} kicked successfully and message sent.")
                except Exception as e:
                    logger.error(f"[{message.chat.id}] Error kicking bot {member.id}: {e}", exc_info=True)
            elif not member.is_bot:
                logger.info(f"[{message.chat.id}] New human user: {member.id} ({member.first_name}).")
                add_or_update_user(member.id, member.username, member.first_name, member.last_name, False)
                
                if NEW_USER_GROUP_LOG_CHANNEL_ID:
                    try:
                        await client.send_message(
                            NEW_USER_GROUP_LOG_CHANNEL_ID,
                            f"➕ **नया सदस्य:**\n"
                            f"यूज़र: [{member.first_name}](tg://user?id={member.id}) (ID: `{member.id}`)\n"
                            f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)"
                        )
                    except Exception as e:
                        logger.error(f"Error logging new user to channel: {e}")

                welcome_msg = group_settings.get('welcome_message', WELCOME_MESSAGE_DEFAULT)
                formatted_welcome = welcome_msg.replace("{username}", member.mention).replace("{groupname}", html.escape(message.chat.title))

                welcome_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")]
                ])

                try:
                    await client.send_message(message.chat.id, formatted_welcome, reply_markup=welcome_keyboard, parse_mode=ParseMode.MARKDOWN)
                    logger.info(f"[{message.chat.id}] Welcome message sent to new user {member.id}.")
                except Exception as e:
                    logger.error(f"[{message.chat.id}] Error sending welcome message to {member.id}: {e}", exc_info=True)

    if message.left_chat_member:
        member = message.left_chat_member
        if member.id == client.me.id:
            delete_group(message.chat.id)
            logger.info(f"Bot was removed from group {message.chat.title} ({message.chat.id}). Group data deleted.")
            if CASE_LOG_CHANNEL_ID:
                try:
                    await client.send_message(
                        CASE_LOG_CHANNEL_ID,
                        f"➖ **बॉट हटाया गया:**\n"
                        f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)\n"
                        f"हटाने वाला: {message.from_user.mention if message.from_user else 'अज्ञात'}"
                    )
                except Exception as e:
                    logger.error(f"Error logging bot removed event: {e}")
        elif not member.is_bot:
            if NEW_USER_GROUP_LOG_CHANNEL_ID:
                try:
                    await client.send_message(
                        NEW_USER_GROUP_LOG_CHANNEL_ID,
                        f"➖ **सदस्य चला गया:**\n"
                        f"यूज़र: [{member.first_name}](tg://user?id={member.id}) (ID: `{member.id}`)\n"
                        f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)"
                    )
                except Exception as e:
                    logger.error(f"Error logging left user to channel: {e}")


# --- बॉट मालिक कमांड्स ---
@pyrogram_app.on_message(filters.command("broadcast") & filters.user(OWNER_ID) & filters.private)
async def broadcast_command(client: Client, message: Message):
    logger.info(f"Owner {message.from_user.id} received /broadcast command.")
    if not check_cooldown(message.from_user.id, "command"):
        return

    if not message.text or len(message.command) < 2:
        await message.reply_text("कृपया प्रसारण के लिए एक संदेश प्रदान करें।")
        logger.warning(f"Owner {message.from_user.id} did not provide message for broadcast.")
        return

    message_to_broadcast = message.text.split(None, 1)[1]
    all_groups = get_all_groups()
    logger.info(f"Attempting to broadcast message to {len(all_groups)} groups.")

    sent_count = 0
    failed_count = 0
    failed_groups = []

    for group in all_groups:
        try:
            chat_member = await client.get_chat_member(group["_id"], client.me.id)
            if chat_member.status != ChatMemberStatus.LEFT:
                await client.send_message(chat_id=group["_id"], text=message_to_broadcast)
                sent_count += 1
                logger.info(f"Broadcasted to group {group['_id']} ({group.get('title', 'N/A')}).")
                await asyncio.sleep(0.1)
            else:
                logger.warning(f"Bot is not a member of group {group['_id']} ({group.get('title', 'N/A')}). Skipping broadcast.")
                failed_count += 1
                failed_groups.append(f"{group.get('title', 'N/A')} ({group['_id']}) - Bot not member")
        except Exception as e:
            logger.error(f"Error broadcasting to group {group['_id']} ({group.get('title', 'N/A')}): {e}", exc_info=True)
            failed_count += 1
            failed_groups.append(f"{group.get('title', 'N/A')} ({group['_id']}) - Error: {e}")

    summary_message = f"संदेश {sent_count} ग्रुप्स को सफलतापूर्वक भेजा गया।"
    if failed_count > 0:
        summary_message += f"\n\n**{failed_count} ग्रुप्स में भेजने में विफल:**\n"
        summary_message += "\n".join(failed_groups[:10])
        if len(failed_groups) > 10:
            summary_message += f"\n...और {len(failed_groups) - 10} अन्य।"
    
    await message.reply_text(summary_message)
    logger.info(f"Broadcast completed. Sent to {sent_count} groups, failed for {failed_count}.")

@pyrogram_app.on_message(filters.command("stats") & filters.user(OWNER_ID) & filters.private)
async def stats_command(client: Client, message: Message):
    logger.info(f"Owner {message.from_user.id} received /stats command.")
    if not check_cooldown(message.from_user.id, "command"):
        return

    group_count = len(get_all_groups())
    # You might need to add get_total_users() and get_total_violations() to database.py
    # For now, I'll use placeholders if they are not yet implemented.
    # If you have them, ensure they are imported from database.py
    total_users_count = 0 # Placeholder
    total_violations_count = 0 # Placeholder
    
    # Example of how to get actual counts if implemented in database.py
    # from database import get_total_users, get_total_violations
    # total_users_count = get_total_users()
    # total_violations_count = get_total_violations()


    stats_message = (
        f"📊 **बॉट आंकड़े** 📊\n\n"
        f"**जुड़े हुए ग्रुप्स:** `{group_count}`\n"
        f"**कुल ट्रैक किए गए यूज़र्स:** `{total_users_count}`\n"
        f"**कुल उल्लंघन:** `{total_violations_count}`\n\n"
        f"सोर्स कोड: [GitHub]({REPO_LINK})\n"
        f"अपडेट चैनल: @{UPDATE_CHANNEL_USERNAME}\n"
        f"मालिक: @{ASBHAI_USERNAME}"
    )
    await message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"Stats sent to owner {message.from_user.id}. Groups: {group_count}, Users: {total_users_count}, Violations: {total_violations_count}.")


# --- Admin Commands (Group specific) ---

@pyrogram_app.on_message(filters.command("ban") & filters.group)
async def ban_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मुझे यूज़र को बैन करने के लिए एडमिन अनुमति चाहिए।")
        return
    
    target_user_id = None
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            target_user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप बैन करना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप बैन करना चाहते हैं।")
        return

    if target_user_id == client.me.id:
        await message.reply_text("मैं खुद को बैन नहीं कर सकता।")
        return
    if target_user_id == message.from_user.id:
        await message.reply_text("आप खुद को बैन नहीं कर सकते।")
        return
    if target_user_id == OWNER_ID:
        await message.reply_text("आप मालिक को बैन नहीं कर सकते।")
        return

    try:
        await client.ban_chat_member(message.chat.id, target_user_id)
        user_info = await client.get_users(target_user_id)
        await message.reply_text(f"✅ {user_info.mention} को इस ग्रुप से बैन कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user_id} banned in group {message.chat.id} by {message.from_user.id}.")
        
        if CASE_LOG_CHANNEL_ID:
            await client.send_message(
                CASE_LOG_CHANNEL_ID,
                f"🚫 **यूज़र बैन किया गया:**\n"
                f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)\n"
                f"बैन किया गया यूज़र: [{user_info.first_name}](tg://user?id={user_info.id}) (ID: `{user_info.id}`)\n"
                f"बैन करने वाला एडमिन: {message.from_user.mention} (ID: `{message.from_user.id}`)"
            )
    except Exception as e:
        logger.error(f"Error banning user {target_user_id} in {message.chat.id}: {e}")
        await message.reply_text(f"यूज़र को बैन करने में त्रुटि आई: `{e}`")


@pyrogram_app.on_message(filters.command("unban") & filters.group)
async def unban_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मुझे यूज़र को अनबैन करने के लिए एडमिन अनुमति चाहिए।")
        return
    
    target_user_id = None
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            target_user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप अनबैन करना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप अनबैन करना चाहते हैं।")
        return

    try:
        await client.unban_chat_member(message.chat.id, target_user_id)
        user_info = await client.get_users(target_user_id)
        await message.reply_text(f"✅ {user_info.mention} को इस ग्रुप से अनबैन कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user_id} unbanned in group {message.chat.id} by {message.from_user.id}.")
        
        if CASE_LOG_CHANNEL_ID:
            await client.send_message(
                CASE_LOG_CHANNEL_ID,
                f"🔓 **यूज़र अनबैन किया गया:**\n"
                f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)\n"
                f"अनबैन किया गया यूज़र: [{user_info.first_name}](tg://user?id={user_info.id}) (ID: `{user_info.id}`)\n"
                f"अनबैन करने वाला एडमिन: {message.from_user.mention} (ID: `{message.from_user.id}`)"
            )
    except Exception as e:
        logger.error(f"Error unbanning user {target_user_id} in {message.chat.id}: {e}")
        await message.reply_text(f"यूज़र को अनबैन करने में त्रुटि आई: `{e}`")


@pyrogram_app.on_message(filters.command("kick") & filters.group)
async def kick_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मुझे यूज़र को किक करने के लिए एडमिन अनुमति चाहिए।")
        return

    target_user_id = None
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            target_user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप किक करना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप किक करना चाहते हैं।")
        return

    if target_user_id == client.me.id:
        await message.reply_text("मैं खुद को किक नहीं कर सकता।")
        return
    if target_user_id == message.from_user.id:
        await message.reply_text("आप खुद को किक नहीं कर सकते।")
        return
    if target_user_id == OWNER_ID:
        await message.reply_text("आप मालिक को किक नहीं कर सकते।")
        return
    
    try:
        await client.restrict_chat_member(message.chat.id, target_user_id, 
                                          ChatPermissions(can_send_messages=False), 
                                          datetime.now() + timedelta(minutes=1))
        await client.unban_chat_member(message.chat.id, target_user_id)
        user_info = await client.get_users(target_user_id)
        await message.reply_text(f"✅ {user_info.mention} को इस ग्रुप से किक कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user_id} kicked from group {message.chat.id} by {message.from_user.id}.")

        if CASE_LOG_CHANNEL_ID:
            await client.send_message(
                CASE_LOG_CHANNEL_ID,
                f"👟 **यूज़र किक किया गया:**\n"
                f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)\n"
                f"किक किया गया यूज़र: [{user_info.first_name}](tg://user?id={user_info.id}) (ID: `{user_info.id}`)\n"
                f"किक करने वाला एडमिन: {message.from_user.mention} (ID: `{message.from_user.id}`)"
            )
    except Exception as e:
        logger.error(f"Error kicking user {target_user_id} in {message.chat.id}: {e}")
        await message.reply_text(f"यूज़र को किक करने में त्रुटि आई: `{e}`")


@pyrogram_app.on_message(filters.command("mute") & filters.group)
async def mute_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मुझे यूज़र को म्यूट करने के लिए एडमिन अनुमति चाहिए।")
        return

    target_user_id = None
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            target_user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप म्यूट करना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप म्यूट करना चाहते हैं।")
        return

    if target_user_id == client.me.id:
        await message.reply_text("मैं खुद को म्यूट नहीं कर सकता।")
        return
    if target_user_id == message.from_user.id:
        await message.reply_text("आप खुद को म्यूट नहीं कर सकते।")
        return
    if target_user_id == OWNER_ID:
        await message.reply_text("आप मालिक को म्यूट नहीं कर सकते।")
        return

    duration = None
    if len(message.command) > 2:
        try:
            duration_value = int(message.command[2])
            duration_unit = message.command[3].lower() if len(message.command) > 3 else "m"
            if duration_unit.startswith("h"):
                duration = timedelta(hours=duration_value)
            elif duration_unit.startswith("d"):
                duration = timedelta(days=duration_value)
            else: # default to minutes
                duration = timedelta(minutes=duration_value)
        except ValueError:
            await message.reply_text("अमान्य अवधि। उदाहरण: `/mute 123456789 30m` (30 मिनट), `/mute 1h` (1 घंटा), `/mute 7d` (7 दिन)")
            return

    try:
        await client.restrict_chat_member(message.chat.id, target_user_id, 
                                          ChatPermissions(can_send_messages=False), 
                                          (datetime.now() + duration) if duration else None)
        user_info = await client.get_users(target_user_id)
        if duration:
            await message.reply_text(f"✅ {user_info.mention} को {duration.total_seconds() // 60} मिनट के लिए म्यूट कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
            logger.info(f"User {target_user_id} muted for {duration} in group {message.chat.id} by {message.from_user.id}.")
        else:
            await message.reply_text(f"✅ {user_info.mention} को म्यूट कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
            logger.info(f"User {target_user_id} muted indefinitely in group {message.chat.id} by {message.from_user.id}.")

        if CASE_LOG_CHANNEL_ID:
            duration_str = f" for {duration}" if duration else " indefinitely"
            await client.send_message(
                CASE_LOG_CHANNEL_ID,
                f"🔇 **यूज़र म्यूट किया गया:**\n"
                f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)\n"
                f"म्यूट किया गया यूज़र: [{user_info.first_name}](tg://user?id={user_info.id}) (ID: `{user_info.id}`)\n"
                f"म्यूट करने वाला एडमिन: {message.from_user.mention} (ID: `{message.from_user.id}`)\n"
                f"अवधि: {duration_str}"
            )
    except Exception as e:
        logger.error(f"Error muting user {target_user_id} in {message.chat.id}: {e}")
        await message.reply_text(f"यूज़र को म्यूट करने में त्रुटि आई: `{e}`")


@pyrogram_app.on_message(filters.command("unmute") & filters.group)
async def unmute_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मुझे यूज़र को अनम्यूट करने के लिए एडमिन अनुमति चाहिए।")
        return

    target_user_id = None
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            target_user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप अनम्यूट करना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप अनम्यूट करना चाहते हैं।")
        return

    try:
        await client.restrict_chat_member(message.chat.id, target_user_id, ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True,
            can_change_info=False,
            can_invite_users=True,
            can_pin_messages=False,
            can_manage_topics=False
        ))
        user_info = await client.get_users(target_user_id)
        await message.reply_text(f"✅ {user_info.mention} को अनम्यूट कर दिया गया है।", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user_id} unmuted in group {message.chat.id} by {message.from_user.id}.")

        if CASE_LOG_CHANNEL_ID:
            await client.send_message(
                CASE_LOG_CHANNEL_ID,
                f"🔊 **यूज़र अनम्यूट किया गया:**\n"
                f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)\n"
                f"अनम्यूट किया गया यूज़र: [{user_info.first_name}](tg://user?id={user_info.id}) (ID: `{user_info.id}`)\n"
                f"अनम्यूट करने वाला एडमिन: {message.from_user.mention} (ID: `{message.from_user.id}`)"
            )
    except Exception as e:
        logger.error(f"Error unmuting user {target_user_id} in {message.chat.id}: {e}")
        await message.reply_text(f"यूज़र को अनम्यूट करने में त्रुटि आई: `{e}`")


@pyrogram_app.on_message(filters.command("warn") & filters.group)
async def warn_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मुझे यूज़र को चेतावनी देने के लिए एडमिन अनुमति चाहिए।")
        return

    target_user = None
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            target_user = await client.get_users(int(message.command[1]))
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप चेतावनी देना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसे आप चेतावनी देना चाहते हैं।")
        return

    if not target_user:
        await message.reply_text("कोई मान्य यूज़र नहीं मिला।")
        return
    
    if target_user.id == client.me.id:
        await message.reply_text("मैं खुद को चेतावनी नहीं दे सकता।")
        return
    if target_user.id == message.from_user.id:
        await message.reply_text("आप खुद को चेतावनी नहीं दे सकते।")
        return
    if target_user.id == OWNER_ID:
        await message.reply_text("आप मालिक को चेतावनी नहीं दे सकते।")
        return

    current_warns = add_warn(message.chat.id, target_user.id)
    group_data = get_group(message.chat.id)
    warn_limit = group_data.get("warn_limit", 3) # Get warn limit from group settings

    warn_message = f"⚠️ {target_user.mention} को {current_warns}/{warn_limit} चेतावनी मिली है।"
    
    if current_warns >= warn_limit:
        await client.ban_chat_member(message.chat.id, target_user.id)
        warn_message += f"\n{target_user.mention} को {warn_limit} चेतावनियों के बाद ग्रुप से बैन कर दिया गया है।"
        delete_warns(message.chat.id, target_user.id)
        logger.info(f"User {target_user.id} banned in group {message.chat.id} after reaching warn limit.")

        if CASE_LOG_CHANNEL_ID:
            await client.send_message(
                CASE_LOG_CHANNEL_ID,
                f"⛔ **चेतावनी के बाद बैन:**\n"
                f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)\n"
                f"यूज़र: [{target_user.first_name}](tg://user?id={target_user.id}) (ID: `{target_user.id}`)\n"
                f"चेतावनी देने वाला एडमिन: {message.from_user.mention} (ID: `{message.from_user.id}`)\n"
                f"चेतावनी संख्या: `{current_warns}`"
            )

    await message.reply_text(warn_message, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {target_user.id} warned in group {message.chat.id} by {message.from_user.id}. Total warns: {current_warns}.")


@pyrogram_app.on_message(filters.command("warnings") & filters.group)
async def warnings_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    
    target_user = None
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            target_user = await client.get_users(int(message.command[1]))
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसकी चेतावनियाँ आप देखना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसकी चेतावनियाँ आप देखना चाहते हैं।")
        return

    if not target_user:
        await message.reply_text("कोई मान्य यूज़र नहीं मिला।")
        return

    current_warns = get_warns(message.chat.id, target_user.id)
    await message.reply_text(f"{target_user.mention} के पास {current_warns} चेतावनियाँ हैं।", parse_mode=ParseMode.MARKDOWN)


@pyrogram_app.on_message(filters.command("resetwarns") & filters.group)
async def resetwarns_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    
    target_user = None
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            target_user = await client.get_users(int(message.command[1]))
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसकी चेतावनियाँ आप रीसेट करना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसकी चेतावनियाँ आप रीसेट करना चाहते हैं।")
        return

    if not target_user:
        await message.reply_text("कोई मान्य यूज़र नहीं मिला।")
        return

    delete_warns(message.chat.id, target_user.id)
    await message.reply_text(f"✅ {target_user.mention} की चेतावनियाँ रीसेट कर दी गई हैं।", parse_mode=ParseMode.MARKDOWN)
    logger.info(f"Warns for user {target_user.id} in group {message.chat.id} reset by {message.from_user.id}.")

    if CASE_LOG_CHANNEL_ID:
        await client.send_message(
            CASE_LOG_CHANNEL_ID,
            f"🔄 **चेतावनी रीसेट:**\n"
            f"ग्रुप: `{message.chat.title}` (ID: `{message.chat.id}`)\n"
            f"यूज़र: [{target_user.first_name}](tg://user?id={target_user.id}) (ID: `{target_user.id}`)\n"
            f"रीसेट करने वाला एडमिन: {message.from_user.mention} (ID: `{message.from_user.id}`)"
        )


@pyrogram_app.on_message(filters.command("info") & filters.group)
async def info_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    
    target_user = None
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            target_user = await client.get_users(int(message.command[1]))
        except ValueError:
            await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसकी जानकारी आप देखना चाहते हैं।")
            return
    else:
        await message.reply_text("कृपया उस यूज़र को रिप्लाई करें या यूज़र ID प्रदान करें जिसकी जानकारी आप देखना चाहते हैं।")
        return

    if not target_user:
        await message.reply_text("कोई मान्य यूज़र नहीं मिला।")
        return

    user_data = get_user(target_user.id)
    warn_count = get_warns(message.chat.id, target_user.id)

    info_text = (
        f"👤 **यूज़र जानकारी:**\n"
        f"  • ID: `{target_user.id}`\n"
        f"  • नाम: `{target_user.first_name}`"
    )
    if target_user.last_name:
        info_text += f" `{target_user.last_name}`"
    if target_user.username:
        info_text += f"\n  • यूज़रनेम: @{target_user.username}"
    info_text += f"\n  • बॉट: {'✅ हाँ' if target_user.is_bot else '❌ नहीं'}"
    info_text += f"\n  • चेतावनियाँ (इस ग्रुप में): `{warn_count}`"

    if user_data:
        info_text += f"\n  • बॉट से आखिरी बातचीत: `{user_data.get('last_seen', 'N/A')}`"
        # Add more user data if stored

    await message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)


@pyrogram_app.on_message(filters.command("setwelcome") & filters.group)
async def set_welcome_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मुझे सेटिंग्स बदलने के लिए एडमिन अनुमति चाहिए।")
        return

    new_welcome_message = message.text.split(None, 1)[1] if len(message.command) > 1 else None

    if not new_welcome_message:
        await message.reply_text("कृपया एक वेलकम मैसेज प्रदान करें। उदाहरण: `/setwelcome वेलकम {username}!`")
        return
    
    update_group_settings(message.chat.id, {"welcome_message": new_welcome_message})
    await message.reply_text(
        f"✅ वेलकम मैसेज अपडेट किया गया है।\nनया मैसेज: `{html.escape(new_welcome_message)}`\n\n"
        "यह सुनिश्चित करने के लिए कि यह काम करता है, वेलकम मैसेज सेटिंग चालू है या नहीं, `/settings` देखें।"
    )
    logger.info(f"Group {message.chat.id}: Custom welcome message set by {message.from_user.id}.")


@pyrogram_app.on_message(filters.command("clean") & filters.group)
async def clean_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मुझे मैसेज डिलीट करने के लिए एडमिन अनुमति चाहिए।")
        return

    count = 1
    if len(message.command) > 1:
        try:
            count = int(message.command[1])
            if count <= 0 or count > 100:
                await message.reply_text("कृपया 1 से 100 के बीच की संख्या प्रदान करें।")
                return
        except ValueError:
            await message.reply_text("अमान्य संख्या। उदाहरण: `/clean 10`")
            return

    try:
        # Delete the command message itself + 'count' number of messages before it
        await client.delete_messages(
            chat_id=message.chat.id,
            message_ids=[message.id] + list(range(message.id - count, message.id))
        )
        logger.info(f"Deleted {count} messages in group {message.chat.id} by {message.from_user.id}.")
    except Exception as e:
        logger.error(f"Error deleting messages in group {message.chat.id}: {e}")
        await message.reply_text(f"मैसेज डिलीट करने में त्रुटि आई: `{e}`")


@pyrogram_app.on_message(filters.command("settings") & filters.group)
async def group_settings_command(client: Client, message: Message):
    if not await is_user_admin_in_chat(client, message.chat.id, message.from_user.id):
        await message.reply_text("आपको यह कमांड चलाने के लिए एडमिन होना चाहिए।")
        return
    if not await is_bot_admin_in_chat(client, message.chat.id):
        await message.reply_text("मैं इस ग्रुप में एडमिन नहीं हूँ। कृपया मुझे एडमिन अनुमति दें।")
        return
    
    await show_group_settings(client, message, message.chat.id)


# --- Run the Bot ---
if __name__ == "__main__":
    logger.info("Bot starting...")
    pyrogram_app.run()
    logger.info("Bot stopped.")
