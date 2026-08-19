import telebot
import requests
import sqlite3
import json
import os
import time
import re
from datetime import datetime
import threading

# ==================== الإعدادات ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', "7999963241:AAHN-AoxKf1MKTnF-fPMWcMZzbhOr-vwa0k")
ADMIN_ID = int(os.environ.get('ADMIN_ID', 7947679527))
SITE_URL = os.environ.get('SITE_URL', 'https://Hosted_by_Kayo-Bots.railway.app')
DB_PATH = 'hosting.db'

bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

# ==================== دوال قاعدة البيانات ====================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_bots():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM bots ORDER BY created_at DESC')
    bots = c.fetchall()
    conn.close()
    return bots

def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

# ==================== دوال API ====================
def api_request(method, endpoint, data=None):
    try:
        url = f"{SITE_URL}/api/{endpoint}"
        if method == 'GET':
            response = requests.get(url, timeout=10)
        else:
            response = requests.post(url, json=data or {}, timeout=10)
        return response.json() if response.ok else {'error': 'API Error'}
    except:
        return {'error': 'Connection failed'}

def start_bot_api(bot_id):
    return api_request('POST', f'start_bot/{bot_id}')

def stop_bot_api(bot_id):
    return api_request('POST', f'stop_bot/{bot_id}')

# ==================== أزرار البوت ====================
def main_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        telebot.types.InlineKeyboardButton("📊 البوتات", callback_data="list_bots"),
        telebot.types.InlineKeyboardButton("📤 رفع بوت", callback_data="upload_bot")
    )
    keyboard.add(
        telebot.types.InlineKeyboardButton("💰 الاشتراكات", callback_data="subscriptions"),
        telebot.types.InlineKeyboardButton("🔄 تحديث", callback_data="refresh")
    )
    keyboard.add(
        telebot.types.InlineKeyboardButton("👑 المطور", url="https://t.me/ggzh9"),
        telebot.types.InlineKeyboardButton("📢 القناة", url="https://t.me/kayo_i")
    )
    return keyboard

def bot_control_keyboard(bot_id, status):
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    if status == 'running':
        keyboard.add(telebot.types.InlineKeyboardButton("⏹ إيقاف", callback_data=f"stop_{bot_id}"))
    else:
        keyboard.add(telebot.types.InlineKeyboardButton("▶️ تشغيل", callback_data=f"start_{bot_id}"))
    keyboard.add(
        telebot.types.InlineKeyboardButton("📋 معلومات", callback_data=f"info_{bot_id}"),
        telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="list_bots")
    )
    return keyboard

# ==================== أوامر البوت ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    welcome = f"""
🌟 اهلاً بك في بوت استضافة البوتات

━━━━━━━━━━━━━━━━━━
👤 الاسم: {user_name}
🆔 ايديك: {user_id}
━━━━━━━━━━━━━━━━━━

📌 يمكنك من خلال هذا البوت:
• 📊 عرض البوتات المرفوعة
• 📤 رفع بوتات جديدة
• 💰 إدارة الاشتراكات
• 🔄 تحديث البوتات

🔗 الموقع: {SITE_URL}

👑 المطور: @ggzh9
📢 القناة: https://t.me/kayo_i
"""
    bot.send_message(user_id, welcome, reply_markup=main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    # قائمة البوتات
    if call.data == "list_bots":
        bots = get_all_bots()
        if not bots:
            bot.edit_message_text("📭 لا توجد بوتات", call.message.chat.id, call.message.message_id, reply_markup=main_keyboard())
            bot.answer_callback_query(call.id)
            return
        
        text = "🤖 <b>قائمة البوتات:</b>\n\n"
        for b in bots[:15]:
            status_emoji = "🟢" if b['status'] == 'running' else "🔴"
            text += f"{status_emoji} <b>{b['bot_name']}</b>\n"
            text += f"🆔 ID: {b['id']}\n"
            text += f"📅 {b['created_at'][:10] if b['created_at'] else ''}\n"
            text += f"📊 {b['status']}\n\n"
        
        if len(bots) > 15:
            text += f"\n... وعرض {len(bots) - 15} بوتات أخرى"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=main_keyboard())
        bot.answer_callback_query(call.id)
        return
    
    # معلومات بوت
    if call.data.startswith("info_"):
        bot_id = int(call.data.split("_")[1])
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM bots WHERE id = ?', (bot_id,))
        b = c.fetchone()
        conn.close()
        
        if not b:
            bot.answer_callback_query(call.id, "❌ البوت غير موجود", show_alert=True)
            return
        
        text = f"""
📋 <b>معلومات البوت</b>

━━━━━━━━━━━━━━━━━━
🆔 المعرف: {b['id']}
📝 الاسم: {b['bot_name']}
📊 الحالة: {b['status']}
📅 التاريخ: {b['created_at'][:10] if b['created_at'] else ''}
👤 المالك: {b['user_id']}
━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=bot_control_keyboard(bot_id, b['status']))
        bot.answer_callback_query(call.id)
        return
    
    # تشغيل بوت
    if call.data.startswith("start_"):
        bot_id = int(call.data.split("_")[1])
        result = start_bot_api(bot_id)
        if result and result.get('success'):
            bot.answer_callback_query(call.id, "✅ تم تشغيل البوت", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ فشل تشغيل البوت", show_alert=True)
        handle_callbacks(call)
        return
    
    # إيقاف بوت
    if call.data.startswith("stop_"):
        bot_id = int(call.data.split("_")[1])
        result = stop_bot_api(bot_id)
        if result and result.get('success'):
            bot.answer_callback_query(call.id, "✅ تم إيقاف البوت", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ فشل إيقاف البوت", show_alert=True)
        handle_callbacks(call)
        return
    
    # الاشتراكات
    if call.data == "subscriptions":
        text = """
💰 <b>أسعار الاشتراك</b>

━━━━━━━━━━━━━━━━━━
📅 <b>الباقات:</b>
• 🟢 أسبوع — 3$
• 🔵 شهر — 6$
• 🟣 سنة — 70$
• 💎 دائم — 100$

━━━━━━━━━━━━━━━━━━
📌 <b>للاشتراك:</b>
تواصل مع المطور: @ggzh9

📢 القناة: https://t.me/kayo_i
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=main_keyboard())
        bot.answer_callback_query(call.id)
        return
    
    # تحديث
    if call.data == "refresh":
        bot.answer_callback_query(call.id, "🔄 تم التحديث")
        start_cmd(call.message)
        return
    
    # رفع بوت
    if call.data == "upload_bot":
        bot.edit_message_text(
            "📤 أرسل ملف البوت (bot.py) لرفعه\n\n"
            "📌 سيتم طلب ملف المتطلبات بعد الرفع",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_keyboard()
        )
        bot.register_next_step_handler(call.message, process_bot_file)
        bot.answer_callback_query(call.id)
        return
    
    bot.answer_callback_query(call.id, "⚠️ جاري التطوير...")

# ==================== معالجة ملفات البوت ====================
def process_bot_file(message):
    user_id = message.from_user.id
    
    if not message.document:
        bot.reply_to(message, "❌ يرجى إرسال ملف bot.py", reply_markup=main_keyboard())
        return
    
    if not message.document.file_name.endswith('.py'):
        bot.reply_to(message, "❌ يرجى إرسال ملف Python (.py)", reply_markup=main_keyboard())
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        bot_name = message.document.file_name.replace('.py', '')
        folder_name = f"bot_{int(time.time())}_{user_id}"
        bot_folder = os.path.join('uploaded_bots', folder_name)
        os.makedirs(bot_folder, exist_ok=True)
        
        file_path = os.path.join(bot_folder, 'bot.py')
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)
        
        # استخراج التوكن
        bot_token = extract_token(file_path)
        bot_data = extract_bot_data(file_path)
        
        # حفظ في قاعدة البيانات
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO bots (user_id, bot_name, bot_token, file_path, created_at, bot_data) VALUES (?, ?, ?, ?, ?, ?)',
                  (user_id, bot_name, bot_token or '', file_path, datetime.now().isoformat(), bot_data))
        bot_id = c.lastrowid
        conn.commit()
        conn.close()
        
        bot.reply_to(
            message,
            f"✅ تم استلام ملف البوت: {bot_name}\n"
            f"🆔 المعرف: {bot_id}\n"
            f"📤 أرسل الآن ملف requirements.txt",
            reply_markup=main_keyboard()
        )
        
        bot.register_next_step_handler(message, process_requirements_file, bot_id, bot_folder)
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}", reply_markup=main_keyboard())

def process_requirements_file(message, bot_id, bot_folder):
    user_id = message.from_user.id
    
    if not message.document:
        bot.reply_to(message, "❌ يرجى إرسال ملف requirements.txt", reply_markup=main_keyboard())
        return
    
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ يرجى إرسال ملف requirements.txt", reply_markup=main_keyboard())
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        req_path = os.path.join(bot_folder, 'requirements.txt')
        with open(req_path, 'wb') as f:
            f.write(downloaded_file)
        
        # تحديث قاعدة البيانات
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE bots SET requirements_file = ? WHERE id = ?', (req_path, bot_id))
        conn.commit()
        conn.close()
        
        # تشغيل البوت عبر API
        result = start_bot_api(bot_id)
        
        if result and result.get('success'):
            bot.reply_to(message, "✅ تم تشغيل البوت بنجاح!", reply_markup=main_keyboard())
            bot.send_message(ADMIN_ID, f"🚀 تم تشغيل بوت جديد (ID: {bot_id}) بواسطة المستخدم {user_id}")
        else:
            bot.reply_to(message, "❌ فشل تشغيل البوت، تحقق من الكود", reply_markup=main_keyboard())
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}", reply_markup=main_keyboard())

def extract_token(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            match = re.search(r'[0-9]{9,10}:[A-Za-z0-9_-]+', content)
            if match:
                return match.group(0)
    except:
        pass
    return None

def extract_bot_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            variables = {}
            lines = content.split('\n')
            for line in lines:
                match = re.search(r'([A-Z_]+)\s*=\s*["\']([^"\']+)["\']', line)
                if match:
                    variables[match.group(1)] = match.group(2)
                token_match = re.search(r'[0-9]{9,10}:[A-Za-z0-9_-]+', line)
                if token_match:
                    variables['TOKEN'] = token_match.group(0)
            return json.dumps(variables, ensure_ascii=False)
    except:
        return None

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 جاري تشغيل بوت استضافة البوتات...")
    print(f"🔗 الموقع: {SITE_URL}")
    print("=" * 50)
    bot.infinity_polling()