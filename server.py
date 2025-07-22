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
from config import (
    BOT_TOKEN, API_ID, API_HASH, CASE_LOG_CHANNEL_ID, NEW_USER_GROUP_LOG_CHANNEL_ID,
    OWNER_ID, UPDATE_CHANNEL_USERNAME, ASBHAI_USERNAME,
    WELCOME_MESSAGE_DEFAULT, BOT_PHOTO_URL, REPO_LINK,
    COMMAND_COOLDOWN_TIME, logger # Import logger from config
)
from database import (
    add_or_update_user, get_user, add_or_update_group, get_group,
    update_group_settings, get_all_groups, delete_group,
    add_warn, get_warns, delete_warns,
    add_command_cooldown, get_command_cooldown, reset_command_cooldown
)
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
# In a real production scenario, use a proper WSGI server like Gunicorn or uWSGI
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
        # You can add a message here informing the user about cooldown if desired.
        return

    user = message.from_user
    add_or_update_user(user.id, user.username, user.first_name, user.last_name, user.is_bot)
    logger.info(f"User {user.id} data added/updated on /start.")

    # Removed the problematic client.get_dialogs() loop for bots.
    # Group connection logic now relies solely on /connectgroup command
    # and on_message for bot being added to groups.
    
    keyboard = [
        [InlineKeyboardButton("➕ ग्रुप में ऐड करें", url=f"https://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("❓ सहायता", callback_data="help_menu")],
        [InlineKeyboardButton("📢 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")],
        [InlineKeyboardButton("🔗 सोर्स कोड", url=REPO_LINK)],
        [InlineKeyboardButton("📞 मुझसे संपर्क करें", url=f"https://t.me/{ASBHAI_USERNAME}")]
    ]

    # Check if the user is an admin in any *known* connected group to show settings
    is_connected_group_admin = False
    all_current_groups = get_all_groups()
    for group_data in all_current_groups:
        try:
            # Check if bot is a member of this group (important before checking admin status)
            bot_member = await client.get_chat_member(group_data["id"], client.me.id)
            if bot_member.status != ChatMemberStatus.LEFT:
                if await is_user_admin_in_chat(client, group_data["id"], user.id):
                    is_connected_group_admin = True
                    break
        except Exception as e:
            # Log specific errors but don't stop the flow
            logger.warning(f"Error checking admin status for group {group_data['id']} after auto-connect attempt: {e}")

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
                bot_member = await client.get_chat_member(group_data["id"], client.me.id)
                if bot_member.status != ChatMemberStatus.LEFT:
                    if await is_user_admin_in_chat(client, group_data["id"], user_id):
                        is_connected_group_admin = True
                        break
            except Exception as e:
                logger.warning(f"Error checking admin status for group {group_data['id']} during start menu for user {user_id}: {e}")

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
        setting_name = parts[1]
        group_id = int(parts[2])

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
            # This will require user to send a message
            await callback_query.message.edit_text("कृपया नया वेलकम मैसेज भेजें। आप `{username}` और `{groupname}` का उपयोग कर सकते हैं।",
                                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस", callback_data=f"settings_menu")]]))
            # Set a temporary state for the user to wait for the next message
            # This is a basic way; for robust state management, you might use a dictionary or Redis.
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
    # Add other settings here as you implement them

    settings_text = (
        f"⚙️ **{group_title}** सेटिंग्स:\n\n"
        f"➡️ वेलकम मैसेज: {'✅ चालू' if welcome_enabled else '❌ बंद'}\n"
        f"➡️ एंटी-लिंक: {'✅ चालू' if anti_link_enabled else '❌ बंद'}\n"
        f"➡️ एंटी-फ्लड: {'✅ चालू' if anti_flood_enabled else '❌ बंद'}\n"
        # Add other settings display here
        f"\n**वर्तमान वेलकम मैसेज:**\n`{html.escape(welcome_message)}`"
    )

    keyboard = [
        [
            InlineKeyboardButton(f"वेलकम मैसेज: {'❌ बंद' if welcome_enabled else '✅ चालू'}", callback_data=f"welcome_toggle_{group_id}"),
            InlineKeyboardButton("वेलकम सेटिंग्स", callback_data=f"welcome_menu_{group_id}") # New button for welcome submenu
        ],
        [InlineKeyboardButton(f"एंटी-लिंक: {'❌ बंद' if anti_link_enabled else '✅ चालू'}", callback_data=f"toggle_anti_link_enabled_{group_id}")],
        [InlineKeyboardButton(f"एंटी-फ्लड: {'❌ बंद' if anti_flood_enabled else '✅ चालू'}", callback_data=f"toggle_anti_flood_enabled_{group_id}")],
        # Add other setting toggle buttons here
        [InlineKeyboardButton("🔙 सभी ग्रुप्स पर वापस", callback_data="settings_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.edit_caption(settings_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


async def show_private_settings_menu(client: Client, message: Message, user_id: int):
    # Get all groups where the user is an admin and the bot is a member
    user_admin_groups = []
    all_known_groups = get_all_groups()

    for group_data in all_known_groups:
        try:
            # Check if bot is a member of this group
            bot_member = await client.get_chat_member(group_data["id"], client.me.id)
            if bot_member.status != ChatMemberStatus.LEFT:
                if await is_user_admin_in_chat(client, group_data["id"], user_id):
                    user_admin_groups.append(group_data)
        except Exception as e:
            logger.warning(f"Could not verify bot/user admin status for group {group_data['id']}: {e}")

    if not user_admin_groups:
        await message.edit_text(
            "आप किसी भी ऐसे ग्रुप में एडमिन नहीं हैं जहाँ मैं मौजूद हूँ। "
            "कृपया मुझे अपने ग्रुप में एडमिन के रूप में ऐड करें।"
        )
        return

    keyboard = []
    for group in user_admin_groups:
        keyboard.append([InlineKeyboardButton(group["title"], callback_data=f"select_group_{group['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 वापस", callback_data="start_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.edit_text("कृपया उस ग्रुप का चयन करें जिसकी आप सेटिंग्स प्रबंधित करना चाहते हैं:", reply_markup=reply_markup)


# @pyrogram_app.on_message(filters.command("connectgroup") & filters.private)
# async def connect_group_command(client: Client, message: Message):
#     if not check_cooldown(message.from_user.id, "command"):
#         return

#     user_id = message.from_user.id
#     if user_id != OWNER_ID:
#         await message.reply_text("आप इस कमांड का उपयोग करने के लिए अधिकृत नहीं हैं।")
#         return

#     if len(message.command) < 2:
#         await message.reply_text("कृपया ग्रुप ID प्रदान करें। उदाहरण: `/connectgroup -1001234567890`")
#         return

#     try:
#         group_id = int(message.command[1])
#     except ValueError:
#         await message.reply_text("अमान्य ग्रुप ID। कृपया एक संख्यात्मक ID प्रदान करें।")
#         return

#     try:
#         chat = await client.get_chat(group_id)
#         if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
#             await message.reply_text("प्रदान की गई ID एक ग्रुप चैट की नहीं है।")
#             return
        
#         # Check if bot is a member and admin
#         bot_member = await client.get_chat_member(group_id, client.me.id)
#         if bot_member.status == ChatMemberStatus.LEFT:
#             await message.reply_text("मैं इस ग्रुप का सदस्य नहीं हूँ। कृपया मुझे पहले ग्रुप में ऐड करें।")
#             return
        
#         if bot_member.status != ChatMemberStatus.ADMINISTRATOR and bot_member.status != ChatMemberStatus.OWNER:
#             await message.reply_text("मैं इस ग्रुप में एडमिन नहीं हूँ। कृपया मुझे एडमिन अनुमति दें।")
#             return

#         add_or_update_group(group_id, chat.title, user_id) # owner_id will be the one who issued command
#         await message.reply_text(f"ग्रुप **{chat.title}** (ID: `{group_id}`) सफलतापूर्वक कनेक्ट हो गया है।")
#         logger.info(f"Group {group_id} ({chat.title}) manually connected by owner {user_id}.")

#     except Exception as e:
#         logger.error(f"Error connecting group {group_id}: {e}", exc_info=True)
#         await message.reply_text(f"ग्रुप कनेक्ट करने में त्रुटि आई: `{e}`")


@pyrogram_app.on_message(filters.new_chat_members & filters.group)
async def new_members_handler(client: Client, message: Message):
    group_id = message.chat.id
    group_title = message.chat.title
    
    # Add group to database if not already present
    group_data = get_group(group_id)
    if not group_data:
        # We don't have a specific admin who added the bot, so we just use the first new member or a placeholder
        # In a real scenario, you might want to find out who added the bot
        added_by_user_id = message.from_user.id if message.from_user else OWNER_ID 
        add_or_update_group(group_id, group_title, added_by_user_id)
        logger.info(f"New group {group_title} ({group_id}) added to database upon bot joining.")
        
        # Log to NEW_USER_GROUP_LOG_CHANNEL_ID
        if NEW_USER_GROUP_LOG_CHANNEL_ID:
            try:
                await client.send_message(
                    NEW_USER_GROUP_LOG_CHANNEL_ID,
                    f"🆕 **नया ग्रुप जुड़ा:**\n"
                    f"नाम: `{group_title}`\n"
                    f"ID: `{group_id}`\n"
                    f"जोड़ने वाला: {message.from_user.mention if message.from_user else 'अज्ञात'}"
                )
            except Exception as e:
                logger.error(f"Error logging new group to channel: {e}")

    # Process new members
    for member in message.new_chat_members:
        if member.id == client.me.id: # If the bot itself was added to the group
            await message.reply_text(
                f"👋 नमस्ते, मैं **{client.me.first_name}** हूँ!\n"
                "मुझे यहां जोड़ने के लिए धन्यवाद। मैं इस ग्रुप को मॉडरेट करने में आपकी मदद कर सकता हूँ।\n"
                "कृपया सुनिश्चित करें कि मेरे पास आवश्यक अनुमतियां हैं (जैसे मैसेज डिलीट करना, यूज़र्स को बैन/किक करना)।\n"
                "अधिक जानकारी के लिए `/help` टाइप करें।"
            )
            # Log this event to the case log channel
            if CASE_LOG_CHANNEL_ID:
                try:
                    await client.send_message(
                        CASE_LOG_CHANNEL_ID,
                        f"🤖 **बॉट जोड़ा गया:**\n"
                        f"ग्रुप: `{group_title}` (ID: `{group_id}`)\n"
                        f"जोड़ने वाला: {message.from_user.mention if message.from_user else 'अज्ञात'}"
                    )
                except Exception as e:
                    logger.error(f"Error logging bot added event: {e}")

        else: # Regular new member
            user_info = f"[{member.first_name}](tg://user?id={member.id})"
            group_info = message.chat.title

            group_settings = get_group(group_id)
            if group_settings and group_settings.get("welcome_enabled", False):
                welcome_msg = group_settings.get("welcome_message", WELCOME_MESSAGE_DEFAULT)
                formatted_welcome = welcome_msg.replace("{username}", user_info).replace("{groupname}", html.escape(group_info))
                try:
                    await message.reply_text(formatted_welcome, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error(f"Error sending welcome message in group {group_id}: {e}")
            
            # Log new user to log channel
            if NEW_USER_GROUP_LOG_CHANNEL_ID:
                try:
                    await client.send_message(
                        NEW_USER_GROUP_LOG_CHANNEL_ID,
                        f"➕ **नया सदस्य:**\n"
                        f"यूज़र: {user_info} (ID: `{member.id}`)\n"
                        f"ग्रुप: `{group_title}` (ID: `{group_id}`)"
                    )
                except Exception as e:
                    logger.error(f"Error logging new user to channel: {e}")


@pyrogram_app.on_message(filters.left_chat_member & filters.group)
async def left_members_handler(client: Client, message: Message):
    group_id = message.chat.id
    group_title = message.chat.title
    member = message.left_chat_member

    if member.id == client.me.id: # If the bot itself was removed
        delete_group(group_id)
        logger.info(f"Bot was removed from group {group_title} ({group_id}). Group data deleted.")
        if CASE_LOG_CHANNEL_ID:
            try:
                await client.send_message(
                    CASE_LOG_CHANNEL_ID,
                    f"➖ **बॉट हटाया गया:**\n"
                    f"ग्रुप: `{group_title}` (ID: `{group_id}`)\n"
                    f"हटाने वाला: {message.from_user.mention if message.from_user else 'अज्ञात'}"
                )
            except Exception as e:
                logger.error(f"Error logging bot removed event: {e}")
    else: # Regular member left
        # Log left user to log channel
        if NEW_USER_GROUP_LOG_CHANNEL_ID:
            try:
                await client.send_message(
                    NEW_USER_GROUP_LOG_CHANNEL_ID,
                    f"➖ **सदस्य चला गया:**\n"
                    f"यूज़र: [{member.first_name}](tg://user?id={member.id}) (ID: `{member.id}`)\n"
                    f"ग्रुप: `{group_title}` (ID: `{group_id}`)"
                )
            except Exception as e:
                logger.error(f"Error logging left user to channel: {e}")


@pyrogram_app.on_chat_member_updated(filters.group)
async def chat_member_update_handler(client: Client, chat_member_update: ChatMemberUpdated):
    user = chat_member_update.new_chat_member.user
    old_member = chat_member_update.old_chat_member
    new_member = chat_member_update.new_chat_member
    chat = chat_member_update.chat
    
    # If the bot itself gets updated (e.g., promoted/demoted)
    if user.id == client.me.id:
        if old_member and new_member.status != old_member.status:
            logger.info(f"Bot status updated in {chat.title} ({chat.id}): from {old_member.status} to {new_member.status}")
            if new_member.status == ChatMemberStatus.ADMINISTRATOR or new_member.status == ChatMemberStatus.OWNER:
                # If bot is promoted to admin, ensure group is in DB
                add_or_update_group(chat.id, chat.title, OWNER_ID) # Use owner_id as placeholder
                logger.info(f"Bot promoted to admin in {chat.title} ({chat.id}). Group ensured in DB.")
            elif new_member.status == ChatMemberStatus.MEMBER and old_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                logger.warning(f"Bot demoted from admin in {chat.title} ({chat.id}).")
            
            if CASE_LOG_CHANNEL_ID:
                try:
                    await client.send_message(
                        CASE_LOG_CHANNEL_ID,
                        f"🤖 **बॉट की स्थिति अपडेट हुई:**\n"
                        f"ग्रुप: `{chat.title}` (ID: `{chat.id}`)\n"
                        f"पुरानी स्थिति: `{old_member.status.name}`\n"
                        f"नई स्थिति: `{new_member.status.name}`"
                    )
                except Exception as e:
                    logger.error(f"Error logging bot status update: {e}")


@pyrogram_app.on_message(filters.text & filters.group & filters.create(is_not_edited_message) & ~filters.via_bot)
async def handle_group_messages(client: Client, message: Message):
    group_id = message.chat.id
    group_data = get_group(group_id)

    if not group_data:
        # Group is not in DB, add it with default settings
        add_or_update_group(group_id, message.chat.title, OWNER_ID) # Owner_ID as placeholder
        group_data = get_group(group_id) # Fetch newly added data
        logger.info(f"Group {message.chat.title} ({group_id}) auto-added to database on first message.")

    # --- Anti-Link Logic ---
    if group_data.get("anti_link_enabled", False):
        if message.entities:
            for entity in message.entities:
                if entity.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]:
                    if not await is_user_admin_in_chat(client, group_id, message.from_user.id):
                        try:
                            await message.delete()
                            await message.reply_text(f"{message.from_user.mention}, इस ग्रुप में लिंक की अनुमति नहीं है।", parse_mode=ParseMode.MARKDOWN)
                            logger.info(f"Deleted link from user {message.from_user.id} in group {group_id}.")
                            # Log to case log channel
                            if CASE_LOG_CHANNEL_ID:
                                try:
                                    await client.send_message(
                                        CASE_LOG_CHANNEL_ID,
                                        f"🔗 **लिंक हटाया गया:**\n"
                                        f"ग्रुप: `{message.chat.title}` (ID: `{group_id}`)\n"
                                        f"यूज़र: {message.from_user.mention} (ID: `{message.from_user.id}`)\n"
                                        f"मैसेज: `{message.text}`"
                                    )
                                except Exception as e:
                                    logger.error(f"Error logging deleted link: {e}")
                            return # Stop further processing for this message
                        except Exception as e:
                            logger.error(f"Could not delete link message in group {group_id}: {e}")

    # --- Anti-Flood Logic (Basic) ---
    # Implement anti-flood using a dictionary for message counts/timestamps
    # This is a basic in-memory flood protection; for large scale, use Redis/DB
    
    # --- Other moderation logic can be added here ---
    
    # Handle custom welcome message setting if a user is in a state of setting it
    if hasattr(client, 'waiting_for_welcome_message') and client.waiting_for_welcome_message == message.from_user.id:
        if group_id == client.waiting_for_welcome_group:
            new_welcome_message = message.text
            update_group_settings(group_id, {"welcome_message": new_welcome_message})
            logger.info(f"Group {group_id}: Custom welcome message set to '{new_welcome_message}' by user {message.from_user.id}.")
            await message.reply_text(
                f"✅ ग्रुप {message.chat.title} के लिए वेलकम मैसेज अपडेट किया गया है।\n"
                f"नया मैसेज: `{html.escape(new_welcome_message)}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 वापस सेटिंग्स", callback_data=f"back_to_settings_{group_id}")]])
            )
            del client.waiting_for_welcome_message
            del client.waiting_for_welcome_group
            return


# --- Admin Commands ---

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
        # Kick by restricting for 1 minute (effectively kick)
        await client.restrict_chat_member(message.chat.id, target_user_id, 
                                          ChatPermissions(can_send_messages=False), 
                                          datetime.now() + timedelta(minutes=1))
        await client.unban_chat_member(message.chat.id, target_user_id) # Immediately unban to allow re-joining
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
            can_manage_topics=False # For topic-enabled groups
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
    warn_limit = 3 # Example: 3 warns lead to ban

    warn_message = f"⚠️ {target_user.mention} को {current_warns}/{warn_limit} चेतावनी मिली है।"
    
    if current_warns >= warn_limit:
        await client.ban_chat_member(message.chat.id, target_user.id)
        warn_message += f"\n{target_user.mention} को 3 चेतावनियों के बाद ग्रुप से बैन कर दिया गया है।"
        delete_warns(message.chat.id, target_user.id) # Reset warns after ban
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
            if count <= 0 or count > 100: # Telegram API limit
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
        # Optional: Send a temporary message indicating deletion if you want, then delete that too
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
