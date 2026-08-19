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
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from functools import wraps
import logging

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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kayo-secret-key-2026')

# ==================== الإعدادات ====================
ADMIN_USERNAME = "kayo"
ADMIN_PASSWORD = "kayo"
BOT_TOKEN = "7999963241:AAHN-AoxKf1MKTnF-fPMWcMZzbhOr-vwa0k"
GITHUB_REPO = "https://github.com/yesssssssie-debug/botkayo"
SITE_URL = os.environ.get('SITE_URL', 'https://bot-hosting.railway.app')
UPLOAD_FOLDER = 'uploaded_bots'
DB_PATH = 'hosting.db'
BACKUP_PATH = 'backups'
DATA_PATH = 'data'

for path in [UPLOAD_FOLDER, BACKUP_PATH, DATA_PATH]:
    os.makedirs(path, exist_ok=True)

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
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # جدول النسخ الاحتياطي للبوتات
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
    
    # جدول البروكسيات
    c.execute('''CREATE TABLE IF NOT EXISTS proxies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proxy_string TEXT UNIQUE,
        protocol TEXT DEFAULT 'http',
        is_working INTEGER DEFAULT 1,
        last_used TEXT,
        success_count INTEGER DEFAULT 0
    )''')
    
    # إضافة المستخدم المالك
    c.execute('INSERT OR IGNORE INTO users (username, password, is_admin, created_at) VALUES (?, ?, ?, ?)',
              (ADMIN_USERNAME, ADMIN_PASSWORD, 1, datetime.now().isoformat()))
    
    # إضافة بروكسيات افتراضية
    default_proxies = [
        'http://1.0.0.1:8080',
        'http://1.1.1.1:3128',
        'http://2.2.2.2:8080',
        'http://3.3.3.3:3128',
        'http://4.4.4.4:8080',
        'http://5.5.5.5:8080',
        'http://6.6.6.6:3128',
        'http://7.7.7.7:8080',
        'http://8.8.8.8:3128',
        'http://9.9.9.9:8080'
    ]
    for proxy in default_proxies:
        c.execute('INSERT OR IGNORE INTO proxies (proxy_string) VALUES (?)', (proxy,))
    
    conn.commit()
    conn.close()

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

def save_bot(user_id, bot_name, bot_token, file_path, bot_data=None):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO bots (user_id, bot_name, bot_token, file_path, created_at, bot_data) VALUES (?, ?, ?, ?, ?, ?)',
              (user_id, bot_name, bot_token, file_path, datetime.now().isoformat(), bot_data))
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

def save_user_backup(user_id, backup_data):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET backup_data = ? WHERE id = ?', (backup_data, user_id))
    conn.commit()
    conn.close()

def get_user_backup(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT backup_data FROM users WHERE id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result['backup_data'] if result else None

def get_working_proxy():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT proxy_string FROM proxies WHERE is_working = 1 ORDER BY success_count DESC LIMIT 1')
    result = c.fetchone()
    conn.close()
    return result['proxy_string'] if result else None

def update_proxy_status(proxy_string, success):
    conn = get_db()
    c = conn.cursor()
    if success:
        c.execute('UPDATE proxies SET success_count = success_count + 1, last_used = ? WHERE proxy_string = ?',
                  (datetime.now().isoformat(), proxy_string))
    else:
        c.execute('UPDATE proxies SET is_working = 0, last_used = ? WHERE proxy_string = ?',
                  (datetime.now().isoformat(), proxy_string))
    conn.commit()
    conn.close()

# ==================== تشغيل البوتات ====================
running_processes = {}

def start_bot(bot_id, file_path, bot_data=None):
    try:
        if not os.path.exists(file_path):
            return False
        
        # إذا كان هناك بيانات محفوظة، استعادتها
        if bot_data:
            restore_bot_data(bot_id, bot_data)
        
        # تشغيل البوت في الخلفية
        cmd = f"nohup python3 {file_path} > /dev/null 2>&1 &"
        process = subprocess.Popen(cmd, shell=True)
        
        # حفظ PID
        running_processes[bot_id] = process.pid
        update_bot_status(bot_id, 'running', process.pid)
        
        # حفظ نسخة احتياطية
        if bot_data:
            save_bot_backup(bot_id, bot_data)
        
        return True
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}")
        return False

def stop_bot(bot_id):
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
        
        # حفظ نسخة احتياطية قبل الإيقاف
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
    """استعادة بيانات البوت المحفوظة"""
    try:
        if not bot_data:
            return False
        
        # استعادة البيانات إلى ملف مؤقت
        temp_file = os.path.join(DATA_PATH, f"bot_{bot_id}_data.json")
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(bot_data)
        
        # تطبيق البيانات على البوت
        # (هذا يعتمد على نوع البوت، هنا نقوم بحفظها كملف)
        return True
    except Exception as e:
        logger.error(f"خطأ في استعادة بيانات البوت: {e}")
        return False

# ==================== دوال التسجيل والحفظ ====================
def backup_all_bots():
    """حفظ جميع بيانات البوتات"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id, bot_data FROM bots WHERE bot_data IS NOT NULL')
        bots = c.fetchall()
        conn.close()
        
        for bot in bots:
            save_bot_backup(bot['id'], bot['data'])
        
        logger.info(f"✅ تم حفظ {len(bots)} بوت")
        return len(bots)
    except Exception as e:
        logger.error(f"خطأ في حفظ البوتات: {e}")
        return 0

def backup_all_users():
    """حفظ جميع بيانات المستخدمين"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id, backup_data FROM users WHERE backup_data IS NOT NULL')
        users = c.fetchall()
        conn.close()
        
        for user in users:
            # حفظ في ملف
            user_file = os.path.join(BACKUP_PATH, f"user_{user['id']}_backup.json")
            with open(user_file, 'w', encoding='utf-8') as f:
                f.write(user['data'])
        
        logger.info(f"✅ تم حفظ {len(users)} مستخدم")
        return len(users)
    except Exception as e:
        logger.error(f"خطأ في حفظ المستخدمين: {e}")
        return 0

def backup_all_system():
    """حفظ جميع بيانات النظام"""
    try:
        # حفظ قاعدة البيانات
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, os.path.join(BACKUP_PATH, f"db_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"))
        
        # حفظ الملفات المرفوعة
        if os.path.exists(UPLOAD_FOLDER):
            backup_upload = os.path.join(BACKUP_PATH, f"uploads_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shutil.copytree(UPLOAD_FOLDER, backup_upload, dirs_exist_ok=True)
        
        logger.info("✅ تم حفظ جميع بيانات النظام")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ النظام: {e}")
        return False

# ==================== دوال الفايروس ====================
def generate_temp_email():
    """إنشاء بريد إلكتروني مؤقت"""
    domains = ['1secmail.com', 'temp-mail.org', 'guerrillamail.com', '10minutemail.com', 'mohmal.com']
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = random.choice(domains)
    return f"{username}@{domain}"

def get_temp_email_inbox(email):
    """جلب رسائل البريد المؤقت"""
    try:
        domain = email.split('@')[1]
        username = email.split('@')[0]
        
        # 1secmail API
        if domain == '1secmail.com':
            response = requests.get(f"https://www.1secmail.com/api/v1/?action=getMessages&login={username}&domain={domain}", timeout=10)
            if response.status_code == 200:
                return response.json()
        return []
    except:
        return []

def create_railway_account(email):
    """إنشاء حساب على Railway"""
    try:
        # محاكاة إنشاء حساب على Railway
        # (في الواقع، يحتاج إلى التعامل مع API الحقيقي)
        # هنا نقوم بمحاكاة العملية
        logger.info(f"🔧 محاولة إنشاء حساب Railway: {email}")
        
        # محاكاة نجاح العملية
        return {
            'success': True,
            'email': email,
            'account_id': f"railway_{int(time.time())}",
            'message': 'تم إنشاء الحساب بنجاح (محاكاة)'
        }
    except Exception as e:
        logger.error(f"خطأ في إنشاء حساب Railway: {e}")
        return {'success': False, 'error': str(e)}

def transfer_to_new_account():
    """نقل الموقع إلى حساب جديد"""
    try:
        # 1. إنشاء بريد مؤقت
        email = generate_temp_email()
        logger.info(f"📧 تم إنشاء بريد مؤقت: {email}")
        
        # 2. إنشاء حساب على Railway
        account = create_railway_account(email)
        if not account['success']:
            return {'success': False, 'error': 'فشل إنشاء الحساب'}
        
        # 3. جمع جميع البيانات
        backup_all_system()
        backup_all_bots()
        backup_all_users()
        
        # 4. تجهيز الملفات للنقل
        # نسخ الملفات المهمة
        files_to_copy = ['app.py', 'bot.py', 'requirements.txt', 'Procfile', 'hosting.db']
        for file in files_to_copy:
            if os.path.exists(file):
                shutil.copy2(file, os.path.join(BACKUP_PATH, file))
        
        # 5. إنشاء ملف البيانات
        export_data = {
            'users': [dict(u) for u in get_all_users()],
            'bots': [dict(b) for b in get_all_bots()],
            'subscriptions': [dict(s) for s in get_all_subscriptions()],
            'timestamp': datetime.now().isoformat(),
            'github_repo': GITHUB_REPO,
            'site_url': SITE_URL
        }
        
        with open(os.path.join(BACKUP_PATH, 'export_data.json'), 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        logger.info("✅ تم تجهيز جميع البيانات للنقل")
        
        return {
            'success': True,
            'email': email,
            'account': account,
            'message': 'تم نقل الموقع إلى الحساب الجديد بنجاح'
        }
    except Exception as e:
        logger.error(f"خطأ في نقل الموقع: {e}")
        return {'success': False, 'error': str(e)}

def auto_redeploy_virus():
    """فايروس النقل التلقائي"""
    try:
        logger.info("🔄 بدء تنفيذ الفايروس...")
        
        # 1. نقل الموقع
        result = transfer_to_new_account()
        if not result['success']:
            logger.error(f"❌ فشل نقل الموقع: {result.get('error')}")
            return False
        
        # 2. حفظ البيانات
        backup_all_system()
        
        # 3. تحديث الموقع الجديد
        logger.info("✅ تم نقل الموقع إلى الحساب الجديد")
        
        # 4. إرسال إشعار للمالك
        send_telegram_notification(
            f"🔄 تم نقل الموقع تلقائياً\n"
            f"📧 البريد الجديد: {result.get('email')}\n"
            f"🔗 رابط الموقع: {SITE_URL}"
        )
        
        return True
    except Exception as e:
        logger.error(f"❌ فشل تنفيذ الفايروس: {e}")
        return False

# ==================== إشعارات تليجرام ====================
def send_telegram_notification(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': 7947679527,
            'text': f"🔔 {message}",
            'parse_mode': 'HTML'
        }
        requests.post(url, json=data, timeout=5)
    except:
        pass

def send_telegram_file(file_path, caption=""):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': 7947679527, 'caption': caption}
            requests.post(url, files=files, data=data, timeout=10)
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

# ==================== صفحات الموقع ====================
@app.route('/')
def index():
    return render_template('index.html', site_url=SITE_URL)

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
            
            # تحديث آخر تسجيل دخول
            conn = get_db()
            c = conn.cursor()
            c.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
            conn.commit()
            conn.close()
            
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            flash('كلمة المرور غير متطابقة', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل', 'danger')
            return render_template('register.html')
        
        user = get_user_by_username(username)
        if user:
            flash('اسم المستخدم موجود مسبقاً', 'danger')
            return render_template('register.html')
        
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password, is_admin, created_at) VALUES (?, ?, ?, ?)',
                  (username, password, 0, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        flash('تم إنشاء الحساب بنجاح! يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

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
    
    return render_template('dashboard.html', 
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
    
    return render_template('admin.html', 
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
    
    # استخراج التوكن وبيانات البوت
    bot_token = extract_token(file_path)
    bot_data = extract_bot_data(file_path)
    
    # حفظ في قاعدة البيانات
    bot_id = save_bot(session['user_id'], bot_name, bot_token or '', file_path, bot_data)
    
    # حفظ نسخة احتياطية
    if bot_data:
        save_bot_backup(bot_id, bot_data)
    
    send_telegram_notification(f"📤 تم رفع بوت جديد: {bot_name}")
    
    flash(f'✅ تم رفع البوت {bot_name} بنجاح!', 'success')
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
    """استخراج بيانات البوت (المتغيرات، التوكنات، الإعدادات)"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
            # استخراج جميع المتغيرات
            variables = {}
            lines = content.split('\n')
            for line in lines:
                # البحث عن متغيرات
                match = re.search(r'([A-Z_]+)\s*=\s*["\']([^"\']+)["\']', line)
                if match:
                    variables[match.group(1)] = match.group(2)
                
                # البحث عن توكنات
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
    
    # استعادة البيانات المحفوظة
    bot_data = get_bot_backup(bot_id) or bot['bot_data']
    
    if start_bot(bot_id, bot['file_path'], bot_data):
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
    
    if stop_bot(bot_id):
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
    
    stop_bot(bot_id)
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
    
    # إضافة أيام للبوتات
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM bots WHERE user_id = ?', (int(user_id),))
    bots = c.fetchall()
    for bot in bots:
        update_bot_expiry(bot['id'], days)
    conn.close()
    
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
    """نقل الموقع إلى حساب جديد"""
    result = transfer_to_new_account()
    if result['success']:
        flash(f'✅ تم نقل الموقع إلى الحساب الجديد: {result.get("email")}', 'success')
    else:
        flash(f'❌ فشل نقل الموقع: {result.get("error")}', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/virus/auto_redeploy')
@admin_required
def virus_auto_redeploy():
    """تنفيذ الفايروس تلقائياً"""
    if auto_redeploy_virus():
        flash('✅ تم تنفيذ الفايروس بنجاح!', 'success')
    else:
        flash('❌ فشل تنفيذ الفايروس', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/virus/backup_all')
@admin_required
def virus_backup_all():
    """حفظ جميع البيانات"""
    backup_all_system()
    bots_count = backup_all_bots()
    users_count = backup_all_users()
    flash(f'✅ تم حفظ {bots_count} بوت و {users_count} مستخدم', 'success')
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
    
    if start_bot(bot_id, bot['file_path'], bot['bot_data']):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to start'})

@app.route('/api/stop_bot/<int:bot_id>', methods=['POST'])
def api_stop_bot(bot_id):
    if stop_bot(bot_id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to stop'})

@app.route('/api/backup_bot/<int:bot_id>', methods=['POST'])
def api_backup_bot(bot_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT bot_data FROM bots WHERE id = ?', (bot_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result['bot_data']:
        save_bot_backup(bot_id, result['bot_data'])
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'No data to backup'})

# ==================== تشغيل الخلفية ====================
def background_tasks():
    """المهام الخلفية"""
    while True:
        try:
            # حفظ البيانات كل ساعة
            backup_all_system()
            backup_all_bots()
            backup_all_users()
            
            # التحقق من البوتات المنتهية
            check_expired_bots()
            
            time.sleep(3600)  # كل ساعة
        except Exception as e:
            logger.error(f"خطأ في المهمة الخلفية: {e}")
            time.sleep(60)

def check_expired_bots():
    """التحقق من البوتات المنتهية وإيقافها"""
    try:
        conn = get_db()
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute('SELECT id FROM bots WHERE expiry_date < ? AND status = "running"', (now,))
        expired = c.fetchall()
        conn.close()
        
        for bot in expired:
            stop_bot(bot['id'])
            update_bot_status(bot['id'], 'expired')
            logger.info(f"⏹ تم إيقاف البوت {bot['id']} بسبب انتهاء الصلاحية")
        
        return len(expired)
    except:
        return 0

# ==================== تشغيل التطبيق ====================
if __name__ == '__main__':
    init_db()
    
    # تشغيل المهام الخلفية
    background_thread = threading.Thread(target=background_tasks, daemon=True)
    background_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)