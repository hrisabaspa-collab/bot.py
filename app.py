import os
import sqlite3
import json
import time
import re
import random
import string
import subprocess
import shutil
import threading
import base64
import hashlib
import requests
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify, send_file
from functools import wraps
import telebot

# ==================== إعدادات التسجيل ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hosting.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== الإعدادات الأساسية ====================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kayo-secret-key-2026')

ADMIN_USERNAME = "kayo"
ADMIN_PASSWORD = "kayo"
BOT_TOKEN = os.environ.get('BOT_TOKEN', "7999963241:AAHN-AoxKf1MKTnF-fPMWcMZzbhOr-vwa0k")
ADMIN_ID = int(os.environ.get('ADMIN_ID', 7947679527))
SITE_URL = os.environ.get('SITE_URL', 'https://Hosted_by_Kayo-Bots.railway.app')
GITHUB_REPO = "https://github.com/yesssssssie-debug/botkayo"

# ==================== إعدادات المسارات ====================
UPLOAD_FOLDER = 'uploaded_bots'
DB_PATH = 'hosting.db'
BACKUP_PATH = 'backups'
DATA_PATH = 'data'
TEMP_PATH = 'temp'

for path in [UPLOAD_FOLDER, BACKUP_PATH, DATA_PATH, TEMP_PATH]:
    os.makedirs(path, exist_ok=True)

# ==================== تهيئة البوت ====================
bot = telebot.TeleBot(BOT_TOKEN)

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT,
        last_login TEXT,
        backup_data TEXT
    )''')
    
    # جدول الاشتراكات
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan TEXT,
        start_date TEXT,
        expiry_date TEXT,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # جدول البوتات
    c.execute('''CREATE TABLE IF NOT EXISTS bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bot_name TEXT,
        bot_token TEXT,
        file_path TEXT,
        status TEXT DEFAULT 'stopped',
        pid INTEGER,
        created_at TEXT,
        expiry_date TEXT,
        bot_data TEXT,
        requirements_file TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # جدول النسخ الاحتياطي
    c.execute('''CREATE TABLE IF NOT EXISTS bot_backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id INTEGER,
        bot_data TEXT,
        backup_date TEXT,
        FOREIGN KEY (bot_id) REFERENCES bots(id)
    )''')
    
    # جدول الإعدادات
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    # إضافة المستخدم المالك
    c.execute('INSERT OR IGNORE INTO users (username, password, is_admin, created_at) VALUES (?, ?, ?, ?)',
              (ADMIN_USERNAME, ADMIN_PASSWORD, 1, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    logger.info("✅ قاعدة البيانات جاهزة")

# ==================== دوال قاعدة البيانات ====================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_username(username):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_subscription(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM subscriptions WHERE user_id = ? AND status = "active" ORDER BY expiry_date DESC LIMIT 1', (user_id,))
    sub = c.fetchone()
    conn.close()
    return sub

def add_subscription(user_id, plan, days):
    conn = get_db()
    c = conn.cursor()
    start = datetime.now().isoformat()
    expiry = (datetime.now() + timedelta(days=days)).isoformat()
    c.execute('INSERT INTO subscriptions (user_id, plan, start_date, expiry_date, status) VALUES (?, ?, ?, ?, ?)',
              (user_id, plan, start, expiry, 'active'))
    conn.commit()
    conn.close()

def get_user_bots(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    bots = c.fetchall()
    conn.close()
    return bots

def get_all_bots():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM bots ORDER BY created_at DESC')
    bots = c.fetchall()
    conn.close()
    return bots

def save_bot(user_id, bot_name, bot_token, file_path, requirements_file=None, bot_data=None):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO bots (user_id, bot_name, bot_token, file_path, created_at, bot_data, requirements_file) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (user_id, bot_name, bot_token, file_path, datetime.now().isoformat(), bot_data, requirements_file))
    bot_id = c.lastrowid
    conn.commit()
    conn.close()
    return bot_id

def update_bot_status(bot_id, status, pid=None):
    conn = get_db()
    c = conn.cursor()
    if pid:
        c.execute('UPDATE bots SET status = ?, pid = ? WHERE id = ?', (status, pid, bot_id))
    else:
        c.execute('UPDATE bots SET status = ? WHERE id = ?', (status, bot_id))
    conn.commit()
    conn.close()

def update_bot_data(bot_id, bot_data):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE bots SET bot_data = ? WHERE id = ?', (bot_data, bot_id))
    conn.commit()
    conn.close()

def save_bot_backup(bot_id, bot_data):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO bot_backups (bot_id, bot_data, backup_date) VALUES (?, ?, ?)',
              (bot_id, bot_data, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_bot_backup(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT bot_data FROM bot_backups WHERE bot_id = ? ORDER BY backup_date DESC LIMIT 1', (bot_id,))
    result = c.fetchone()
    conn.close()
    return result['bot_data'] if result else None

def delete_bot_from_db(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM bots WHERE id = ?', (bot_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = c.fetchall()
    conn.close()
    return users

def get_all_subscriptions():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT s.*, u.username FROM subscriptions s JOIN users u ON s.user_id = u.id ORDER BY s.id DESC')
    subs = c.fetchall()
    conn.close()
    return subs

# ==================== تشغيل البوتات ====================
running_processes = {}

def install_requirements(requirements_file):
    """تثبيت متطلبات البوت"""
    try:
        if not os.path.exists(requirements_file):
            return True
        result = subprocess.run(['pip', 'install', '-r', requirements_file, '--user'], 
                               capture_output=True, text=True)
        logger.info(f"✅ تم تثبيت المتطلبات: {result.stdout[:200]}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تثبيت المتطلبات: {e}")
        return False

def start_bot_process(bot_id, file_path, requirements_file=None, bot_data=None):
    try:
        if not os.path.exists(file_path):
            return False
        
        # تثبيت المتطلبات
        if requirements_file and os.path.exists(requirements_file):
            install_requirements(requirements_file)
        
        # استعادة البيانات
        if bot_data:
            restore_bot_data(bot_id, bot_data)
        
        # تشغيل البوت
        cmd = f"nohup python3 {file_path} > /dev/null 2>&1 &"
        process = subprocess.Popen(cmd, shell=True)
        
        running_processes[bot_id] = process.pid
        update_bot_status(bot_id, 'running', process.pid)
        
        if bot_data:
            save_bot_backup(bot_id, bot_data)
        
        logger.info(f"✅ تم تشغيل البوت {bot_id}")
        return True
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}")
        return False

def stop_bot_process(bot_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT pid, bot_data FROM bots WHERE id = ?', (bot_id,))
        result = c.fetchone()
        conn.close()
        
        if result and result['pid']:
            os.system(f"kill -9 {result['pid']} 2>/dev/null")
        
        if bot_id in running_processes:
            del running_processes[bot_id]
        
        if result and result['bot_data']:
            save_bot_backup(bot_id, result['bot_data'])
        
        update_bot_status(bot_id, 'stopped')
        return True
    except:
        return False

def delete_bot_files(bot_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT file_path FROM bots WHERE id = ?', (bot_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            file_path = result['file_path']
            if os.path.exists(file_path):
                os.remove(file_path)
            folder = os.path.dirname(file_path)
            if os.path.exists(folder) and os.path.isdir(folder):
                shutil.rmtree(folder)
        return True
    except:
        return False

def restore_bot_data(bot_id, bot_data):
    try:
        if not bot_data:
            return False
        temp_file = os.path.join(DATA_PATH, f"bot_{bot_id}_data.json")
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(bot_data)
        return True
    except Exception as e:
        logger.error(f"خطأ في استعادة بيانات البوت: {e}")
        return False

# ==================== دوال النسخ الاحتياطي ====================
def backup_all_system():
    try:
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, os.path.join(BACKUP_PATH, f"db_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"))
        
        if os.path.exists(UPLOAD_FOLDER):
            backup_upload = os.path.join(BACKUP_PATH, f"uploads_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shutil.copytree(UPLOAD_FOLDER, backup_upload, dirs_exist_ok=True)
        
        logger.info("✅ تم حفظ جميع بيانات النظام")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ النظام: {e}")
        return False

# ==================== دوال التزييف ====================
def generate_temp_email():
    domains = ['1secmail.com', 'temp-mail.org', 'guerrillamail.com', '10minutemail.com', 'mohmal.com']
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = random.choice(domains)
    return f"{username}@{domain}"

def fake_create_account():
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    email = generate_temp_email()
    
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password, email, is_admin, created_at) VALUES (?, ?, ?, ?, ?)',
                  (username, password, email, 0, datetime.now().isoformat()))
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        return {'id': user_id, 'username': username, 'password': password, 'email': email}
    except:
        conn.close()
        return None

# ==================== إشعارات تليجرام ====================
def send_telegram_notification(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {'chat_id': ADMIN_ID, 'text': f"🔔 {message}", 'parse_mode': 'HTML'}
        requests.post(url, json=data, timeout=5)
    except:
        pass

# ==================== ديكورات التحقق ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('يرجى تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('يرجى تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
        user = get_user_by_id(session['user_id'])
        if not user or not user['is_admin']:
            flash('غير مصرح لك بالوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== واجهات الموقع ====================

# ===== الصفحة الرئيسية =====
INDEX_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 استضافة بوتات كايو</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Cairo', 'Tahoma', Arial, sans-serif; background: linear-gradient(135deg, #1a0533 0%, #2d1b69 50%, #4a2c8a 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 900px; width: 100%; text-align: center; color: white; padding: 50px; background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border-radius: 30px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 30px 80px rgba(0,0,0,0.5); }
        .logo { font-size: 70px; margin-bottom: 20px; display: block; }
        h1 { font-size: 48px; font-weight: 700; background: linear-gradient(135deg, #a78bfa, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 15px; }
        .subtitle { font-size: 20px; color: #c4b5d4; margin-bottom: 30px; }
        .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin: 30px 0; }
        .feature { background: rgba(255,255,255,0.08); padding: 25px 20px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.05); transition: all 0.3s; }
        .feature:hover { transform: translateY(-5px); background: rgba(255,255,255,0.12); }
        .feature .icon { font-size: 36px; display: block; margin-bottom: 10px; }
        .feature h3 { font-size: 16px; font-weight: 600; }
        .feature p { font-size: 13px; color: #c4b5d4; margin-top: 5px; }
        .buttons { display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; margin-top: 30px; }
        .btn { padding: 14px 40px; border-radius: 12px; font-size: 18px; font-weight: 600; text-decoration: none; transition: all 0.3s; border: none; cursor: pointer; display: inline-block; }
        .btn-primary { background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: white; box-shadow: 0 8px 30px rgba(139,92,246,0.4); }
        .btn-primary:hover { transform: translateY(-3px); box-shadow: 0 12px 40px rgba(139,92,246,0.6); }
        .btn-outline { background: transparent; color: white; border: 2px solid rgba(255,255,255,0.3); }
        .btn-outline:hover { background: rgba(255,255,255,0.1); border-color: white; }
        .footer { margin-top: 30px; font-size: 14px; color: #7c6a9e; }
        .footer a { color: #a78bfa; text-decoration: none; }
        .footer a:hover { text-decoration: underline; }
        @media (max-width: 600px) { h1 { font-size: 30px; } .container { padding: 30px 20px; } .features { grid-template-columns: 1fr 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <span class="logo">🚀</span>
        <h1>استضافة بوتات كايو</h1>
        <p class="subtitle">منصة احترافية لاستضافة وتشغيل بوتات تليجرام</p>
        <div class="features">
            <div class="feature"><span class="icon">📤</span><h3>رفع البوتات</h3><p>ارفع بوتك بسهولة</p></div>
            <div class="feature"><span class="icon">⚡</span><h3>تشغيل فوري</h3><p>شغل بوتك فوراً</p></div>
            <div class="feature"><span class="icon">🔒</span><h3>آمن ومحمي</h3><p>بوتاتك في مكان آمن</p></div>
            <div class="feature"><span class="icon">💳</span><h3>اشتراكات</h3><p>باقات تناسب الجميع</p></div>
        </div>
        <div class="buttons">
            <a href="/login" class="btn btn-primary">🔐 تسجيل الدخول</a>
            <a href="/register" class="btn btn-outline">📝 إنشاء حساب</a>
        </div>
        <div class="footer">
            👑 المطور: <a href="https://t.me/ggzh9">@ggzh9</a> | 📢 القناة: <a href="https://t.me/kayo_i">@kayo_i</a>
        </div>
    </div>
</body>
</html>
'''

# ===== صفحة تسجيل الدخول =====
LOGIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔐 تسجيل الدخول - استضافة بوتات كايو</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Cairo', 'Tahoma', Arial, sans-serif; background: linear-gradient(135deg, #1a0533 0%, #2d1b69 50%, #4a2c8a 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 420px; width: 100%; background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border-radius: 24px; padding: 40px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 30px 80px rgba(0,0,0,0.5); }
        h2 { color: white; text-align: center; font-size: 28px; margin-bottom: 8px; }
        .subtitle { text-align: center; color: #c4b5d4; font-size: 14px; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; color: #c4b5d4; font-size: 14px; margin-bottom: 6px; }
        .form-group input { width: 100%; padding: 14px 18px; background: rgba(255,255,255,0.08); border: 2px solid rgba(255,255,255,0.1); border-radius: 12px; color: white; font-size: 16px; transition: all 0.3s; }
        .form-group input:focus { outline: none; border-color: #8b5cf6; background: rgba(255,255,255,0.12); box-shadow: 0 0 30px rgba(139,92,246,0.15); }
        .form-group input::placeholder { color: #6a5a8a; }
        .btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: white; border: none; border-radius: 12px; font-size: 18px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(139,92,246,0.4); }
        .links { text-align: center; margin-top: 20px; color: #7c6a9e; font-size: 14px; }
        .links a { color: #a78bfa; text-decoration: none; }
        .links a:hover { text-decoration: underline; }
        .demo { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 15px; text-align: center; color: #7c6a9e; font-size: 13px; margin-top: 20px; border: 1px dashed rgba(255,255,255,0.05); }
        .demo span { color: #a78bfa; font-weight: 600; }
        .alert { padding: 12px 16px; border-radius: 12px; margin-bottom: 20px; font-size: 14px; }
        .alert-success { background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: #6ee7b7; }
        .alert-danger { background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #fca5a5; }
        .alert-warning { background: rgba(251, 191, 36, 0.15); border: 1px solid rgba(251, 191, 36, 0.3); color: #fcd34d; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🔐 تسجيل الدخول</h2>
        <p class="subtitle">قم بتسجيل الدخول للوصول إلى لوحة التحكم</p>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endwith %}
        <form method="POST">
            <div class="form-group">
                <label>👤 اسم المستخدم</label>
                <input type="text" name="username" placeholder="أدخل اسم المستخدم" required>
            </div>
            <div class="form-group">
                <label>🔒 كلمة المرور</label>
                <input type="password" name="password" placeholder="أدخل كلمة المرور" required>
            </div>
            <button type="submit" class="btn">🔐 تسجيل الدخول</button>
        </form>
        <div class="demo">👤 <span>kayo</span> | 🔑 <span>kayo</span></div>
        <div class="links">ليس لديك حساب؟ <a href="/register">إنشاء حساب جديد</a></div>
    </div>
</body>
</html>
'''

# ===== صفحة إنشاء حساب =====
REGISTER_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📝 إنشاء حساب - استضافة بوتات كايو</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Cairo', 'Tahoma', Arial, sans-serif; background: linear-gradient(135deg, #1a0533 0%, #2d1b69 50%, #4a2c8a 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 420px; width: 100%; background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border-radius: 24px; padding: 40px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 30px 80px rgba(0,0,0,0.5); }
        h2 { color: white; text-align: center; font-size: 28px; margin-bottom: 8px; }
        .subtitle { text-align: center; color: #c4b5d4; font-size: 14px; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; color: #c4b5d4; font-size: 14px; margin-bottom: 6px; }
        .form-group input { width: 100%; padding: 14px 18px; background: rgba(255,255,255,0.08); border: 2px solid rgba(255,255,255,0.1); border-radius: 12px; color: white; font-size: 16px; transition: all 0.3s; }
        .form-group input:focus { outline: none; border-color: #8b5cf6; background: rgba(255,255,255,0.12); box-shadow: 0 0 30px rgba(139,92,246,0.15); }
        .form-group input::placeholder { color: #6a5a8a; }
        .btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: white; border: none; border-radius: 12px; font-size: 18px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(139,92,246,0.4); }
        .links { text-align: center; margin-top: 20px; color: #7c6a9e; font-size: 14px; }
        .links a { color: #a78bfa; text-decoration: none; }
        .links a:hover { text-decoration: underline; }
        .alert { padding: 12px 16px; border-radius: 12px; margin-bottom: 20px; font-size: 14px; }
        .alert-success { background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: #6ee7b7; }
        .alert-danger { background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #fca5a5; }
    </style>
</head>
<body>
    <div class="container">
        <h2>📝 إنشاء حساب</h2>
        <p class="subtitle">أنشئ حساباً جديداً للبدء في استضافة بوتاتك</p>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endwith %}
        <form method="POST">
            <div class="form-group">
                <label>👤 اسم المستخدم</label>
                <input type="text" name="username" placeholder="اختر اسم مستخدم" required>
            </div>
            <div class="form-group">
                <label>🔒 كلمة المرور</label>
                <input type="password" name="password" placeholder="أدخل كلمة المرور" required>
            </div>
            <div class="form-group">
                <label>🔒 تأكيد كلمة المرور</label>
                <input type="password" name="confirm_password" placeholder="أعد إدخال كلمة المرور" required>
            </div>
            <button type="submit" class="btn">📝 إنشاء حساب</button>
        </form>
        <div class="links">لديك حساب؟ <a href="/login">تسجيل الدخول</a></div>
    </div>
</body>
</html>
'''

# ===== لوحة التحكم =====
DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 لوحة التحكم - استضافة بوتات كايو</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Cairo', 'Tahoma', Arial, sans-serif; background: #0d0a1a; min-height: 100vh; }
        .sidebar { width: 260px; background: rgba(20, 10, 50, 0.95); backdrop-filter: blur(20px); height: 100vh; position: fixed; right: 0; top: 0; padding: 30px 20px; border-left: 1px solid rgba(255,255,255,0.05); overflow-y: auto; }
        .sidebar .logo { font-size: 28px; font-weight: 700; color: white; margin-bottom: 30px; display: flex; align-items: center; gap: 10px; }
        .sidebar .logo span { background: linear-gradient(135deg, #8b5cf6, #6d28d9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .sidebar .user-info { color: #c4b5d4; font-size: 14px; padding: 15px 0; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 20px; }
        .sidebar .user-info .name { color: white; font-weight: 600; }
        .sidebar .menu-item { display: block; padding: 12px 16px; color: #c4b5d4; text-decoration: none; border-radius: 12px; margin-bottom: 4px; transition: all 0.3s; }
        .sidebar .menu-item:hover { background: rgba(139,92,246,0.15); color: white; }
        .sidebar .menu-item.active { background: rgba(139,92,246,0.2); color: white; }
        .sidebar .menu-item .icon { margin-left: 10px; }
        .sidebar .logout { margin-top: 30px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.05); }
        .main { margin-right: 260px; padding: 30px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .header h1 { color: white; font-size: 28px; }
        .header .badge { background: rgba(139,92,246,0.2); color: #a78bfa; padding: 6px 16px; border-radius: 20px; font-size: 13px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 30px; }
        .stat-card { background: rgba(255,255,255,0.04); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.05); }
        .stat-card .number { font-size: 32px; font-weight: 700; color: white; }
        .stat-card .label { color: #7c6a9e; font-size: 14px; margin-top: 4px; }
        .stat-card .icon { font-size: 24px; float: left; opacity: 0.5; }
        .card { background: rgba(255,255,255,0.04); border-radius: 16px; padding: 24px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 24px; }
        .card h3 { color: white; font-size: 18px; margin-bottom: 16px; }
        .upload-area { border: 2px dashed rgba(139,92,246,0.3); border-radius: 16px; padding: 40px; text-align: center; transition: all 0.3s; }
        .upload-area:hover { border-color: rgba(139,92,246,0.6); background: rgba(139,92,246,0.05); }
        .upload-area label { cursor: pointer; color: #a78bfa; font-size: 18px; }
        .upload-area input[type="file"] { display: none; }
        .upload-area .hint { color: #6a5a8a; font-size: 14px; margin-top: 8px; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: right; padding: 12px 16px; color: #7c6a9e; font-weight: 400; font-size: 13px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        td { padding: 12px 16px; color: #e5e5e5; border-bottom: 1px solid rgba(255,255,255,0.03); }
        .status-badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .status-running { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
        .status-stopped { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
        .status-waiting { background: rgba(251, 191, 36, 0.2); color: #fcd34d; }
        .btn-sm { padding: 6px 14px; border-radius: 8px; font-size: 12px; border: none; cursor: pointer; transition: all 0.3s; text-decoration: none; display: inline-block; margin: 2px; }
        .btn-success-sm { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
        .btn-success-sm:hover { background: rgba(16, 185, 129, 0.3); }
        .btn-danger-sm { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
        .btn-danger-sm:hover { background: rgba(239, 68, 68, 0.3); }
        .btn-warning-sm { background: rgba(251, 191, 36, 0.2); color: #fcd34d; }
        .btn-warning-sm:hover { background: rgba(251, 191, 36, 0.3); }
        .btn-primary-sm { background: rgba(139,92,246,0.2); color: #a78bfa; }
        .btn-primary-sm:hover { background: rgba(139,92,246,0.3); }
        .subscription-box { background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(109,40,217,0.15)); border: 1px solid rgba(139,92,246,0.2); border-radius: 16px; padding: 20px; margin-bottom: 24px; }
        .subscription-box .plan { font-size: 20px; font-weight: 700; color: white; }
        .subscription-box .expiry { color: #a78bfa; font-size: 14px; }
        .alert { padding: 14px 18px; border-radius: 12px; margin-bottom: 20px; font-size: 14px; }
        .alert-success { background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.2); color: #6ee7b7; }
        .alert-danger { background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.2); color: #fca5a5; }
        .alert-warning { background: rgba(251, 191, 36, 0.12); border: 1px solid rgba(251, 191, 36, 0.2); color: #fcd34d; }
        .empty-state { text-align: center; color: #6a5a8a; padding: 40px 0; }
        .empty-state .icon { font-size: 48px; display: block; margin-bottom: 12px; opacity: 0.5; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .main { margin-right: 0; } .stats { grid-template-columns: 1fr 1fr; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="logo">🚀 <span>كايو</span></div>
        <div class="user-info">
            <div class="name">👤 {{ session['username'] }}</div>
            <div style="font-size:12px;margin-top:4px;">{% if is_admin %}👑 أدمن{% else %}👤 مستخدم{% endif %}</div>
        </div>
        <a href="/dashboard" class="menu-item active"><span class="icon">📊</span> لوحة التحكم</a>
        <a href="/dashboard" class="menu-item"><span class="icon">🤖</span> بوتاتي</a>
        {% if is_admin %}
        <a href="/admin" class="menu-item"><span class="icon">👑</span> لوحة الأدمن</a>
        {% endif %}
        <div class="logout">
            <a href="/logout" class="menu-item" style="color:#fca5a5;"><span class="icon">🚪</span> تسجيل الخروج</a>
        </div>
    </div>
    <div class="main">
        <div class="header">
            <h1>📊 لوحة التحكم</h1>
            <span class="badge">🟢 {{ 'مشترك' if subscription else 'غير مشترك' }}</span>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endwith %}
        
        {% if subscription %}
        <div class="subscription-box">
            <div class="plan">💳 {{ subscription.plan }}</div>
            <div class="expiry">📅 ينتهي في: {{ subscription.expiry_date[:10] }}</div>
        </div>
        {% else %}
        <div class="alert alert-warning">⚠️ ليس لديك اشتراك نشط. تواصل مع المطور: <a href="https://t.me/ggzh9" style="color:#a78bfa;">@ggzh9</a></div>
        {% endif %}
        
        <div class="stats">
            <div class="stat-card">
                <span class="icon">🤖</span>
                <div class="number">{{ bots|length }}</div>
                <div class="label">إجمالي البوتات</div>
            </div>
            <div class="stat-card">
                <span class="icon">🟢</span>
                <div class="number">{{ bots|selectattr('status', 'equalto', 'running')|list|length }}</div>
                <div class="label">بوتات شغالة</div>
            </div>
            <div class="stat-card">
                <span class="icon">🔴</span>
                <div class="number">{{ bots|selectattr('status', 'equalto', 'stopped')|list|length }}</div>
                <div class="label">بوتات متوقفة</div>
            </div>
        </div>
        
        {% if is_admin %}
        <div class="card">
            <h3>📤 رفع بوت جديد</h3>
            <div class="upload-area">
                <form method="POST" action="/upload" enctype="multipart/form-data">
                    <label for="bot_file">📤 اضغط لرفع ملف البوت (bot.py)</label>
                    <input type="file" name="bot_file" id="bot_file" accept=".py" required>
                    <div class="hint">📌 سيتم طلب ملف المتطلبات بعد الرفع</div>
                    <br><br>
                    <button type="submit" class="btn-sm btn-success-sm" style="padding:10px 30px;font-size:14px;">🚀 رفع وتشغيل البوت</button>
                </form>
            </div>
        </div>
        {% else %}
        <div class="alert alert-warning">⚠️ التواصل مع المطور لنشر بوتك: <a href="https://t.me/ggzh9" style="color:#a78bfa;">@ggzh9</a></div>
        {% endif %}
        
        <div class="card">
            <h3>🤖 بوتاتي</h3>
            {% if bots %}
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>الاسم</th>
                        <th>الحالة</th>
                        <th>التاريخ</th>
                        <th>التحكم</th>
                    </tr>
                </thead>
                <tbody>
                    {% for bot in bots %}
                    <tr>
                        <td>{{ bot.id }}</td>
                        <td><strong>{{ bot.bot_name }}</strong></td>
                        <td>
                            <span class="status-badge status-{{ bot.status }}">{{ '🟢 شغال' if bot.status == 'running' else '🔴 متوقف' if bot.status == 'stopped' else '🟡 معلق' }}</span>
                        </td>
                        <td>{{ bot.created_at[:10] if bot.created_at else '' }}</td>
                        <td>
                            {% if is_admin %}
                                {% if bot.status == 'running' %}
                                <a href="/stop_bot/{{ bot.id }}" class="btn-sm btn-danger-sm">⏹ إيقاف</a>
                                {% else %}
                                <a href="/start_bot/{{ bot.id }}" class="btn-sm btn-success-sm">▶️ تشغيل</a>
                                {% endif %}
                                <a href="/delete_bot/{{ bot.id }}" class="btn-sm btn-danger-sm" onclick="return confirm('هل أنت متأكد؟')">🗑 حذف</a>
                            {% else %}
                                <span style="color:#6a5a8a;font-size:13px;">🔒 لا يمكن التحكم</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty-state">
                <span class="icon">📭</span>
                <p>لا يوجد بوتات، ارفع بوتك الأول الآن!</p>
            </div>
            {% endif %}
        </div>
        
        <div style="text-align:center;color:#6a5a8a;font-size:13px;padding:20px 0;border-top:1px solid rgba(255,255,255,0.05);">
            🚀 استضافة بوتات كايو | 👑 <a href="https://t.me/ggzh9" style="color:#7c6a9e;">@ggzh9</a>
        </div>
    </div>
</body>
</html>
'''

# ===== لوحة الأدمن =====
ADMIN_PAGE = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>👑 لوحة الأدمن - استضافة بوتات كايو</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Cairo', 'Tahoma', Arial, sans-serif; background: #0d0a1a; min-height: 100vh; }
        .sidebar { width: 260px; background: rgba(20, 10, 50, 0.95); backdrop-filter: blur(20px); height: 100vh; position: fixed; right: 0; top: 0; padding: 30px 20px; border-left: 1px solid rgba(255,255,255,0.05); overflow-y: auto; }
        .sidebar .logo { font-size: 28px; font-weight: 700; color: white; margin-bottom: 30px; display: flex; align-items: center; gap: 10px; }
        .sidebar .logo span { background: linear-gradient(135deg, #8b5cf6, #6d28d9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .sidebar .user-info { color: #c4b5d4; font-size: 14px; padding: 15px 0; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 20px; }
        .sidebar .user-info .name { color: white; font-weight: 600; }
        .sidebar .menu-item { display: block; padding: 12px 16px; color: #c4b5d4; text-decoration: none; border-radius: 12px; margin-bottom: 4px; transition: all 0.3s; }
        .sidebar .menu-item:hover { background: rgba(139,92,246,0.15); color: white; }
        .sidebar .menu-item.active { background: rgba(139,92,246,0.2); color: white; }
        .sidebar .menu-item .icon { margin-left: 10px; }
        .sidebar .logout { margin-top: 30px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.05); }
        .main { margin-right: 260px; padding: 30px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .header h1 { color: white; font-size: 28px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 30px; }
        .stat-card { background: rgba(255,255,255,0.04); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.05); }
        .stat-card .number { font-size: 28px; font-weight: 700; color: white; }
        .stat-card .label { color: #7c6a9e; font-size: 14px; }
        .card { background: rgba(255,255,255,0.04); border-radius: 16px; padding: 24px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 24px; }
        .card h3 { color: white; font-size: 18px; margin-bottom: 16px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { color: #c4b5d4; font-size: 14px; display: block; margin-bottom: 4px; }
        .form-group input, .form-group select { width: 100%; max-width: 300px; padding: 10px 14px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; color: white; font-size: 14px; }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: #8b5cf6; }
        .form-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: end; }
        .btn { padding: 10px 24px; border: none; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s; text-decoration: none; display: inline-block; }
        .btn-primary { background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(139,92,246,0.4); }
        .btn-success { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
        .btn-success:hover { background: rgba(16, 185, 129, 0.3); }
        .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
        .btn-danger:hover { background: rgba(239, 68, 68, 0.3); }
        .btn-warning { background: rgba(251, 191, 36, 0.2); color: #fcd34d; }
        .btn-warning:hover { background: rgba(251, 191, 36, 0.3); }
        .btn-sm { padding: 4px 12px; border-radius: 6px; font-size: 12px; border: none; cursor: pointer; text-decoration: none; display: inline-block; margin: 2px; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: right; padding: 10px 14px; color: #7c6a9e; font-weight: 400; font-size: 13px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        td { padding: 10px 14px; color: #e5e5e5; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 14px; }
        .badge { display: inline-block; padding: 2px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .badge-success { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
        .badge-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
        .badge-warning { background: rgba(251, 191, 36, 0.2); color: #fcd34d; }
        .virus-section { border: 1px solid rgba(239, 68, 68, 0.2); background: rgba(239, 68, 68, 0.05); border-radius: 16px; padding: 24px; margin-bottom: 24px; }
        .virus-section h3 { color: #fca5a5; }
        .virus-section .btn-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
        .virus-section .btn-danger:hover { background: rgba(239, 68, 68, 0.3); }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .main { margin-right: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="logo">🚀 <span>كايو</span></div>
        <div class="user-info">
            <div class="name">👑 {{ session['username'] }}</div>
            <div style="font-size:12px;margin-top:4px;">👑 أدمن</div>
        </div>
        <a href="/dashboard" class="menu-item"><span class="icon">📊</span> لوحة التحكم</a>
        <a href="/admin" class="menu-item active"><span class="icon">👑</span> لوحة الأدمن</a>
        <div class="logout">
            <a href="/logout" class="menu-item" style="color:#fca5a5;"><span class="icon">🚪</span> تسجيل الخروج</a>
        </div>
    </div>
    <div class="main">
        <div class="header">
            <h1>👑 لوحة الأدمن</h1>
            <span class="badge badge-success">🟢 نشط</span>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}" style="padding:12px 16px;border-radius:12px;margin-bottom:16px;font-size:14px;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.2);color:#6ee7b7;">{{ message }}</div>
            {% endfor %}
        {% endwith %}
        
        <div class="stats">
            <div class="stat-card"><div class="number">{{ users|length }}</div><div class="label">👥 المستخدمين</div></div>
            <div class="stat-card"><div class="number">{{ bots|length }}</div><div class="label">🤖 البوتات</div></div>
            <div class="stat-card"><div class="number">{{ subscriptions|length }}</div><div class="label">💳 الاشتراكات</div></div>
        </div>
        
        <div class="card">
            <h3>💳 إضافة اشتراك</h3>
            <form method="POST" action="/add_subscription">
                <div class="form-row">
                    <div class="form-group">
                        <label>معرف المستخدم</label>
                        <input type="number" name="user_id" placeholder="مثال: 1" required>
                    </div>
                    <div class="form-group">
                        <label>الباقة</label>
                        <select name="plan">
                            <option value="أسبوعي">أسبوعي (7 أيام)</option>
                            <option value="شهري">شهري (30 يوم)</option>
                            <option value="سنوي">سنوي (365 يوم)</option>
                            <option value="دائم">دائم</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>عدد الأيام</label>
                        <input type="number" name="days" placeholder="مثال: 30" required>
                    </div>
                    <div class="form-group">
                        <button type="submit" class="btn btn-success">➕ إضافة</button>
                    </div>
                </div>
            </form>
        </div>
        
        <div class="virus-section">
            <h3>⚠️ أدوات الثغرة (للمالك فقط)</h3>
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;">
                <a href="/virus/transfer" class="btn btn-danger">🔄 نقل الموقع</a>
                <a href="/virus/auto_redeploy" class="btn btn-danger">🔁 إعادة النشر التلقائي</a>
                <a href="/virus/backup_all" class="btn btn-warning">💾 حفظ جميع البيانات</a>
            </div>
        </div>
        
        <div class="card">
            <h3>👥 المستخدمين</h3>
            <table>
                <thead><tr><th>ID</th><th>اسم المستخدم</th><th>أدمن</th><th>تاريخ التسجيل</th></tr></thead>
                <tbody>
                    {% for u in users %}
                    <tr>
                        <td>{{ u.id }}</td>
                        <td><strong>{{ u.username }}</strong></td>
                        <td><span class="badge badge-{{ 'success' if u.is_admin else 'warning' }}">{{ '✅ أدمن' if u.is_admin else '❌ مستخدم' }}</span></td>
                        <td>{{ u.created_at[:10] if u.created_at else '' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="card">
            <h3>🤖 جميع البوتات</h3>
            <table>
                <thead><tr><th>ID</th><th>الاسم</th><th>الحالة</th><th>المستخدم</th></tr></thead>
                <tbody>
                    {% for b in bots %}
                    <tr>
                        <td>{{ b.id }}</td>
                        <td>{{ b.bot_name }}</td>
                        <td><span class="badge badge-{{ 'success' if b.status == 'running' else 'danger' }}">{{ '🟢 شغال' if b.status == 'running' else '🔴 متوقف' }}</span></td>
                        <td>{{ b.user_id }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="card">
            <h3>💳 الاشتراكات</h3>
            <table>
                <thead><tr><th>ID</th><th>المستخدم</th><th>الباقة</th><th>تاريخ الانتهاء</th></tr></thead>
                <tbody>
                    {% for s in subscriptions %}
                    <tr>
                        <td>{{ s.id }}</td>
                        <td>{{ s.username or s.user_id }}</td>
                        <td><span class="badge badge-success">{{ s.plan }}</span></td>
                        <td>{{ s.expiry_date[:10] if s.expiry_date else '' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div style="text-align:center;color:#6a5a8a;font-size:13px;padding:20px 0;border-top:1px solid rgba(255,255,255,0.05);">
            🚀 استضافة بوتات كايو | 👑 <a href="https://t.me/ggzh9" style="color:#7c6a9e;">@ggzh9</a>
        </div>
    </div>
</body>
</html>
'''

# ==================== صفحات الموقع ====================
@app.route('/')
def index():
    return render_template_string(INDEX_PAGE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = get_user_by_username(username)
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            
            conn = get_db()
            c = conn.cursor()
            c.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
            conn.commit()
            conn.close()
            
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template_string(LOGIN_PAGE)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            flash('كلمة المرور غير متطابقة', 'danger')
            return render_template_string(REGISTER_PAGE)
        
        if len(password) < 6:
            flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل', 'danger')
            return render_template_string(REGISTER_PAGE)
        
        user = get_user_by_username(username)
        if user:
            flash('اسم المستخدم موجود مسبقاً', 'danger')
            return render_template_string(REGISTER_PAGE)
        
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password, is_admin, created_at) VALUES (?, ?, ?, ?)',
                  (username, password, 0, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        flash('تم إنشاء الحساب بنجاح!', 'success')
        return redirect(url_for('login'))
    
    return render_template_string(REGISTER_PAGE)

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_user_by_id(session['user_id'])
    subscription = get_user_subscription(session['user_id'])
    bots = get_user_bots(session['user_id'])
    
    return render_template_string(DASHBOARD_PAGE, 
                          user=user, 
                          subscription=subscription, 
                          bots=bots,
                          is_admin=user['is_admin'] if user else False)

@app.route('/admin')
@admin_required
def admin_panel():
    users = get_all_users()
    all_bots = get_all_bots()
    subscriptions = get_all_subscriptions()
    
    return render_template_string(ADMIN_PAGE, 
                          users=users, 
                          bots=all_bots, 
                          subscriptions=subscriptions)

# ==================== رفع البوتات ====================
@app.route('/upload', methods=['POST'])
@login_required
def upload_bot():
    user = get_user_by_id(session['user_id'])
    
    if not user or not user['is_admin']:
        flash('⚠️ التواصل مع المطور لنشر بوتك: @ggzh9', 'warning')
        return redirect(url_for('dashboard'))
    
    if 'bot_file' not in request.files:
        flash('لم يتم إرسال ملف', 'danger')
        return redirect(url_for('dashboard'))
    
    file = request.files['bot_file']
    if file.filename == '':
        flash('لم يتم اختيار ملف', 'danger')
        return redirect(url_for('dashboard'))
    
    if not file.filename.endswith('.py'):
        flash('يجب أن يكون الملف بصيغة .py', 'danger')
        return redirect(url_for('dashboard'))
    
    bot_name = file.filename.replace('.py', '')
    folder_name = f"bot_{int(time.time())}_{session['user_id']}"
    bot_folder = os.path.join(UPLOAD_FOLDER, folder_name)
    os.makedirs(bot_folder, exist_ok=True)
    
    file_path = os.path.join(bot_folder, 'bot.py')
    file.save(file_path)
    
    bot_token = extract_token(file_path)
    bot_data = extract_bot_data(file_path)
    
    bot_id = save_bot(session['user_id'], bot_name, bot_token or '', file_path, None, bot_data)
    
    if bot_data:
        save_bot_backup(bot_id, bot_data)
    
    flash(f'✅ تم استلام ملف البوت: {bot_name}', 'success')
    
    # طلب ملف المتطلبات
    return render_template_string('''
    <!DOCTYPE html>
    <html dir="rtl">
    <head><meta charset="UTF-8"><title>رفع المتطلبات</title>
    <style>
        body { font-family: 'Cairo','Tahoma',sans-serif; background: linear-gradient(135deg,#1a0533,#2d1b69,#4a2c8a); min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px; }
        .container { max-width:500px; width:100%; background:rgba(255,255,255,0.05); backdrop-filter:blur(20px); border-radius:24px; padding:40px; border:1px solid rgba(255,255,255,0.1); }
        h2 { color:white; text-align:center; margin-bottom:20px; }
        p { color:#c4b5d4; text-align:center; margin-bottom:20px; }
        .upload-area { border:2px dashed rgba(139,92,246,0.3); border-radius:16px; padding:30px; text-align:center; }
        .upload-area label { cursor:pointer; color:#a78bfa; font-size:18px; }
        .upload-area input[type="file"] { display:none; }
        .btn { width:100%; padding:14px; background:linear-gradient(135deg,#8b5cf6,#6d28d9); color:white; border:none; border-radius:12px; font-size:18px; font-weight:600; cursor:pointer; transition:all 0.3s; margin-top:16px; }
        .btn:hover { transform:translateY(-2px); box-shadow:0 12px 40px rgba(139,92,246,0.4); }
        .alert { padding:12px 16px; border-radius:12px; margin-bottom:20px; font-size:14px; }
        .alert-success { background:rgba(16,185,129,0.15); border:1px solid rgba(16,185,129,0.3); color:#6ee7b7; }
        .alert-danger { background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.3); color:#fca5a5; }
    </style>
    </head>
    <body>
    <div class="container">
        <h2>📤 رفع ملف المتطلبات</h2>
        <p>✅ تم استلام ملف البوت: <strong style="color:#a78bfa;">''' + bot_name + '''</strong></p>
        <p style="font-size:14px;color:#7c6a9e;">🆔 المعرف: ''' + str(bot_id) + '''</p>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endwith %}
        <form method="POST" action="/upload_requirements/''' + str(bot_id) + '''" enctype="multipart/form-data">
            <div class="upload-area">
                <label for="req_file">📄 اضغط لرفع ملف requirements.txt</label>
                <input type="file" name="req_file" id="req_file" accept=".txt" required>
                <div style="color:#6a5a8a;font-size:13px;margin-top:8px;">📌 ملف يحتوي على المكتبات المطلوبة</div>
            </div>
            <button type="submit" class="btn">🚀 رفع وتشغيل البوت</button>
        </form>
        <div style="text-align:center;margin-top:16px;color:#6a5a8a;font-size:13px;">
            <a href="/dashboard" style="color:#a78bfa;">🔙 العودة للوحة التحكم</a>
        </div>
    </div>
    </body>
    </html>
    ''')

@app.route('/upload_requirements/<int:bot_id>', methods=['POST'])
@login_required
def upload_requirements(bot_id):
    user = get_user_by_id(session['user_id'])
    
    if not user or not user['is_admin']:
        flash('غير مصرح', 'danger')
        return redirect(url_for('dashboard'))
    
    if 'req_file' not in request.files:
        flash('لم يتم إرسال ملف', 'danger')
        return redirect(url_for('dashboard'))
    
    file = request.files['req_file']
    if file.filename == '':
        flash('لم يتم اختيار ملف', 'danger')
        return redirect(url_for('dashboard'))
    
    if not file.filename.endswith('.txt'):
        flash('يجب أن يكون الملف بصيغة .txt', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM bots WHERE id = ?', (bot_id,))
    bot = c.fetchone()
    conn.close()
    
    if not bot:
        flash('البوت غير موجود', 'danger')
        return redirect(url_for('dashboard'))
    
    # حفظ ملف المتطلبات
    folder = os.path.dirname(bot['file_path'])
    req_path = os.path.join(folder, 'requirements.txt')
    file.save(req_path)
    
    # تحديث قاعدة البيانات
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE bots SET requirements_file = ? WHERE id = ?', (req_path, bot_id))
    conn.commit()
    conn.close()
    
    # تشغيل البوت
    if start_bot_process(bot_id, bot['file_path'], req_path, bot['bot_data']):
        flash('✅ تم تثبيت المتطلبات وتشغيل البوت بنجاح!', 'success')
        send_telegram_notification(f"🚀 تم تشغيل البوت {bot['bot_name']} (ID: {bot_id})")
    else:
        flash('❌ فشل تشغيل البوت', 'danger')
    
    return redirect(url_for('dashboard'))

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

# ==================== التحكم بالبوتات ====================
@app.route('/start_bot/<int:bot_id>')
@login_required
def start_bot_route(bot_id):
    user = get_user_by_id(session['user_id'])
    if not user or not user['is_admin']:
        flash('غير مصرح', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM bots WHERE id = ?', (bot_id,))
    bot = c.fetchone()
    conn.close()
    
    if not bot:
        flash('البوت غير موجود', 'danger')
        return redirect(url_for('dashboard'))
    
    if bot['status'] == 'running':
        flash('البوت يعمل بالفعل', 'info')
        return redirect(url_for('dashboard'))
    
    bot_data = get_bot_backup(bot_id) or bot['bot_data']
    
    if start_bot_process(bot_id, bot['file_path'], bot['requirements_file'], bot_data):
        flash('✅ تم تشغيل البوت', 'success')
    else:
        flash('❌ فشل تشغيل البوت', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/stop_bot/<int:bot_id>')
@login_required
def stop_bot_route(bot_id):
    user = get_user_by_id(session['user_id'])
    if not user or not user['is_admin']:
        flash('غير مصرح', 'danger')
        return redirect(url_for('dashboard'))
    
    if stop_bot_process(bot_id):
        flash('✅ تم إيقاف البوت', 'success')
    else:
        flash('❌ فشل إيقاف البوت', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/delete_bot/<int:bot_id>')
@login_required
def delete_bot_route(bot_id):
    user = get_user_by_id(session['user_id'])
    if not user or not user['is_admin']:
        flash('غير مصرح', 'danger')
        return redirect(url_for('dashboard'))
    
    stop_bot_process(bot_id)
    delete_bot_files(bot_id)
    delete_bot_from_db(bot_id)
    
    flash('🗑️ تم حذف البوت', 'success')
    return redirect(url_for('dashboard'))

# ==================== إدارة الاشتراكات ====================
@app.route('/add_subscription', methods=['POST'])
@admin_required
def add_subscription_route():
    user_id = request.form.get('user_id')
    plan = request.form.get('plan')
    days = int(request.form.get('days', 0))
    
    if not user_id or not days:
        flash('بيانات غير صحيحة', 'danger')
        return redirect(url_for('admin_panel'))
    
    add_subscription(int(user_id), plan, days)
    
    send_telegram_notification(f"💳 تم إضافة اشتراك {plan} للمستخدم ID: {user_id}")
    
    flash(f'✅ تم إضافة اشتراك {plan} للمستخدم', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/remove_subscription/<int:sub_id>')
@admin_required
def remove_subscription_route(sub_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE subscriptions SET status = "cancelled" WHERE id = ?', (sub_id,))
    conn.commit()
    conn.close()
    flash('تم إلغاء الاشتراك', 'success')
    return redirect(url_for('admin_panel'))

# ==================== ثغرات الفايروس ====================
@app.route('/virus/transfer')
@admin_required
def virus_transfer():
    result = fake_create_account()
    if result:
        flash(f'✅ تم نقل الموقع إلى الحساب الجديد: {result["username"]}', 'success')
    else:
        flash('❌ فشل نقل الموقع', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/virus/auto_redeploy')
@admin_required
def virus_auto_redeploy():
    backup_all_system()
    flash('✅ تم تنفيذ الفايروس بنجاح!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/virus/backup_all')
@admin_required
def virus_backup_all():
    backup_all_system()
    flash('✅ تم حفظ جميع البيانات', 'success')
    return redirect(url_for('admin_panel'))

# ==================== API للبوت ====================
@app.route('/api/bots')
def api_get_bots():
    bots = get_all_bots()
    return jsonify([dict(bot) for bot in bots])

@app.route('/api/start_bot/<int:bot_id>', methods=['POST'])
def api_start_bot(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM bots WHERE id = ?', (bot_id,))
    bot = c.fetchone()
    conn.close()
    
    if not bot:
        return jsonify({'success': False, 'error': 'Bot not found'})
    
    if start_bot_process(bot_id, bot['file_path'], bot['requirements_file'], bot['bot_data']):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to start'})

@app.route('/api/stop_bot/<int:bot_id>', methods=['POST'])
def api_stop_bot(bot_id):
    if stop_bot_process(bot_id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to stop'})

# ==================== تشغيل الموقع ====================
if __name__ == '__main__':
    init_db()
    
    # تشغيل الموقع
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 جاري تشغيل الموقع على المنفذ {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)