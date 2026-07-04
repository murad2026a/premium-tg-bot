from pyodide.http import pyfetch
import json
import asyncio
import time
import urllib.parse

# ================= কনফিগারেশন =================
BOT_TOKEN = "8631547598:AAEtZkJKYxN6JOp-qWG8TM99QSelezHeV-4"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
ADMIN_ID = 5578674054
BOT_USERNAME = "BdView2026te_bot" 

# 🟢 আপনার ব্লগস্পট অ্যাড শো করার লিংক
WEB_APP_URL = "https://bjkbnbb577787787.blogspot.com/?m=1"

# ================= ফায়ারবেস কনফিগারেশন =================
FIREBASE_DB_URL = "https://earning-36434-default-rtdb.firebaseio.com"

users_db = set() 
videos_db = []   
admin_states = {} 

# ================= ফায়ারবেস API ফাংশনস =================
async def firebase_get_users():
    url = f"{FIREBASE_DB_URL}/users.json"
    try:
        response = await pyfetch(url, method="GET")
        if response.status == 200:
            data = await response.json()
            if not data:
                return set()
            if isinstance(data, dict):
                return set(int(k) for k in data.keys() if k.isdigit())
            elif isinstance(data, list):
                return set(int(v) for v in data if v is not None)
    except Exception as e:
        print(f"⚠️ [Firebase Load Users Error]: {e}")
    return set()

async def firebase_save_user(chat_id):
    url = f"{FIREBASE_DB_URL}/users/{chat_id}.json"
    try:
        await pyfetch(url, method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(True))
    except Exception as e:
        print(f"⚠️ [Firebase Save User Error]: {e}")

async def firebase_get_videos():
    url = f"{FIREBASE_DB_URL}/videos.json"
    try:
        response = await pyfetch(url, method="GET")
        if response.status == 200:
            data = await response.json()
            if not data:
                return []
            if isinstance(data, dict):
                return list(data.values())
            elif isinstance(data, list):
                return [v for v in data if v is not None]
    except Exception as e:
        print(f"⚠️ [Firebase Load Videos Error]: {e}")
    return []

async def firebase_save_video(video):
    url = f"{FIREBASE_DB_URL}/videos/{video['id']}.json"
    try:
        await pyfetch(url, method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(video))
    except Exception as e:
        print(f"⚠️ [Firebase Save Video Error]: {e}")

async def firebase_delete_video(video_id):
    url = f"{FIREBASE_DB_URL}/videos/{video_id}.json"
    try:
        await pyfetch(url, method="DELETE")
    except Exception as e:
        print(f"⚠️ [Firebase Delete Video Error]: {e}")

# ================= TELEGRAM API ফাংশন =================
async def telegram_api_call(method, payload=None):
    url = BASE_URL + method
    headers = {"Content-Type": "application/json"}
    try:
        if payload:
            response = await pyfetch(url, method="POST", headers=headers, body=json.dumps(payload))
        else:
            response = await pyfetch(url, method="GET")
        
        res_json = await response.json()
        if response.status == 200:
            return res_json
        else:
            print(f"❌ [Telegram API Error ({method})]: {res_json.get('description', 'Unknown Error')}")
    except Exception as e:
        print(f"⚠️ [Network Error ({method})]: {e}")
    return None

# ================= হেল্পার ফাংশনস =================
def get_admin_keyboard():
    return {
        "keyboard": [[{"text": "📤 POST Video"}]],
        "resize_keyboard": True,
        "is_persistent": True
    }

async def broadcast_to_users(video_info):
    print(f"📢 ব্রডকাস্ট শুরু হচ্ছে... টার্গেট ইউজার: {len(users_db)} জন।")
    for user_id in list(users_db):
        if int(user_id) != int(ADMIN_ID):
            asyncio.create_task(send_video_post(user_id, video_info, is_admin=False))

async def send_video_post(chat_id, video, is_admin=False):
    if not video or not isinstance(video, dict):
        return
        
    vid_id = video.get('id', '')
    title = video.get('title', 'No Title')
    desc = video.get('desc', 'No Description')
    thumb_id = video.get('thumb_id', '')
    video_file_id = video.get('video_id', '')
    likes = video.get('likes', 0)

    if not thumb_id:
        return

    caption = f"🎬 <b>{title}</b>\n\n📄 {desc}"
    
    if is_admin:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🗑️ Delete Video", "callback_data": f"del_{vid_id}"},
                    {"text": f"👍 {likes}", "callback_data": f"like_{vid_id}"}
                ]
            ]
        }
    else:
        url_separator = "&" if "?" in WEB_APP_URL else "?"
        final_web_url = f"{WEB_APP_URL}{url_separator}chat_id={chat_id}&file_id={video_file_id}"

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🔓 Unlock Video 🔓", "web_app": {"url": final_web_url}},
                    {"text": f"👍 {likes}", "callback_data": f"like_{vid_id}"}
                ]
            ]
        }

    res = await telegram_api_call("sendPhoto", {
        "chat_id": chat_id,
        "photo": thumb_id,
        "caption": caption,
        "parse_mode": "HTML",
        "reply_markup": keyboard
    })
    
    if res and res.get("ok"):
        msg_id = res["result"]["message_id"]
        url = f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{video_file_id}.json"
        await pyfetch(url, method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(msg_id))

# ================= অটো-ডেলিভারি এবং টাইমার ফাংশনস =================
async def check_ad_unlock_requests():
    """অ্যাড দেখার পর ভিডিও আনলক করার প্রক্রিয়া"""
    while True:
        try:
            url = f"{FIREBASE_DB_URL}/unlock_requests.json"
            response = await pyfetch(url, method="GET")
            if response.status == 200:
                requests = await response.json()
                if requests and isinstance(requests, dict):
                    for req_id, req_data in requests.items():
                        chat_id = req_data.get("chat_id")
                        file_id = req_data.get("file_id")
                        
                        if chat_id and file_id:
                            print(f"🚀 Unlocking Video -> User: {chat_id}, File: {file_id}")
                            
                            track_url = f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{file_id}.json"
                            track_resp = await pyfetch(track_url, method="GET")
                            
                            video_item = next((v for v in videos_db if v["video_id"] == file_id), None)
                            v_id = video_item["id"] if video_item else str(int(time.time()))
                            title = video_item["title"] if video_item else "Premium Video"
                            desc = video_item["desc"] if video_item else ""
                            likes = video_item["likes"] if video_item else 0
                            
                            share_text = urllib.parse.quote(f"🔥 চমৎকার এই ভিডিওটি দেখুন সম্পূর্ণ ফ্রিতে! 👇\n\nt.me/{BOT_USERNAME}?start=video_{v_id}")
                            share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text={share_text}"
                            
                            unlocked_keyboard = {
                                "inline_keyboard": [
                                    [
                                        {"text": f"👍 {likes}", "callback_data": f"like_{v_id}"},
                                        {"text": "📢 Share Video", "url": share_url}
                                    ]
                                ]
                            }
                            
                            caption_text = f"🎬 <b>{title}</b>\n\n📄 {desc}\n\n🎉 <i>ভিডিওটি আনলক করা হয়েছে (১৫ মিনিট পর পুনরায় লক হয়ে যাবে)।</i>"

                            if track_resp.status == 200 and track_resp.text:
                                msg_id = await track_resp.json()
                                if msg_id:
                                    # থাম্বনেইল পরিবর্তন করে ভিডিও বসানো হচ্ছে
                                    await telegram_api_call("editMessageMedia", {
                                        "chat_id": chat_id,
                                        "message_id": int(msg_id),
                                        "media": {
                                            "type": "video",
                                            "media": file_id,
                                            "caption": caption_text,
                                            "parse_mode": "HTML"
                                        },
                                        "reply_markup": unlocked_keyboard
                                    })
                                    
                                    # 🟢 ১৫ মিনিটের টাইমারের জন্য রেকর্ড ফায়ারবেসে সেভ করা হচ্ছে
                                    unlock_record = {
                                        "chat_id": chat_id,
                                        "message_id": int(msg_id),
                                        "file_id": file_id,
                                        "unlock_time": time.time()
                                    }
                                    await pyfetch(f"{FIREBASE_DB_URL}/active_unlocks/{chat_id}_{file_id}.json", method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(unlock_record))
                                    
                                    # পুরনো ট্র্যাক মুছে ফেলা
                                    await pyfetch(track_url, method="DELETE")
                                    await pyfetch(f"{FIREBASE_DB_URL}/unlock_requests/{req_id}.json", method="DELETE")
                                    continue
                            
                            # প্রসেসড রিকোয়েস্টটি ফায়ারবেস থেকে ডিলিট
                            await pyfetch(f"{FIREBASE_DB_URL}/unlock_requests/{req_id}.json", method="DELETE")
        except Exception as e:
            pass
        await asyncio.sleep(2)

async def check_expired_unlocks():
    """১৫ মিনিট (৯০০ সেকেন্ড) পর ভিডিও পুনরায় লক করার প্রক্রিয়া"""
    while True:
        try:
            url = f"{FIREBASE_DB_URL}/active_unlocks.json"
            response = await pyfetch(url, method="GET")
            if response.status == 200:
                unlocks = await response.json()
                if unlocks and isinstance(unlocks, dict):
                    current_time = time.time()
                    for key, record in unlocks.items():
                        chat_id = record.get("chat_id")
                        msg_id = record.get("message_id")
                        file_id = record.get("file_id")
                        unlock_time = record.get("unlock_time", 0)
                        
                        # 🟢 ৯০০ সেকেন্ড = ১৫ মিনিট
                        if current_time - unlock_time >= 900:
                            print(f"🔒 Relocking Video -> User: {chat_id}, File: {file_id}")
                            
                            video = next((v for v in videos_db if v["video_id"] == file_id), None)
                            if video:
                                v_id = video["id"]
                                title = video.get("title", "Premium Video")
                                desc = video.get("desc", "")
                                thumb_id = video.get("thumb_id", "")
                                likes = video.get("likes", 0)
                                
                                caption = f"🎬 <b>{title}</b>\n\n📄 {desc}\n\n🔒 <i>সময় শেষ! ভিডিওটি পুনরায় লক হয়ে গেছে। আবার দেখতে আনলক করুন।</i>"
                                
                                url_separator = "&" if "?" in WEB_APP_URL else "?"
                                final_web_url = f"{WEB_APP_URL}{url_separator}chat_id={chat_id}&file_id={file_id}"
                                
                                locked_keyboard = {
                                    "inline_keyboard": [
                                        [
                                            {"text": "🔓 Unlock Video 🔓", "web_app": {"url": final_web_url}},
                                            {"text": f"👍 {likes}", "callback_data": f"like_{v_id}"}
                                        ]
                                    ]
                                }
                                
                                # ভিডিওটিকে পরিবর্তন করে পুনরায় থাম্বনেইল ফটো বসানো হচ্ছে
                                await telegram_api_call("editMessageMedia", {
                                    "chat_id": chat_id,
                                    "message_id": int(msg_id),
                                    "media": {
                                        "type": "photo",
                                        "media": thumb_id,
                                        "caption": caption,
                                        "parse_mode": "HTML"
                                    },
                                    "reply_markup": locked_keyboard
                                })
                                
                                # আবার আনলক করার জন্য ট্র্যাক হিস্টোরি রিস্টোর করা হচ্ছে
                                track_url = f"{FIREBASE_DB_URL}/msg_tracks/{chat_id}_{file_id}.json"
                                await pyfetch(track_url, method="PUT", headers={"Content-Type": "application/json"}, body=json.dumps(msg_id))
                            
                            # ১৫ মিনিট পার হয়ে যাওয়ার পর টাইমার লিস্ট থেকে মুছে ফেলা
                            await pyfetch(f"{FIREBASE_DB_URL}/active_unlocks/{key}.json", method="DELETE")
        except Exception as e:
            pass
        await asyncio.sleep(5)

# ================= মূল আপডেট হ্যান্ডলার =================
async def process_message(msg):
    global videos_db
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    
    if chat_id not in users_db:
        users_db.add(chat_id)
        asyncio.create_task(firebase_save_user(chat_id))

    if text.startswith("/start"):
        if chat_id == ADMIN_ID:
            await telegram_api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "👨‍💻 <b>স্বাগতম অ্যাডমিন!</b>\nনিচের <b>POST Video</b> বাটনে ক্লিক করে নতুন ভিডিও আপলোড করুন।",
                "parse_mode": "HTML",
                "reply_markup": get_admin_keyboard()
            })
        else:
            await telegram_api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "🌟 <b>স্বাগতম!</b>\nএখানে আমাদের সব প্রিমিয়াম ভিডিও দেওয়া আছে।",
                "parse_mode": "HTML",
                "reply_markup": {"remove_keyboard": True}
            })
            
            if "_" in text:
                target_id = text.split("_")[1]
                specific_video = next((v for v in videos_db if v["id"] == target_id), None)
                if specific_video:
                    await send_video_post(chat_id, specific_video, is_admin=False)
                    return
            
            if not videos_db:
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "এখনো কোনো ভিডিও আপলোড করা হয়নি।"})
            else:
                for video in videos_db:
                    await send_video_post(chat_id, video, is_admin=False)
        return

    if chat_id == ADMIN_ID:
        if text in ["📤 POST Video", "POST Video"]:
            admin_states[chat_id] = {"step": "title"}
            await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "📝 <b>ধাপ ১:</b> ভিডিওর Title (নাম) দিন:", "parse_mode": "HTML"})
            return
            
        state = admin_states.get(chat_id)
        if state:
            if state["step"] == "title" and text:
                state["title"] = text
                state["step"] = "desc"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "📄 <b>ধাপ ২:</b> ভিডিওর Description (বর্ণনা) দিন:", "parse_mode": "HTML"})
            
            elif state["step"] == "desc" and text:
                state["desc"] = text
                state["step"] = "thumb"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🖼️ <b>ধাপ ৩:</b> ভিডিওর Thumbnail (ছবি) পাঠান:", "parse_mode": "HTML"})
            
            elif state["step"] == "thumb" and "photo" in msg:
                photo_id = msg["photo"][-1]["file_id"]
                state["thumb_id"] = photo_id
                state["step"] = "video"
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "🎥 <b>ধাপ ৪:</b> এবার মূল Video টি পাঠান:", "parse_mode": "HTML"})
            
            elif state["step"] == "video" and "video" in msg:
                video_id = msg["video"]["file_id"]
                video_uid = str(int(time.time() * 1000))
                
                new_video = {
                    "id": video_uid, 
                    "title": state["title"],
                    "desc": state["desc"],
                    "thumb_id": state["thumb_id"],
                    "video_id": video_id,
                    "likes": 0,
                    "liked_by": []
                }
                
                videos_db.append(new_video)
                asyncio.create_task(firebase_save_video(new_video))
                
                if chat_id in admin_states:
                    del admin_states[chat_id] 
                
                await telegram_api_call("sendMessage", {"chat_id": chat_id, "text": "✅ <b>ভিডিও সফলভাবে আপলোড ও ডেটাবেসে সেভ হয়েছে!</b>", "parse_mode": "HTML"})
                await send_video_post(chat_id, new_video, is_admin=True)
                await broadcast_to_users(new_video)

# ================= কলব্যাক হ্যান্ডলার =================
async def process_callback(cq):
    global videos_db 
    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    data = cq["data"]
    callback_id = cq["id"]
    
    if data.startswith("like_"):
        vid_id = data.split("_")[1]
        video = next((v for v in videos_db if v["id"] == vid_id), None)
        if video:
            liked_by = video.get('liked_by', [])
            if not isinstance(liked_by, list):
                liked_by = []
            
            if chat_id != ADMIN_ID and chat_id in liked_by:
                await telegram_api_call("answerCallbackQuery", {
                    "callback_query_id": callback_id, 
                    "text": "❌ আপনি ইতিমধ্যে এই ভিডিওটি লাইক করেছেন!",
                    "show_alert": True
                })
                return
            
            video['likes'] = video.get('likes', 0) + 1
            if chat_id != ADMIN_ID:
                liked_by.append(chat_id)
            video['liked_by'] = liked_by
            
            asyncio.create_task(firebase_save_video(video))
            await telegram_api_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "❤️ আপনি ভিডিওটি লাইক করেছেন!"})
            
            current_keyboard = cq["message"]["reply_markup"]
            for row in current_keyboard["inline_keyboard"]:
                for btn in row:
                    if btn.get("callback_data") == data:
                        btn["text"] = f"👍 {video['likes']}"
            
            await telegram_api_call("editMessageReplyMarkup", {
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": current_keyboard
            })

    elif data.startswith("del_") and chat_id == ADMIN_ID:
        vid_id = data.split("_")[1]
        videos_db = [v for v in videos_db if v["id"] != vid_id]
        asyncio.create_task(firebase_delete_video(vid_id))
        
        await telegram_api_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "✅ ভিডিও ডিলেট করা হয়েছে!"})
        await telegram_api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

# ================= মূল বট লুপ =================
async def start_bot():
    global users_db, videos_db
    print("✨ ব্রাউজারে টেলিগ্রাম বট সফলভাবে চালু হয়েছে...")
    
    users_db = await firebase_get_users()
    raw_vids = await firebase_get_videos()
    videos_db = [v for v in raw_vids if isinstance(v, dict) and 'id' in v]
    
    # 🟢 ব্যাকগ্রাউন্ডে আনলক এবং রিলক মনিটরিং টাস্কগুলো শুরু করা হলো
    asyncio.create_task(check_ad_unlock_requests())
    asyncio.create_task(check_expired_unlocks())
    
    offset = 0
    await telegram_api_call("getUpdates", {"offset": -1})
    
    while True:
        updates = await telegram_api_call("getUpdates", {"offset": offset, "timeout": 2})
        if updates and updates.get("ok") and updates.get("result"):
            for update in updates["result"]:
                offset = update["update_id"] + 1
                try:
                    if "message" in update:
                        await process_message(update["message"])
                    elif "callback_query" in update:
                        await process_callback(update["callback_query"])
                except Exception as e:
                    print(f"Error Processing Update: {e}")
        await asyncio.sleep(1)

await start_bot()
