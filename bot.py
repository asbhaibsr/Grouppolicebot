from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, Message
from pyrogram.enums import ParseMode, ChatType, ChatMemberStatus # ChatMemberStatus is important
from datetime import datetime, timedelta
import asyncio
import time

from config import (
    BOT_TOKEN, API_ID, API_HASH, CASE_LOG_CHANNEL_ID,
    NEW_USER_GROUP_LOG_CHANNEL_ID, OWNER_ID, WELCOME_MESSAGE_DEFAULT,
    logger, UPDATE_CHANNEL_USERNAME, ASBHAI_USERNAME,
    COMMAND_COOLDOWN_TIME, # MESSAGE_REPLY_COOLDOWN_TIME hata diya gaya hai
    BOT_PHOTO_URL, REPO_LINK
)
from database import (
    add_or_update_group, get_group_settings, update_group_setting, add_violation,
    get_user_biolink_exception, set_user_biolink_exception, get_all_groups,
    get_total_users, get_total_violations, add_or_update_user, log_new_user_or_group
)
from filters import (
    is_abusive, is_pornographic_text, contains_links, is_spam, has_bio_link, contains_usernames
)

# Pyrogram Client Instance
app = Client(
    "GroupPoliceBot", # Session name
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# यह एक अस्थायी डिक्शनरी है जो वेलकम मैसेज इनपुट के लिए यूज़र स्टेट को स्टोर करती है।
user_data_awaiting_input = {}
user_cooldowns = {} # Cooldowns for commands per user
# chat_message_cooldowns = {} # Chatbot related cooldown hata diya gaya hai

# --- सहायक फ़ंक्शन ---

async def is_user_admin_in_chat(client: Client, chat_id: int, user_id: int) -> bool:
    """चेक करता है कि यूज़र चैट में एडमिन है या नहीं।"""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except Exception as e:
        logger.error(f"Error checking admin status for user {user_id} in chat {chat_id}: {e}")
        return False

async def send_case_log_to_channel(client: Client, violation_data: dict):
    """उल्लंघन लॉग केस लॉग चैनल में भेजता है।"""
    log_message = (
        f"🚨 **नया उल्लंघन रिकॉर्डेड** 🚨\n\n"
        f"**उल्लंघनकर्ता:** [{violation_data['username']}](tg://user?id={violation_data['user_id']}) (ID: `{violation_data['user_id']}`)\n"
        f"**ग्रुप:** [{violation_data['group_name']}](https://t.me/c/{str(violation_data['group_id'])[4:]}) (ID: `{violation_data['group_id']}`)\n"
        f"**उल्लंघन का प्रकार:** `{violation_data['violation_type']}`\n"
        f"**समय:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
        f"--- **भेजी गई सामग्री** ---\n"
        f"`{violation_data['original_content']}`\n"
    )

    if violation_data.get('case_name'):
        log_message += f"\n**केस नेम:** `{violation_data['case_name']}`"

    try:
        await client.send_message(
            chat_id=CASE_LOG_CHANNEL_ID,
            text=log_message,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error sending case log to channel: {e}")

async def send_new_entry_log_to_channel(client: Client, log_type: str, entity_id: int, entity_name: str, inviter_info=None, group_info=None):
    """नए यूज़र या ग्रुप जुड़ने को लॉग चैनल में भेजता है।"""
    log_message = ""
    if log_type == "new_group":
        log_message = (
            f"➕ **नया ग्रुप जोड़ा गया** ➕\n\n"
            f"**ग्रुप नाम:** `{entity_name}`\n"
            f"**ग्रुप ID:** `{entity_id}`\n"
        )
        if inviter_info:
            log_message += f"**द्वारा जोड़ा गया:** [{inviter_info['username']}](tg://user?id={inviter_info['id']}) (ID: `{inviter_info['id']}`)\n"
    elif log_type == "new_user":
        log_message = (
            f"👥 **नया यूज़र ग्रुप में शामिल हुआ** 👥\n\n"
            f"**यूज़र:** [{entity_name}](tg://user?id={entity_id}) (ID: `{entity_id}`)\n"
        )
        if group_info:
             log_message += f"**ग्रुप:** [{group_info['name']}](https://t.me/c/{str(group_info['id'])[4:]})\n"

    log_message += f"**समय:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"

    try:
        await client.send_message(
            chat_id=NEW_USER_GROUP_LOG_CHANNEL_ID,
            text=log_message,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error sending new entry log to channel: {e}")

def check_cooldown(user_id, cooldown_type="command"):
    """चेक करता है और यूज़र के लिए कॉलिंग को अपडेट करता है।"""
    now = time.time()
    if cooldown_type == "command":
        if user_id in user_cooldowns and (now - user_cooldowns[user_id]) < COMMAND_COOLDOWN_TIME:
            return False # Still on cooldown
        user_cooldowns[user_id] = now
    # elif cooldown_type == "message_reply": # Chatbot related cooldown hata diya gaya hai
        # if user_id in chat_message_cooldowns and (now - chat_message_cooldowns[user_id]) < MESSAGE_REPLY_COOLDOWN_TIME:
            # return False
        # chat_message_cooldowns[user_id] = now
    return True

# --- कमांड हैंडलर्स ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    if not check_cooldown(message.from_user.id, "command"):
        return

    user = message.from_user
    add_or_update_user(user.id, user.username, user.first_name, user.last_name, user.is_bot)

    keyboard = [
        [InlineKeyboardButton("➕ ग्रुप में ऐड करें", url=f"https://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("❓ सहायता", callback_data="help_menu")],
        [InlineKeyboardButton("📢 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")],
        [InlineKeyboardButton("🔗 सोर्स कोड", url=REPO_LINK)],
        [InlineKeyboardButton("📞 मुझसे संपर्क करें", url=f"https://t.me/{ASBHAI_USERNAME}")]
    ]

    is_connected_group_admin = False
    all_connected_groups = get_all_groups()
    for group_data in all_connected_groups:
        if await is_user_admin_in_chat(client, group_data["id"], user.id):
            is_connected_group_admin = True
            break

    if is_connected_group_admin:
        keyboard.append([InlineKeyboardButton("⚙️ सेटिंग्स", callback_data="settings_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    start_message_text = (
        f"👋 नमस्ते {user.first_name}! मैं आपका ग्रुप पुलिस बॉट हूँ, {client.me.first_name}.\n\n"
        "मैं ग्रुप चैट को मॉडरेट करने, स्पैम, अनुचित सामग्री और अवांछित लिंक को फ़िल्टर करने में मदद करता हूँ।\n"
        "आपकी मदद कैसे कर सकता हूँ?"
    )
    
    try:
        await message.reply_photo(
            photo=BOT_PHOTO_URL, # बॉट की फोटो URL
            caption=start_message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error sending start message with photo: {e}. Sending text only.")
        await message.reply_text(
            start_message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )


@app.on_message(filters.command("connectgroup") & filters.private)
async def connect_group_command(client: Client, message: Message):
    if not check_cooldown(message.from_user.id, "command"):
        return

    if not message.text or len(message.command) < 2:
        await message.reply_text("कृपया ग्रुप ID प्रदान करें। उदाहरण: `/connectgroup -1234567890`")
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
    except Exception as e:
        await message.reply_text(f"ग्रुप ढूंढने में असमर्थ। सुनिश्चित करें कि बॉट उस ग्रुप का सदस्य है और ID सही है। एरर: {e}")
        return

    if not await is_user_admin_in_chat(client, group_id, message.from_user.id):
        await message.reply_text("आप इस ग्रुप के एडमिन नहीं हैं, इसलिए इसे कनेक्ट नहीं कर सकते।")
        return

    add_or_update_group(group_id, chat_info.title, message.from_user.id)
    await message.reply_text(f"ग्रुप '{chat_info.title}' सफलतापूर्वक कनेक्ट हो गया है! अब आप यहाँ से सेटिंग्स प्रबंधित कर सकते हैं।")
    
    await send_new_entry_log_to_channel(
        client, "new_group", chat_info.id, chat_info.title,
        {"id": message.from_user.id, "username": message.from_user.username or message.from_user.first_name}
    )


@app.on_message(filters.command("settings") & filters.private)
async def settings_menu_command(client: Client, message: Message):
    if not check_cooldown(message.from_user.id, "command"):
        return

    user = message.from_user
    connected_group = None
    all_groups = get_all_groups()
    for group_data in all_groups:
        if await is_user_admin_in_chat(client, group_data["id"], user.id):
            connected_group = group_data
            break

    if not connected_group:
        await message.reply_text(
            "कोई कनेक्टेड ग्रुप नहीं मिला या आप किसी कनेक्टेड ग्रुप के एडमिन नहीं हैं।\n"
            "कृपया पहले एक ग्रुप को `/connectgroup <groupid>` कमांड से कनेक्ट करें।"
        )
        return

    keyboard = await generate_settings_keyboard(connected_group["id"])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        f"'{connected_group['name']}' के लिए सेटिंग्स:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query()
async def button_callback_handler(client: Client, query):
    await query.answer()

    data = query.data
    parts = data.split('_')
    action = parts[0]

    if action == "toggle":
        setting_name = "_".join(parts[1:-1])
        group_id = int(parts[-1])
        
        if not await is_user_admin_in_chat(client, group_id, query.from_user.id):
            await query.message.edit_text("आपको यह सेटिंग बदलने की अनुमति नहीं है।")
            return

        group_settings = get_group_settings(group_id)
        if group_settings:
            current_value = group_settings.get(setting_name)
            new_value = not current_value
            update_group_setting(group_id, setting_name, new_value)
            
            updated_keyboard = await generate_settings_keyboard(group_id)
            await query.message.edit_text(
                f"'{group_settings['name']}' के लिए `{setting_name.replace('filter_', '').replace('_', ' ').replace('del_', ' ').capitalize()}` अब {'ON' if new_value else 'OFF'} है।\n"
                f"सेटिंग्स अपडेटेड।",
                reply_markup=InlineKeyboardMarkup(updated_keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text("ग्रुप सेटिंग्स नहीं मिली।")

    elif action == "set_welcome_message":
        group_id = int(parts[-1])
        user_data_awaiting_input[query.from_user.id] = {"awaiting_welcome_message_input": group_id}
        await query.message.edit_text(
            "कृपया अब नया वेलकम मैसेज भेजें। आप `{username}` और `{groupname}` का उपयोग कर सकते हैं।\n"
            "रद्द करने के लिए `/cancel` भेजें।"
        )
    
    elif action == "take_action":
        user_id_to_act = int(parts[2])
        group_id = int(parts[3])
        if not await is_user_admin_in_chat(client, group_id, query.from_user.id):
            await query.message.edit_text("आपको इस यूज़र पर कार्रवाई करने की अनुमति नहीं है।")
            return
            
        action_keyboard = [
            [InlineKeyboardButton("🔇 म्यूट करें (1 घंटा)", callback_data=f"mute_user_{user_id_to_act}_{group_id}_3600")],
            [InlineKeyboardButton("👢 किक करें", callback_data=f"kick_user_{user_id_to_act}_{group_id}")],
            [InlineKeyboardButton("🚫 बैन करें", callback_data=f"ban_user_{user_id_to_act}_{group_id}")],
            [InlineKeyboardButton("⚠️ चेतावनी दें", callback_data=f"warn_user_{user_id_to_act}_{group_id}")],
            [InlineKeyboardButton("❌ रद्द करें", callback_data=f"cancel_action_{user_id_to_act}_{group_id}")]
        ]
        await query.message.edit_text(
            f"[{user_id_to_act}](tg://user?id={user_id_to_act}) पर क्या कार्रवाई करनी है?",
            reply_markup=InlineKeyboardMarkup(action_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "manage_permission": # बायो लिंक अपवाद के लिए
        user_id_to_manage = int(parts[2])
        group_id = int(parts[3])
        if not await is_user_admin_in_chat(client, group_id, query.from_user.id):
            await query.message.edit_text("आपको इस यूज़र की अनुमति प्रबंधित करने की अनुमति नहीं है।")
            return

        current_permission = get_user_biolink_exception(user_id_to_manage)
        permission_status_text = "अनुमति मिली है" if current_permission else "अनुमति नहीं मिली है"

        permission_keyboard = [
            [InlineKeyboardButton("✅ अनुमति दें", callback_data=f"set_bio_permission_{user_id_to_manage}_true")],
            [InlineKeyboardButton("❌ अनुमति न दें", callback_data=f"set_bio_permission_{user_id_to_manage}_false")]
        ]
        await query.message.edit_text(
            f"[{user_id_to_manage}](tg://user?id={user_id_to_manage}) को बायो लिंक की अनुमति वर्तमान में: **{permission_status_text}**\n\n"
            f"अनुमति दें या नहीं दें?",
            reply_markup=InlineKeyboardMarkup(permission_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "set_bio_permission":
        user_id = int(parts[2])
        permission_status = parts[3] == 'true'
        set_user_biolink_exception(user_id, permission_status)
        await query.message.edit_text(f"[{user_id}](tg://user?id={user_id}) को बायो लिंक की अनुमति {'मिल गई है' if permission_status else 'नहीं मिली है'}।", parse_mode=ParseMode.MARKDOWN)

    elif action in ["mute_user", "kick_user", "ban_user", "warn_user"]:
        user_id = int(parts[2])
        group_id = int(parts[3])
        if not await is_user_admin_in_chat(client, group_id, query.from_user.id):
            await query.message.edit_text("आपको यह कार्रवाई करने की अनुमति नहीं है।")
            return

        try:
            target_user_info = await client.get_users(user_id)
            target_username = target_user_info.username or target_user_info.first_name
            
            if action == "mute_user":
                duration = int(parts[4])
                await client.restrict_chat_member(
                    chat_id=group_id,
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=datetime.now() + timedelta(seconds=duration)
                )
                await query.message.edit_text(f"@{target_username} को {duration/60} मिनट के लिए म्यूट कर दिया गया है।")
            elif action == "kick_user":
                await client.ban_chat_member(chat_id=group_id, user_id=user_id)
                await client.unban_chat_member(chat_id=group_id, user_id=user_id) # किक करने के लिए अनबैन भी करें
                await query.message.edit_text(f"@{target_username} को ग्रुप से किक कर दिया गया है।")
            elif action == "ban_user":
                await client.ban_chat_member(chat_id=group_id, user_id=user_id)
                await query.message.edit_text(f"@{target_username} को ग्रुप से बैन कर दिया गया है।")
            elif action == "warn_user":
                # चेतावनी लॉजिक यहां जोड़ें, जैसे चेतावनी काउंट बढ़ाना
                await query.message.edit_text(f"@{target_username} को चेतावनी दी गई है।")
        except Exception as e:
            await query.message.edit_text(f"कार्रवाई करने में एरर: {e}")
            logger.error(f"Action failed for user {user_id} in chat {group_id}: {e}")

    elif action == "close_settings":
        await query.message.edit_text("सेटिंग्स बंद कर दी गईं।")
    
    elif action == "help_menu":
        help_text = (
            "🤖 **ग्रुप पुलिस बॉट सहायता** 🤖\n\n"
            "मैं आपके ग्रुप को साफ और सुरक्षित रखने में मदद करता हूँ। यहाँ कुछ कमांड और मेरी विशेषताएं हैं:\n\n"
            "**निजी कमांड (मुझे PM करें):**\n"
            "• `/start`: बॉट शुरू करें और मुख्य मेनू देखें।\n"
            "• `/connectgroup <group_id>`: अपने ग्रुप को बॉट से कनेक्ट करें (आपको ग्रुप एडमिन होना चाहिए)।\n"
            "• `/settings`: अपने कनेक्टेड ग्रुप के लिए मॉडरेशन सेटिंग्स प्रबंधित करें।\n"
            "• `/broadcast <message>`: (केवल मालिक) सभी कनेक्टेड ग्रुप्स में संदेश भेजें।\n"
            "• `/stats`: (केवल मालिक) बॉट के उपयोग के आंकड़े देखें।\n\n"
            "**ग्रुप मॉडरेशन विशेषताएं:**\n"
            "• **गाली-गलौज फ़िल्टर**: आपत्तिजनक शब्दों को हटाता है।\n"
            "• **पॉर्नोग्राफिक टेक्स्ट फ़िल्टर**: पॉर्नोग्राफिक शब्दों को हटाता है।\n"
            "• **स्पैम फ़िल्टर**: अत्यधिक लंबे या दोहराए गए संदेशों को हटाता है।\n"
            "• **लिंक फ़िल्टर**: अवांछित लिंक को हटाता है।\n"
            "• **बायो लिंक फ़िल्टर**: उन यूज़र्स के संदेशों को हटाता है जिनके बायो में लिंक हैं (जिन्हें अनुमति नहीं है)।\n"
            "• **यूज़रनेम फ़िल्टर**: अन्य चैनल/बॉट के यूजरनेम को हटाता है।\n"
            "• **नया मेंबर वेलकम**: नए मेंबर्स को कस्टमाइजेबल वेलकम मैसेज भेजता है।\n"
            "• **ऑटो-रिमूव बॉट्स**: नए जुड़ने वाले बॉट्स को स्वचालित रूप से किक करता है।\n\n"
            "**ग्रुप एडमिन के लिए:**\n"
            "मॉडरेशन सेटिंग्स बदलने के लिए मुझे PM करें और `/settings` का उपयोग करें।\n"
            "किसी भी प्रश्न या सहायता के लिए, [मालिक से संपर्क करें](https://t.me/{ASBHAI_USERNAME})।"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ सेटिंग्स", callback_data="settings_menu")],
            [InlineKeyboardButton("🔗 सोर्स कोड", url=REPO_LINK)],
            [InlineKeyboardButton("📢 अपडेट चैनल", url=f"https://t.me/{UPDATE_CHANNEL_USERNAME}")]
        ])
        await query.message.edit_text(help_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def generate_settings_keyboard(group_id):
    """सेटिंग्स कीबोर्ड को डायनामिक रूप से जेनरेट करता है।"""
    group_settings = get_group_settings(group_id)
    if not group_settings:
        return []

    keyboard = [
        [InlineKeyboardButton(f"बॉट सक्षम: {'ON' if group_settings.get('bot_enabled') else 'OFF'}", callback_data=f"toggle_bot_enabled_{group_id}")],
        [InlineKeyboardButton(f"गाली-गलौज फ़िल्टर: {'ON' if group_settings.get('filter_abusive') else 'OFF'}", callback_data=f"toggle_filter_abusive_{group_id}")],
        [InlineKeyboardButton(f"पॉर्नोग्राफिक टेक्स्ट: {'ON' if group_settings.get('filter_pornographic_text') else 'OFF'}", callback_data=f"toggle_filter_pornographic_text_{group_id}")],
        [InlineKeyboardButton(f"स्पैम फ़िल्टर: {'ON' if group_settings.get('filter_spam') else 'OFF'}", callback_data=f"toggle_filter_spam_{group_id}")],
        [InlineKeyboardButton(f"लिंक फ़िल्टर: {'ON' if group_settings.get('filter_links') else 'OFF'}", callback_data=f"toggle_filter_links_{group_id}")],
        [InlineKeyboardButton(f"बायो लिंक फ़िल्टर: {'ON' if group_settings.get('filter_bio_links') else 'OFF'}", callback_data=f"toggle_filter_bio_links_{group_id}")],
        [InlineKeyboardButton(f"यूज़रनेम फ़िल्टर: {'ON' if group_settings.get('usernamedel_enabled') else 'OFF'}", callback_data=f"toggle_usernamedel_enabled_{group_id}")],
        [InlineKeyboardButton("वेलकम मैसेज सेट करें", callback_data=f"set_welcome_message_{group_id}")],
        [InlineKeyboardButton("✅ बंद करें", callback_data="close_settings")]
    ]
    return keyboard

@app.on_message(filters.text & filters.private & (lambda _, __, msg: not msg.text.startswith('/') and not msg.text.startswith('!')) & filters.user(lambda _, __, msg: msg.from_user.id in user_data_awaiting_input and 'awaiting_welcome_message_input' in user_data_awaiting_input[msg.from_user.id]))
async def handle_welcome_message_input(client: Client, message: Message):
    if message.from_user.id in user_data_awaiting_input and 'awaiting_welcome_message_input' in user_data_awaiting_input[message.from_user.id]:
        group_id = user_data_awaiting_input[message.from_user.id].pop('awaiting_welcome_message_input')
        new_welcome_message = message.text
        update_group_setting(group_id, 'welcome_message', new_welcome_message)
        await message.reply_text(f"वेलकम मैसेज सफलतापूर्वक अपडेट किया गया है।")
        
        group_settings = get_group_settings(group_id)
        if group_settings:
            keyboard = await generate_settings_keyboard(group_id)
            await message.reply_text(
                f"'{group_settings['name']}' के लिए सेटिंग्स:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
    elif message.text == "/cancel":
        if message.from_user.id in user_data_awaiting_input and 'awaiting_welcome_message_input' in user_data_awaiting_input[message.from_user.id]:
            user_data_awaiting_input[message.from_user.id].pop('awaiting_welcome_message_input')
            await message.reply_text("वेलकम मैसेज सेट करना रद्द कर दिया गया है।")

# --- मुख्य मैसेज हैंडलर (ग्रुप में) ---
@app.on_message(filters.text & filters.group & ~filters.edited)
async def handle_group_message(client: Client, message: Message):
    chat = message.chat
    user = message.from_user
    
    # अपने खुद के बॉट या अन्य बॉट्स के मैसेज को इग्नोर करें
    if user.is_bot:
        return

    add_or_update_user(user.id, user.username, user.first_name, user.last_name, user.is_bot)

    group_settings = get_group_settings(chat.id)
    if not group_settings or not group_settings.get('bot_enabled', True):
        return # यदि ग्रुप कनेक्टेड नहीं है या बॉट अक्षम है, तो कुछ न करें

    violation_detected = False
    violation_type = None
    original_content = message.text
    case_name = None

    # 1. गाली-गलौज और पॉर्नोग्राफिक टेक्स्ट
    if group_settings.get('filter_abusive') and is_abusive(message.text):
        violation_detected = True
        violation_type = "गाली-गलौज"
        case_name = "आपत्तिजनक भाषा का प्रयोग"
    elif group_settings.get('filter_pornographic_text') and is_pornographic_text(message.text):
        violation_detected = True
        violation_type = "पॉर्नोग्राफिक टेक्स्ट"
        case_name = "पॉर्नोग्राफिक सामग्री"
    # 2. स्पैमिंग और सामान्य लिंक
    elif group_settings.get('filter_spam') and is_spam(message.text):
        violation_detected = True
        violation_type = "स्पैम"
        case_name = "संदिग्ध स्पैम"
    elif group_settings.get('filter_links') and contains_links(message.text):
        violation_detected = True
        violation_type = "लिंक"
        case_name = "अनधिकृत लिंक"
    # 3. बायो लिंक वाला यूज़र का मैसेज
    elif group_settings.get('filter_bio_links'):
        has_bio = await has_bio_link(client, user.id)
        if has_bio:
            if not get_user_biolink_exception(user.id): # यदि यूज़र को अनुमति नहीं है
                violation_detected = True
                violation_type = "बायो_लिंक_उल्लंघन"
                case_name = "बायो में अनधिकृत लिंक"
    # 4. यूज़रनेम फ़िल्टर
    elif group_settings.get('usernamedel_enabled') and contains_usernames(message.text):
        violation_detected = True
        violation_type = "यूज़रनेम"
        case_name = "यूज़रनेम प्रचार"


    # --- उल्लंघन होने पर कार्रवाई ---
    if violation_detected:
        try:
            await message.delete()

            log_data = {
                'username': user.username or user.first_name,
                'user_id': user.id,
                'group_name': chat.title,
                'group_id': chat.id,
                'violation_type': violation_type,
                'original_content': original_content,
                'case_name': case_name
            }
            add_violation(**log_data)
            await send_case_log_to_channel(client, log_data)

            warning_text = (
                f"⚠️ **आपत्तिजनक सामग्री का पता चला** ⚠️\n\n"
                f"[{user.first_name}](tg://user?id={user.id}) ने नियमों का उल्लंघन किया है।\n"
                f"यह संदेश स्वचालित रूप से हटा दिया गया है।"
            )

            keyboard = []
            if violation_type == "बायो_लिंक_उल्लंघन":
                 keyboard = [
                    [InlineKeyboardButton("👤 यूज़र प्रोफ़ाइल देखें", url=f"tg://user?id={user.id}")],
                    [InlineKeyboardButton("⚙️ अनुमति प्रबंधित करें", callback_data=f"manage_permission_{user.id}_{chat.id}")],
                    [InlineKeyboardButton("📋 केस देखें", url=f"https://t.me/c/{str(CASE_LOG_CHANNEL_ID)[4:]}")]
                ]
            else: # अन्य सभी प्रकार के उल्लंघन
                keyboard = [
                    [InlineKeyboardButton("👤 यूज़र प्रोफ़ाइल देखें", url=f"tg://user?id={user.id}")],
                    [InlineKeyboardButton("🔨 कार्रवाई करें", callback_data=f"take_action_{user.id}_{chat.id}")],
                    [InlineKeyboardButton("📋 केस देखें", url=f"https://t.me/c/{str(CASE_LOG_CHANNEL_ID)[4:]}")]
                ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await client.send_message(
                chat_id=chat.id,
                text=warning_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Error handling violation for {user.id} in {chat.id}: {e}")


# --- नए मेंबर/ग्रुप इवेंट्स हैंडलर ---
@app.on_message(filters.new_chat_members | filters.left_chat_member & filters.group)
async def handle_new_chat_members(client: Client, message: Message):
    group_settings = get_group_settings(message.chat.id)
    if not group_settings or not group_settings.get('bot_enabled', True):
        return # यदि बॉट अक्षम है, तो नए सदस्य पर कार्रवाई न करें

    # बॉट को खुद जोड़े जाने पर लॉग
    if message.new_chat_members and client.me.id in [member.id for member in message.new_chat_members]:
        inviter_info = None
        if message.from_user: # बॉट को जोड़ने वाला यूज़र
            inviter_info = {"id": message.from_user.id, "username": message.from_user.username or message.from_user.first_name}
        
        add_or_update_group(message.chat.id, message.chat.title, inviter_info['id'] if inviter_info else None)
        await log_new_user_or_group(
            "new_group", message.chat.id, message.chat.title, inviter_info['id'] if inviter_info else None, inviter_info['username'] if inviter_info else None
        )
        await send_new_entry_log_to_channel(
            client, "new_group", message.chat.id, message.chat.title, inviter_info
        )
        

    # नए यूज़र जुड़ने पर लॉग और वेलकम मैसेज
    if message.new_chat_members:
        for member in message.new_chat_members:
            if member.is_bot and member.id != client.me.id:
                # यदि कोई और बॉट जुड़ता है, तो उसे किक कर सकते हैं (यदि बॉट के पास परमिशन है)
                try:
                    await client.kick_chat_member(message.chat.id, member.id)
                    await client.send_message(
                        message.chat.id,
                        f"🤖 नया बॉट [{member.first_name}](tg://user?id={member.id}) पाया गया और हटा दिया गया।"
                    )
                except Exception as e:
                    logger.error(f"Error kicking bot {member.id}: {e}")
            elif not member.is_bot: # वास्तविक यूज़र
                add_or_update_user(member.id, member.username, member.first_name, member.last_name, False)
                await log_new_user_or_group(
                    "new_user", member.id, member.first_name, None, None # यूज़र के लिए कोई इनवाइटर नहीं
                )
                await send_new_entry_log_to_channel(
                    client, "new_user", member.id, member.first_name, None,
                    {"id": message.chat.id, "name": message.chat.title}
                )
                # वेलकम मैसेज
                welcome_msg = group_settings.get('welcome_message') or WELCOME_MESSAGE_DEFAULT
                welcome_msg = welcome_msg.format(username=member.first_name, groupname=message.chat.title)
                try:
                    await client.send_message(message.chat.id, welcome_msg)
                except Exception as e:
                    logger.error(f"Error sending welcome message in {message.chat.id}: {e}")

    # मेंबर के ग्रुप छोड़ने पर लॉग (वैकल्पिक)
    if message.left_chat_member:
        member = message.left_chat_member
        if not member.is_bot and member.id != client.me.id: # अपने बॉट के छोड़ने पर लॉग न करें
            await log_new_user_or_group(
                "left_user", member.id, member.first_name, None, None
            )


# --- बॉट मालिक कमांड्स ---
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID) & filters.private)
async def broadcast_command(client: Client, message: Message):
    if not check_cooldown(message.from_user.id, "command"):
        return

    if not message.text or len(message.command) < 2:
        await message.reply_text("कृपया प्रसारण के लिए एक संदेश प्रदान करें।")
        return
    
    message_to_broadcast = message.text.split(None, 1)[1] 
    all_groups = get_all_groups()

    sent_count = 0
    for group in all_groups:
        try:
            # चेक करें कि बॉट उस ग्रुप में अभी भी है या नहीं
            chat_member = await client.get_chat_member(group["id"], client.me.id)
            if chat_member.status != ChatMemberStatus.LEFT:
                await client.send_message(chat_id=group["id"], text=message_to_broadcast)
                sent_count += 1
                await asyncio.sleep(0.1) # Flood control
        except Exception as e:
            logger.error(f"Error broadcasting to group {group['id']}: {e}")
    
    await message.reply_text(f"संदेश {sent_count} ग्रुप्स को सफलतापूर्वक भेजा गया।")

@app.on_message(filters.command("stats") & filters.user(OWNER_ID) & filters.private)
async def stats_command(client: Client, message: Message):
    if not check_cooldown(message.from_user.id, "command"):
        return

    group_count = len(get_all_groups())
    user_count = get_total_users()
    violation_count = get_total_violations()

    stats_message = (
        f"📊 **बॉट आंकड़े** 📊\n\n"
        f"**जुड़े हुए ग्रुप्स:** `{group_count}`\n"
        f"**कुल ट्रैक किए गए यूज़र्स:** `{user_count}`\n"
        f"**कुल उल्लंघन:** `{violation_count}`\n\n"
        f"सोर्स कोड: [GitHub]({REPO_LINK})\n"
        f"अपडेट चैनल: @{UPDATE_CHANNEL_USERNAME}\n"
        f"मालिक: @{ASBHAI_USERNAME}"
    )
    await message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)

# --- Bot start up (main function) ---
async def main():
    logger.info("Starting GroupPoliceBot...")
    await app.start()
    logger.info("GroupPoliceBot started successfully!")

if __name__ == "__main__":
    pass # We will start the bot from server.py now
