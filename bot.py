import asyncio
import json
import random
import string
import re
import os
import aiohttp
from aiohttp import web

# ⚠️ আপনার বট টোকেন (Render Environment Variable থেকে নিবে, না থাকলে ডিফল্ট টোকেন ব্যবহার করবে)
TOKEN = os.environ.get("BOT_TOKEN", "8633261962:AAGKeQhtSoIApD283SpLf8B1xoD_BJoGefw")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

# Mail.tm API Base URL
MAIL_API = "https://api.mail.tm"

# ইউজারদের ডেটা সংরক্ষণের জন্য ডিকশনারি 
users_db = {}
offset = 0

# ==========================================
# 🌐 API Helper Function (pyfetch এর বিকল্প)
# ==========================================
async def make_request(url, method="GET", headers=None, payload=None):
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as response:
                return await response.json() if response.status != 204 else None
        elif method == "POST":
            async with session.post(url, headers=headers, json=payload) as response:
                return await response.json() if response.status != 204 else None
        elif method == "DELETE":
            async with session.delete(url, headers=headers) as response:
                return await response.text() if response.status != 204 else None

# সুন্দর কি-বোর্ড ডিজাইন
def get_reply_keyboard():
    return {
        "keyboard": [
            [{"text": "✨ Generate New Mail"}, {"text": "📥 Inbox"}],
            [{"text": "👤 Profile"}, {"text": "🗑️ Delete Mail"}]
        ],
        "resize_keyboard": True, 
        "is_persistent": True
    }

# মেসেজ পাঠানোর ফাংশন
async def send_message(chat_id, text, reply_markup=None):
    url = BASE_URL + "sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    return await make_request(url, method="POST", payload=payload)

# মেসেজ এডিট করার ফাংশন
async def edit_message_text(chat_id, message_id, text, reply_markup=None):
    url = BASE_URL + "editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    await make_request(url, method="POST", payload=payload)

# ব্যাকগ্রাউন্ডে লোডিং অ্যানিমেশন চালানোর ফাংশন
async def loading_animation(chat_id, message_id):
    loading_text = "⏳ <i>নতুন ইমেইল তৈরি করা হচ্ছে...</i>\n\n"
    frames = [
        f"{loading_text}[🟥 ⬜ ⬜ ⬜ ⬜]",
        f"{loading_text}[🟥 🟧 ⬜ ⬜ ⬜]",
        f"{loading_text}[🟥 🟧 🟨 ⬜ ⬜]",
        f"{loading_text}[🟥 🟧 🟨 🟩 ⬜]",
        f"{loading_text}[🟥 🟧 🟨 🟩 🟦]"
    ]
    idx = 0
    while True:
        try:
            await edit_message_text(chat_id, message_id, frames[idx % len(frames)])
            idx += 1
            # টেলিগ্রামের রেট লিমিট এড়াতে ১.২ সেকেন্ড দেওয়া হলো
            await asyncio.sleep(1.2) 
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(1.2)

# ==========================================
# ✉️ Mail.tm API Helpers 
# ==========================================
async def get_domain():
    data = await make_request(f"{MAIL_API}/domains", method="GET")
    return data["hydra:member"][0]["domain"]

async def create_account():
    domain = await get_domain()
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    email = f"{username}@{domain}"
    
    payload = {"address": email, "password": password}
    
    acc_data = await make_request(f"{MAIL_API}/accounts", method="POST", payload=payload)
    account_id = acc_data["id"]
    
    auth_data = await make_request(f"{MAIL_API}/token", method="POST", payload=payload)
    token = auth_data["token"]
    
    return account_id, email, token

async def fetch_inbox(token):
    headers = {"Authorization": f"Bearer {token}"}
    data = await make_request(f"{MAIL_API}/messages", method="GET", headers=headers)
    return data.get("hydra:member", [])

async def read_message(msg_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    return await make_request(f"{MAIL_API}/messages/{msg_id}", method="GET", headers=headers)

async def delete_account_api(account_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    await make_request(f"{MAIL_API}/accounts/{account_id}", method="DELETE", headers=headers)

# ==========================================
# 🤖 Telegram Bot Handlers
# ==========================================
async def handle_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    user_name = message["from"].get("first_name", "User")
    user_id = message["from"]["id"]
    
    if user_id not in users_db:
        users_db[user_id] = {"name": user_name, "id": None, "email": None, "token": None}
    
    if text == "/start":
        welcome_text = (
            f"✨ <b>স্বাগতম {user_name}!</b> ✨\n\n"
            "🛡️ এটি একটি প্রিমিয়াম <b>Temp Mail Bot</b>।\n"
            "এখানে আপনি আনলিমিটেড টেম্পোরারি ইমেইল তৈরি করতে পারবেন।\n\n"
            "👇 <b>নিচের মেনু থেকে অপশন বেছে নিন:</b>"
        )
        await send_message(chat_id, welcome_text, get_reply_keyboard())
        
    elif text == "✨ Generate New Mail":
        msg_res = await send_message(chat_id, "⏳ <i>নতুন ইমেইল তৈরি করা হচ্ছে...</i>\n\n[⬜ ⬜ ⬜ ⬜ ⬜]")
        msg_id = None
        anim_task = None
        
        if msg_res and msg_res.get("ok"):
            msg_id = msg_res["result"]["message_id"]
            anim_task = asyncio.create_task(loading_animation(chat_id, msg_id))
            
        try:
            old_data = users_db.get(user_id)
            if old_data and old_data.get("id"):
                try:
                    await delete_account_api(old_data["id"], old_data["token"])
                except:
                    pass

            account_id, email, token = await create_account()
            
            users_db[user_id]["id"] = account_id
            users_db[user_id]["email"] = email
            users_db[user_id]["token"] = token
            
            mail_text = (
                "🎉 <b>সফলভাবে ইমেইল তৈরি হয়েছে!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"📧 <b>ইমেইল:</b> <code>{email}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💡 <i>(কপি করতে ইমেইলের উপর ক্লিক করুন)</i>"
            )
            
            if anim_task:
                anim_task.cancel()
                
            if msg_id:
                await edit_message_text(chat_id, msg_id, mail_text)
            else:
                await send_message(chat_id, mail_text)
                
        except Exception as e:
            if anim_task:
                anim_task.cancel()
            error_text = "⚠️ <b>দুঃখিত!</b> ইমেইল তৈরি করতে সমস্যা হচ্ছে। কিছুক্ষণ পর আবার চেষ্টা করুন।"
            if msg_id:
                await edit_message_text(chat_id, msg_id, error_text)
            else:
                await send_message(chat_id, error_text)
            
    elif text == "📥 Inbox":
        user_data = users_db.get(user_id)
        if not user_data or not user_data.get("token"):
            await send_message(chat_id, "⚠️ <b>আপনার কোনো ইমেইল নেই!</b>\nআগে '✨ Generate New Mail' এ ক্লিক করুন।")
            return
            
        await send_message(chat_id, "🔄 <i>ইনবক্স চেক করা হচ্ছে...</i>")
        try:
            messages = await fetch_inbox(user_data["token"])
            if not messages:
                await send_message(chat_id, "📭 <b>আপনার ইনবক্স ফাঁকা।</b>\nএখনো কোনো নতুন মেইল আসেনি।")
            else:
                latest_msg_id = messages[0]['id']
                msg_details = await read_message(latest_msg_id, user_data["token"])
                
                sender = msg_details.get('from', {}).get('address', 'Unknown')
                subject = msg_details.get('subject', 'No Subject')
                body = msg_details.get('text', 'No Content available in text format.')
                date = msg_details.get('createdAt', '')[:19].replace("T", " ")
                
                code_match = re.search(r'\b\d{4,8}\b', subject)
                if not code_match:
                    code_match = re.search(r'\b\d{4,8}\b', body)
                
                reply_markup = None
                if code_match:
                    extracted_code = code_match.group(0)
                    reply_markup = {
                        "inline_keyboard": [
                            [{"text": f"📋 Copy Code: {extracted_code}", "copy_text": {"text": extracted_code}}]
                        ]
                    }

                if len(body) > 1000:
                    body = body[:1000] + "\n\n... [Message Truncated] ..."
                
                reply_text = (
                    "📬 <b>নতুন ইমেইল পাওয়া গেছে!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>From:</b> <code>{sender}</code>\n"
                    f"🏷 <b>Subject:</b> <b>{subject}</b>\n"
                    f"🕒 <b>Date:</b> {date}\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📝 <b>Message:</b>\n<pre>{body}</pre>"
                )
                await send_message(chat_id, reply_text, reply_markup)
                
        except Exception as e:
            await send_message(chat_id, "⚠️ <b>দুঃখিত!</b> সার্ভার ইনবক্স ফেচ করতে ব্যর্থ হয়েছে।")
            
    elif text == "👤 Profile":
        user_email = users_db[user_id].get("email")
        if user_email:
            profile_text = (
                "👤 <b>আপনার প্রোফাইল:</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 <b>নাম:</b> {user_name}\n"
                f"🔹 <b>বর্তমান ইমেইল:</b> <code>{user_email}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
        else:
            profile_text = (
                "👤 <b>আপনার প্রোফাইল:</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 <b>নাম:</b> {user_name}\n"
                "🔹 <b>বর্তমান ইমেইল:</b> ❌ <i>নাই</i>\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
        await send_message(chat_id, profile_text)
        
    elif text == "🗑️ Delete Mail":
        user_data = users_db.get(user_id)
        if user_data and user_data.get("id"):
            try:
                await delete_account_api(user_data["id"], user_data["token"])
            except Exception as e:
                pass
            
            users_db[user_id]["id"] = None
            users_db[user_id]["email"] = None
            users_db[user_id]["token"] = None
            
            await send_message(chat_id, "🗑️ <b>আপনার বর্তমান ইমেইল সার্ভার থেকে সফলভাবে ডিলিট করা হয়েছে!</b>\nনতুন ইমেইল নিতে '✨ Generate New Mail' এ ক্লিক করুন।")
        else:
            await send_message(chat_id, "⚠️ আপনার কোনো অ্যাক্টিভ ইমেইল নেই যা ডিলিট করা যাবে।")
            
    else:
        await send_message(chat_id, "দয়া করে নিচের মেনু থেকে সঠিক একটি অপশন বেছে নিন।", get_reply_keyboard())


# ==========================================
# 🔄 Update Polling
# ==========================================
async def poll_updates():
    global offset
    print("Bot is polling for updates...")
    while True:
        try:
            url = BASE_URL + f"getUpdates?offset={offset}&timeout=10"
            data = await make_request(url, method="GET")
            
            if data and data.get("ok"):
                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    if "message" in result:
                        await handle_message(result["message"])
        except Exception as e:
            pass 
        await asyncio.sleep(1)


# ==========================================
# 🌍 Dummy Web Server (For Render)
# ==========================================
async def handle_request(request):
    return web.Response(text="Bot is running and healthy!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_request)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render সাধারণত $PORT এনভায়রনমেন্ট ভ্যারিয়েবল প্রোভাইড করে
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")


# মূল রান ফাংশন
async def main():
    # ওয়েব সার্ভার এবং বট পোলিং একসাথে রান করানো হচ্ছে
    await asyncio.gather(
        start_web_server(),
        poll_updates()
    )

if __name__ == "__main__":
    asyncio.run(main())
