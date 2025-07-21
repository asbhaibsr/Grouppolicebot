from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions, Message
from pyrogram.errors import FloodWait, PeerIdInvalid, UserNotParticipant, ChatAdminRequired, BadRequest
from pyrogram.enums import ChatType, ParseMode

from datetime import datetime
import asyncio
import time

from config import (
    BOT_TOKEN, API_ID, API_HASH, OWNER_ID, CASE_LOG_CHANNEL_ID,
    NEW_USER_GROUP_LOG_CHANNEL_ID, UPDATE_CHANNEL_USERNAME, ASBHAI_USERNAME,
    BOT_PHOTO_URL, REPO_LINK, COMMAND_COOLDOWN_TIME, logger
)
from database import (
    add_or_update_group, get_group_settings, update_group_setting,
    add_or_update_user, add_violation, get_total_users, get_total_violations,
    get_all_groups, log_new_user_or_group, set_user_biolink_exception,
    get_user_biolink_exception, add_keywords, remove_keywords, get_all_keyword_lists
)
from filters import (
    is_abusive, is_pornographic_text, contains_links, is_spam,
    has_bio_link, contains_usernames
)

# Initialize Pyrogram Client
app = Client(
    "group_police_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Cooldowns for commands ---
user_last_command_time = {}

async def is_on_cooldown(user_id: int) -> bool:
    """Checks if a user is on cooldown for commands."""
    last_time = user_last_command_time.get(user_id)
    if last_time and (time.time() - last_time < COMMAND_COOLDOWN_TIME):
        return True
    user_last_command_time[user_id] = time.time()
    return False

# --- Helper Function for Admin Check ---
async def is_user_admin_in_chat(chat_id: int, user_id: int) -> bool:
    """Checks if a user is an admin in a specific chat."""
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except Exception as e:
        logger.error(f"Error checking admin status for user {user_id} in chat {chat_id}: {e}")
        return False

# --- Startup Message ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    is_bot_user = message.from_user.is_bot

    await add_or_update_user(user_id, username, first_name, last_name, is_bot_user)

    if await is_on_cooldown(user_id):
        await message.reply_text(f"थोड़ा इंतज़ार करें! यह कमांड {COMMAND_COOLDOWN_TIME} सेकंड के कूलडाउन पर है।")
        return

    welcome_text = (
        f"👋 नमस्ते {message.from_user.mention}! मैं {client.me.mention} हूँ, आपका ग्रुप पुलिस बॉट।\n\n"
        "मैं ग्रुप को गालियों, पोर्नोग्राफिक टेक्स्ट, स्पैम, लिंक्स और अवांछित यूजरनेम से सुरक्षित रखने में मदद करता हूँ।\n\n"
        "अपने ग्रुप में मुझे जोड़कर और एडमिन अनुमतियाँ देकर आप इसका उपयोग कर सकते हैं।"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ मुझे ग्रुप में जोड़ें", url=f"https://t.me/{client.me.username}?startgroup=true"),
                InlineKeyboardButton("🌐 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")
            ],
            [
                InlineKeyboardButton("❓ सहायता", callback_data="help_menu"), # इस बटन पर क्लिक करने पर हेल्प मेनू खुलेगा
                InlineKeyboardButton("📞 मुझसे संपर्क करें", url=f"https://t.me/{ASBHAI_USERNAME}")
            ],
            [
                InlineKeyboardButton("📊 बॉट के आँकड़े", callback_data="bot_stats"),
                InlineKeyboardButton("⚙️ ग्रुप सेटिंग्स", callback_data="group_settings")
            ]
        ]
    )
    await message.reply_photo(
        photo=BOT_PHOTO_URL,
        caption=welcome_text,
        reply_markup=keyboard
    )

# --- Callback Query Handler ---
@app.on_callback_query()
async def button_callback_handler(client: Client, query):
    user_id = query.from_user.id
    action = query.data

    if await is_on_cooldown(user_id):
        await query.answer(f"थोड़ा इंतज़ार करें! यह कमांड {COMMAND_COOLDOWN_TIME} सेकंड के कूलडाउन पर है।", show_alert=True)
        return

    if action == "help_menu":
        help_text = (
            "**👋 बॉट कैसे काम करता है और क्या कमांड्स हैं?**\n\n"
            "मैं आपके ग्रुप को सुरक्षित और स्वच्छ रखने के लिए बनाया गया हूँ। मैं गालियों, स्पैम, लिंक्स, और आपत्तिजनक टेक्स्ट को स्वचालित रूप से फ़िल्टर कर सकता हूँ।\n\n"
            "**ग्रुप में इस्तेमाल कैसे करें:**\n"
            "1. **मुझे अपने ग्रुप में जोड़ें।**\n"
            "2. **मुझे ग्रुप का पूर्ण एडमिन बनाएं** (विशेषकर संदेश हटाने, सदस्यों को प्रतिबंधित करने की अनुमति दें)।\n"
            "3. मैं ग्रुप में आते ही डिफ़ॉल्ट सेटिंग्स के साथ काम करना शुरू कर दूंगा। आप `/settings` कमांड (निजी चैट में) का उपयोग करके सेटिंग्स बदल सकते हैं।\n\n"
            "**कुछ महत्वपूर्ण कमांड्स:**\n"
            " `/start` - बॉट को शुरू करें (निजी चैट में)\n"
            " `/settings` - ग्रुप की मॉडरेशन सेटिंग्स बदलें (निजी चैट में)\n"
            " `/stats` - बॉट के उपयोग के आँकड़े देखें (निजी चैट में)\n"
            " `/connectgroup <Group ID>` - बॉट को किसी ग्रुप से मैन्युअल रूप से कनेक्ट करें (निजी चैट में)\n\n"
            "**नोट:** ये सभी कमांड निजी चैट में मेरे साथ काम करेंगी। ग्रुप के भीतर, मैं स्वचालित रूप से फ़िल्टर करूँगा और आप मेरे बटन का उपयोग करके कार्यवाहियाँ कर सकते हैं।"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅️ वापस", callback_data="start_menu")]
            ]
        )
        try:
            await query.message.edit_text(help_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            logger.error(f"Error editing help message: {e}")
            await query.answer("सहायता संदेश अपडेट करने में त्रुटि हुई।", show_alert=True)

    elif action == "start_menu":
        welcome_text = (
            f"👋 नमस्ते {query.from_user.mention}! मैं {client.me.mention} हूँ, आपका ग्रुप पुलिस बॉट।\n\n"
            "मैं ग्रुप को गालियों, पोर्नोग्राफिक टेक्स्ट, स्पैम, लिंक्स और अवांछित यूजरनेम से सुरक्षित रखने में मदद करता हूँ।\n\n"
            "अपने ग्रुप में मुझे जोड़कर और एडमिन अनुमतियाँ देकर आप इसका उपयोग कर सकते हैं।"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("➕ मुझे ग्रुप में जोड़ें", url=f"https://t.me/{client.me.username}?startgroup=true"),
                    InlineKeyboardButton("🌐 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")
                ],
                [
                    InlineKeyboardButton("❓ सहायता", callback_data="help_menu"),
                    InlineKeyboardButton("📞 मुझसे संपर्क करें", url=f"https://t.me/{ASBHAI_USERNAME}")
                ],
                [
                    InlineKeyboardButton("📊 बॉट के आँकड़े", callback_data="bot_stats"),
                    InlineKeyboardButton("⚙️ ग्रुप सेटिंग्स", callback_data="group_settings")
                ]
            ]
        )
        try:
            await query.message.edit_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            logger.error(f"Error editing start menu message: {e}")
            await query.answer("स्टार्ट मेनू अपडेट करने में त्रुटि हुई।", show_alert=True)

    elif action == "bot_stats":
        total_users = get_total_users()
        total_violations = get_total_violations()
        total_groups = len(get_all_groups()) # Adjusted to count from database

        stats_text = (
            "📊 **बॉट के आँकड़े:**\n"
            f"👥 कुल उपयोगकर्ता: `{total_users}`\n"
            f"🚫 कुल उल्लंघन: `{total_violations}`\n"
            f"🏘️ कुल जुड़े हुए ग्रुप: `{total_groups}`\n\n"
            f"मालिक: @{ASBHAI_USERNAME}\n"
            f"स्रोत कोड: [GitHub]({REPO_LINK})"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅️ वापस", callback_data="start_menu")]
            ]
        )
        try:
            await query.message.edit_text(stats_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            logger.error(f"Error editing stats message: {e}")
            await query.answer("आँकड़े संदेश अपडेट करने में त्रुटि हुई।", show_alert=True)

    elif action == "group_settings":
        # Check if the user is in a private chat and is an owner
        if query.message.chat.type == ChatType.PRIVATE:
            if user_id == OWNER_ID:
                all_groups = get_all_groups()
                if not all_groups:
                    await query.answer("कोई ग्रुप कनेक्ट नहीं है। पहले एक ग्रुप जोड़ें।", show_alert=True)
                    return

                # Create buttons for each group
                group_buttons = []
                for group in all_groups:
                    group_buttons.append([InlineKeyboardButton(group['name'], callback_data=f"show_group_settings_{group['id']}")])
                
                group_buttons.append([InlineKeyboardButton("⬅️ वापस", callback_data="start_menu")])
                
                keyboard = InlineKeyboardMarkup(group_buttons)
                await query.message.edit_text("कृपया उस ग्रुप का चयन करें जिसकी सेटिंग्स आप बदलना चाहते हैं:", reply_markup=keyboard)
            else:
                await query.answer("आपको इस कमांड का उपयोग करने की अनुमति नहीं है।", show_alert=True)
        else:
            await query.answer("यह कमांड केवल निजी चैट में काम करती है।", show_alert=True)

    elif action.startswith("show_group_settings_"):
        group_id = int(action.split("_")[3])
        settings = get_group_settings(group_id)
        
        if not settings:
            await query.answer("ग्रुप सेटिंग्स नहीं मिलीं।", show_alert=True)
            return

        settings_text = f"⚙️ **{settings['name']} की सेटिंग्स:**\n\n"
        buttons = []

        # Bot Enabled
        bot_status = "✅ सक्षम" if settings.get('bot_enabled', True) else "❌ अक्षम"
        buttons.append([InlineKeyboardButton(f"बॉट: {bot_status}", callback_data=f"toggle_setting_{group_id}_bot_enabled")])

        # Filters
        filters_map = {
            "filter_abusive": "गालियाँ",
            "filter_pornographic_text": "आपत्तिजनक टेक्स्ट",
            "filter_spam": "स्पैम",
            "filter_links": "लिंक्स",
            "filter_bio_links": "बायो लिंक्स",
            "usernamedel_enabled": "यूजरनेम फिल्टर"
        }

        for setting_key, display_name in filters_map.items():
            status = "✅ सक्षम" if settings.get(setting_key, True) else "❌ अक्षम"
            buttons.append([InlineKeyboardButton(f"{display_name}: {status}", callback_data=f"toggle_setting_{group_id}_{setting_key}")])

        # Welcome Message
        buttons.append([InlineKeyboardButton("वेलकम मैसेज बदलें", callback_data=f"edit_welcome_message_{group_id}")])
        
        buttons.append([InlineKeyboardButton("⬅️ वापस", callback_data="group_settings")]) # Back to group list

        keyboard = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(settings_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    elif action.startswith("toggle_setting_"):
        parts = action.split("_")
        group_id = int(parts[2])
        setting_name = parts[3]
        
        settings = get_group_settings(group_id)
        current_value = settings.get(setting_name)
        new_value = not current_value # Toggle boolean

        update_group_setting(group_id, setting_name, new_value)
        await query.answer(f"{setting_name} को {'सक्षम' if new_value else 'अक्षम'} कर दिया गया है।", show_alert=True)
        
        # Re-display settings to reflect change
        await query.message.edit_text(
            f"⚙️ **{settings['name']} की सेटिंग्स:**\n\n",
            reply_markup=await get_group_settings_keyboard(group_id) # Helper to rebuild keyboard
        )

    elif action.startswith("edit_welcome_message_"):
        group_id = int(action.split("_")[3])
        await query.answer("अभी यह फ़ंक्शन विकसित किया जा रहा है।", show_alert=True)
        # TODO: Implement welcome message editing logic (e.g., prompt user for new message)
        # For now, just show an alert.

    elif action.startswith("action_"):
        # This part handles mute/kick/ban actions from violation messages
        parts = action.split("_")
        action_type = parts[1] # mute, kick, ban
        target_user_id = int(parts[2])
        target_group_id = int(parts[3])
        message_id_to_delete = int(parts[4])

        chat_member = await app.get_chat_member(target_group_id, query.from_user.id)
        if chat_member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            await query.answer("आपको इस ग्रुप में इस कार्रवाई को करने की अनुमति नहीं है।", show_alert=True)
            return

        try:
            if action_type == "mute":
                await app.restrict_chat_member(target_group_id, target_user_id, ChatPermissions())
                await query.answer("उपयोगकर्ता को म्यूट कर दिया गया है।", show_alert=True)
            elif action_type == "kick":
                await app.ban_chat_member(target_group_id, target_user_id)
                await query.answer("उपयोगकर्ता को किक कर दिया गया है।", show_alert=True)
            elif action_type == "ban":
                await app.ban_chat_member(target_group_id, target_user_id)
                await query.answer("उपयोगकर्ता को ग्रुप से बैन कर दिया गया है।", show_alert=True)
            
            # Delete the original violation message from the group
            try:
                await app.delete_messages(target_group_id, message_id_to_delete)
                logger.info(f"Deleted violation message {message_id_to_delete} in group {target_group_id}")
            except Exception as e:
                logger.error(f"Could not delete message {message_id_to_delete} in group {target_group_id}: {e}")

            # Edit the log channel message to indicate action taken
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"{action_type.capitalize()}ed by {query.from_user.first_name}", callback_data="done")
            ]]))
            
        except ChatAdminRequired:
            await query.answer("बॉट के पास इस कार्रवाई को करने के लिए आवश्यक एडमिन अनुमतियाँ नहीं हैं।", show_alert=True)
        except Exception as e:
            logger.error(f"Error performing {action_type} on user {target_user_id} in chat {target_group_id}: {e}")
            await query.answer(f"कार्रवाई करने में असमर्थ: {e}", show_alert=True)

    else:
        await query.answer("अज्ञात कार्रवाई।")

# Helper to generate group settings keyboard (avoids repetition)
async def get_group_settings_keyboard(group_id: int):
    settings = get_group_settings(group_id)
    if not settings:
        return InlineKeyboardMarkup([[InlineKeyboardButton("सेटिंग्स नहीं मिलीं", callback_data="group_settings")]])

    buttons = []
    bot_status = "✅ सक्षम" if settings.get('bot_enabled', True) else "❌ अक्षम"
    buttons.append([InlineKeyboardButton(f"बॉट: {bot_status}", callback_data=f"toggle_setting_{group_id}_bot_enabled")])

    filters_map = {
        "filter_abusive": "गालियाँ",
        "filter_pornographic_text": "आपत्तिजनक टेक्स्ट",
        "filter_spam": "स्पैम",
        "filter_links": "लिंक्स",
        "filter_bio_links": "बायो लिंक्स",
        "usernamedel_enabled": "यूजरनेम फिल्टर"
    }

    for setting_key, display_name in filters_map.items():
        status = "✅ सक्षम" if settings.get(setting_key, True) else "❌ अक्षम"
        buttons.append([InlineKeyboardButton(f"{display_name}: {status}", callback_data=f"toggle_setting_{group_id}_{setting_key}")])

    buttons.append([InlineKeyboardButton("वेलकम मैसेज बदलें", callback_data=f"edit_welcome_message_{group_id}")])
    buttons.append([InlineKeyboardButton("⬅️ वापस", callback_data="group_settings")])
    return InlineKeyboardMarkup(buttons)

# --- Group Join Handler ---
@app.on_message(filters.new_chat_members & filters.group)
async def welcome_new_members(client: Client, message: Message):
    chat_id = message.chat.id
    chat_title = message.chat.title

    # Log group addition if bot is added for the first time
    if client.me in message.new_chat_members:
        # Check if group already exists in DB, if not, add it
        group_settings = get_group_settings(chat_id)
        if not group_settings:
            added_by_user_id = message.from_user.id if message.from_user else None
            await add_or_update_group(chat_id, chat_title, added_by_user_id)
            
            log_message = f"**🆕 नया ग्रुप जोड़ा गया!**\n" \
                          f"ग्रुप का नाम: `{chat_title}`\n" \
                          f"ग्रुप ID: `{chat_id}`\n" \
                          f"जोड़ने वाला: {message.from_user.mention if message.from_user else 'अज्ञात'}"
            try:
                await client.send_message(NEW_USER_GROUP_LOG_CHANNEL_ID, log_message, parse_mode=ParseMode.MARKDOWN)
                logger.info(f"Sent new group log to {NEW_USER_GROUP_LOG_CHANNEL_ID}")
            except Exception as e:
                logger.error(f"Error sending new group log: {e}")
        else:
            logger.info(f"Bot re-added to existing group: {chat_title} ({chat_id})")

    group_settings = get_group_settings(chat_id)
    if not group_settings or not group_settings.get("bot_enabled", True):
        logger.info(f"Bot not enabled in group {chat_title} ({chat_id}). Skipping welcome message.")
        return

    for user in message.new_chat_members:
        if user.is_bot:
            continue # Don't welcome other bots

        await add_or_update_user(user.id, user.username, user.first_name, user.last_name, user.is_bot)

        welcome_msg_template = group_settings.get("welcome_message", "👋 नमस्ते {username}! {groupname} में आपका स्वागत है।")
        welcome_text = welcome_msg_template.format(
            username=user.mention,
            groupname=chat_title
        )
        try:
            await message.reply_text(welcome_text, quote=True)
            logger.info(f"Sent welcome message to {user.id} in {chat_id}")
        except Exception as e:
            logger.error(f"Error sending welcome message to {user.id} in {chat_id}: {e}")

        # Log new user addition
        inviter_id = message.from_user.id if message.from_user else None
        inviter_username = message.from_user.username if message.from_user else None
        log_new_user_or_group("new_user", user.id, user.first_name, inviter_id, inviter_username)
        try:
            await client.send_message(
                NEW_USER_GROUP_LOG_CHANNEL_ID,
                f"**👤 नया उपयोगकर्ता जुड़ा!**\n"
                f"नाम: {user.first_name} (@{user.username if user.username else 'N/A'})\n"
                f"ID: `{user.id}`\n"
                f"ग्रुप: `{chat_title}` (`{chat_id}`)\n"
                f"जोड़ने वाला: {message.from_user.mention if message.from_user else 'अज्ञात'}",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"Sent new user log for {user.id} to {NEW_USER_GROUP_LOG_CHANNEL_ID}")
        except Exception as e:
            logger.error(f"Error sending new user log for {user.id}: {e}")

# --- Message Filter Handler (Main Logic for Group Moderation) ---
@app.on_message(filters.group & filters.text & ~filters.me)
async def process_message(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"
    first_name = message.from_user.first_name or ""
    chat_title = message.chat.title or "N/A"
    message_text = message.text

    # Add or update user info in DB
    await add_or_update_user(user_id, username, first_name, message.from_user.last_name, message.from_user.is_bot)

    group_settings = get_group_settings(chat_id)
    if not group_settings or not group_settings.get("bot_enabled", True):
        return # Bot is not enabled in this group

    # Check if the user is an admin or owner of the group - don't filter admins
    if await is_user_admin_in_chat(chat_id, user_id):
        logger.debug(f"User {user_id} is admin in {chat_id}. Skipping filters.")
        return

    violation_found = False
    violation_type = None

    # Filter checks based on group settings
    if group_settings.get("filter_abusive", True) and is_abusive(message_text):
        violation_found = True
        violation_type = "गाली"
    elif group_settings.get("filter_pornographic_text", True) and is_pornographic_text(message_text):
        violation_found = True
        violation_type = "आपत्तिजनक टेक्स्ट"
    elif group_settings.get("filter_links", True) and contains_links(message_text):
        violation_found = True
        violation_type = "लिंक"
    elif group_settings.get("filter_spam", True) and is_spam(message_text):
        violation_found = True
        violation_type = "स्पैम"
    elif group_settings.get("usernamedel_enabled", True) and contains_usernames(message_text):
        violation_found = True
        violation_type = "यूजरनेम"

    # Bio link check
    if group_settings.get("filter_bio_links", True) and not get_user_biolink_exception(user_id):
        user_has_bio_link = await has_bio_link(client, user_id)
        if user_has_bio_link:
            violation_found = True
            violation_type = "बायो लिंक"

    if violation_found:
        logger.warning(f"Violation detected for {username} ({user_id}) in {chat_title} ({chat_id}): {violation_type}")
        await add_violation(username, user_id, chat_title, chat_id, violation_type, message_text)

        try:
            # Delete the offending message
            await message.delete()
            logger.info(f"Deleted message by {user_id} in {chat_id} due to {violation_type}.")
        except ChatAdminRequired:
            logger.error(f"Bot is not admin in {chat_id} or missing 'Delete Messages' permission. Cannot delete message.")
            await app.send_message(chat_id, "मेरे पास संदेश हटाने की अनुमति नहीं है। कृपया मुझे 'Delete Messages' अनुमति दें।")
            return
        except Exception as e:
            logger.error(f"Error deleting message in {chat_id}: {e}")
            return # Don't proceed to send case if message deletion failed

        # Send case to log channel
        case_message_link = f"https://t.me/c/{str(chat_id)[4:]}/{message.id}" # Format for public channel link
        
        case_text = (
            f"🚫 **नया उल्लंघन दर्ज किया गया!**\n"
            f"**उपयोगकर्ता:** {message.from_user.mention} (ID: `{user_id}`)\n"
            f"**ग्रुप:** `{chat_title}` (ID: `{chat_id}`)\n"
            f"**उल्लंघन का प्रकार:** `{violation_type}`\n"
            f"**मूल सामग्री:** `{(message_text[:100] + '...') if len(message_text) > 100 else message_text}`\n"
            f"**समय:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⚠️ म्यूट करें", callback_data=f"action_mute_{user_id}_{chat_id}_{message.id}"),
                    InlineKeyboardButton("🚷 किक करें", callback_data=f"action_kick_{user_id}_{chat_id}_{message.id}"),
                    InlineKeyboardButton("⛔ बैन करें", callback_data=f"action_ban_{user_id}_{chat_id}_{message.id}")
                ],
                [
                    InlineKeyboardButton("संदेश पर जाएं", url=case_message_link) # Add link to original message
                ]
            ]
        )

        try:
            await client.send_message(CASE_LOG_CHANNEL_ID, case_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"Sent case for user {user_id} to {CASE_LOG_CHANNEL_ID}")
        except Exception as e:
            logger.error(f"Error sending case to log channel {CASE_LOG_CHANNEL_ID}: {e}")
            await app.send_message(chat_id, "मैं केस लॉग चैनल पर संदेश नहीं भेज पा रहा हूँ। कृपया जांचें कि मैंने चैनल में सही अनुमति के साथ जोड़ा गया है।")
            
# --- Connect Group Command (Private Chat Only) ---
@app.on_message(filters.command("connectgroup") & filters.private & filters.user(OWNER_ID))
async def connect_group_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("उपयोग: `/connectgroup <ग्रुप ID>`")
        return

    try:
        group_id = int(message.command[1])
    except ValueError:
        await message.reply_text("अमान्य ग्रुप ID। कृपया एक संख्यात्मक ID प्रदान करें।")
        return

    try:
        chat_info = await client.get_chat(group_id)
        if chat_info.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.reply_text("प्रदान की गई ID एक वैध ग्रुप ID नहीं है।")
            return
        
        # Ensure bot is a member of the group before connecting
        try:
            await client.get_chat_member(group_id, client.me.id)
        except UserNotParticipant:
            await message.reply_text("बॉट इस ग्रुप का सदस्य नहीं है। कृपया पहले बॉट को ग्रुप में जोड़ें।")
            return

        # Add or update group in database
        await add_or_update_group(group_id, chat_info.title, message.from_user.id)
        await message.reply_text(f"`{chat_info.title}` (`{group_id}`) ग्रुप सफलतापूर्वक कनेक्ट हो गया है।")
        logger.info(f"Owner connected group: {chat_info.title} ({group_id})")

    except PeerIdInvalid:
        await message.reply_text("Peer ID Invalid। सुनिश्चित करें कि ग्रुप ID सही है और बॉट ग्रुप का सदस्य है।")
        logger.error(f"PeerIdInvalid for group ID: {group_id}")
    except Exception as e:
        logger.error(f"Error connecting group {group_id}: {e}")
        await message.reply_text(f"ग्रुप ढूंढने या जोड़ने में असमर्थ। सुनिश्चित करें कि बॉट उस ग्रुप का सदस्य है और ID सही है। एरर: {e}")

# --- Set Bio Link Exception Command (Owner Only) ---
@app.on_message(filters.command(["addbioex", "removebioex"]) & filters.private & filters.user(OWNER_ID))
async def bio_link_exception_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("उपयोग:\n`/addbioex <उपयोगकर्ता ID>` - उपयोगकर्ता को बायो लिंक अपवाद जोड़ें\n`/removebioex <उपयोगकर्ता ID>` - उपयोगकर्ता से बायो लिंक अपवाद हटाएँ")
        return

    try:
        target_user_id = int(message.command[1])
    except ValueError:
        await message.reply_text("अमान्य उपयोगकर्ता ID।")
        return

    allowed = (message.command[0] == "/addbioex")
    set_user_biolink_exception(target_user_id, allowed)
    await message.reply_text(f"उपयोगकर्ता `{target_user_id}` के लिए बायो लिंक अपवाद को {'सक्षम' if allowed else 'अक्षम'} कर दिया गया है।")
    logger.info(f"Owner {message.from_user.id} set biolink exception for {target_user_id} to {allowed}")


# --- Keyword Management Commands (Owner Only) ---
@app.on_message(filters.command(["addkeyword", "removekeyword", "listkeywords"]) & filters.private & filters.user(OWNER_ID))
async def manage_keywords_command(client: Client, message: Message):
    command = message.command[0]
    
    if command == "/listkeywords":
        all_lists = get_all_keyword_lists()
        if not all_lists:
            await message.reply_text("कोई कीवर्ड सूची परिभाषित नहीं है।")
            return
        
        response = "**उपलब्ध कीवर्ड सूचियां:**\n"
        for list_name in all_lists:
            words = get_keyword_list(list_name)
            response += f"**- {list_name}:** {', '.join(words[:10])}{'...' if len(words) > 10 else ''} ({len(words)} शब्द)\n"
        await message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        return

    if len(message.command) < 3:
        await message.reply_text("उपयोग:\n`/addkeyword <सूची का नाम> <शब्द1,शब्द2,...>`\n`/removekeyword <सूची का नाम> <शब्द1,शब्द2,...>`")
        return

    list_name = message.command[1]
    keywords_str = message.command[2]
    keywords_to_process = [k.strip().lower() for k in keywords_str.split(',') if k.strip()]

    if not keywords_to_process:
        await message.reply_text("कृपया जोड़ने या हटाने के लिए कुछ शब्द प्रदान करें।")
        return

    if command == "/addkeyword":
        count = add_keywords(list_name, keywords_to_process)
        await message.reply_text(f"सूची `{list_name}` में `{count}` शब्द {'जोड़े' if count > 0 else 'जोड़े नहीं गए'}।")
        logger.info(f"Owner {message.from_user.id} added {count} keywords to '{list_name}'")
    elif command == "/removekeyword":
        count = remove_keywords(list_name, keywords_to_process)
        await message.reply_text(f"सूची `{list_name}` से `{count}` शब्द {'हटाए' if count > 0 else 'हटाए नहीं गए'}।")
        logger.info(f"Owner {message.from_user.id} removed {count} keywords from '{list_name}'")

# --- Mute/Unmute/Ban (Direct commands in groups - Admin only) ---
@app.on_message(filters.command(["mute", "unmute", "ban"]) & filters.group)
async def moderation_commands(client: Client, message: Message):
    chat_id = message.chat.id
    command_type = message.command[0][1:] # 'mute', 'unmute', 'ban'
    
    if not message.reply_to_message:
        await message.reply_text("कृपया उस उपयोगकर्ता के संदेश का जवाब दें जिस पर आप यह कार्रवाई करना चाहते हैं।")
        return

    target_user = message.reply_to_message.from_user
    if not target_user: # In case of channel posts, etc.
        await message.reply_text("इस संदेश का कोई उपयोगकर्ता नहीं है।")
        return

    # Check if the issuer is admin
    if not await is_user_admin_in_chat(chat_id, message.from_user.id):
        await message.reply_text("आपके पास इस कमांड का उपयोग करने की अनुमति नहीं है।")
        return

    # Check if the bot is admin and has necessary permissions
    bot_member = await app.get_chat_member(chat_id, client.me.id)
    if bot_member.status != enums.ChatMemberStatus.ADMINISTRATOR:
        await message.reply_text("मुझे इस कार्रवाई को करने के लिए ग्रुप में एडमिन होना चाहिए।")
        return

    # Prevent bot from banning/muting itself or owner
    if target_user.id == client.me.id:
        await message.reply_text("मैं खुद पर कार्रवाई नहीं कर सकता।")
        return
    if target_user.id == OWNER_ID:
        await message.reply_text("आप मालिक पर कार्रवाई नहीं कर सकते।")
        return

    # Prevent admin from banning/muting other admins (unless issuer is owner)
    if await is_user_admin_in_chat(chat_id, target_user.id) and message.from_user.id != OWNER_ID:
        await message.reply_text("आप दूसरे एडमिन पर कार्रवाई नहीं कर सकते।")
        return
        
    try:
        if command_type == "mute":
            await app.restrict_chat_member(chat_id, target_user.id, ChatPermissions(can_send_messages=False))
            await message.reply_text(f"{target_user.mention} को म्यूट कर दिया गया है।")
            logger.info(f"User {target_user.id} muted in {chat_id} by {message.from_user.id}")
        elif command_type == "unmute":
            await app.restrict_chat_member(chat_id, target_user.id, ChatPermissions(can_send_messages=True))
            await message.reply_text(f"{target_user.mention} को अनम्यूट कर दिया गया है।")
            logger.info(f"User {target_user.id} unmuted in {chat_id} by {message.from_user.id}")
        elif command_type == "ban":
            await app.ban_chat_member(chat_id, target_user.id)
            await message.reply_text(f"{target_user.mention} को ग्रुप से बैन कर दिया गया है।")
            logger.info(f"User {target_user.id} banned from {chat_id} by {message.from_user.id}")
        
        # Delete the original message that was replied to, if moderation was successful
        try:
            await message.reply_to_message.delete()
        except Exception as e:
            logger.error(f"Failed to delete replied message: {e}")

    except ChatAdminRequired:
        await message.reply_text("मेरे पास इस कार्रवाई को करने के लिए आवश्यक एडमिन अनुमतियाँ नहीं हैं।")
        logger.warning(f"Bot lacks admin permissions for {command_type} in {chat_id}")
    except Exception as e:
        await message.reply_text(f"कार्रवाई करने में असमर्थ: {e}")
        logger.error(f"Error performing {command_type} on {target_user.id} in {chat_id}: {e}")

# --- नया फ़ंक्शन जिसे server.py इम्पोर्ट करेगा ---
async def start_bot():
    """Starts the Pyrogram bot client."""
    logger.info("Pyrogram bot client starting...")
    await app.start()
    logger.info("Pyrogram bot client started successfully.")

async def stop_bot():
    """Stops the Pyrogram bot client."""
    logger.info("Pyrogram bot client stopping...")
    await app.stop()
    logger.info("Pyrogram bot client stopped.")

# यदि bot.py को सीधे चलाया जाता है (Koyeb के मामले में यह आमतौर पर नहीं होगा)
if __name__ == "__main__":
    logger.info("Running bot.py directly (for testing purposes).")
    app.run()
    logger.info("Bot stopped.")
