import os
import sys
import time
import json
import requests
import sqlite3
import shutil
import random
import string
import threading
import logging
from datetime import datetime
import subprocess
import re
import base64
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
import pickle
import tempfile

# ==================== إعدادات التسجيل ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('virus.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== الإعدادات ====================
GITHUB_REPO = "https://github.com/yesssssssie-debug/botkayo"
SITE_URL = os.environ.get('SITE_URL', 'https://bot-hosting.railway.app')
ADMIN_ID = 7947679527
BOT_TOKEN = "7999963241:AAHN-AoxKf1MKTnF-fPMWcMZzbhOr-vwa0k"
DB_PATH = 'hosting.db'
BACKUP_PATH = 'backups'
DATA_PATH = 'data'
COOKIES_PATH = 'cookies'

for path in [BACKUP_PATH, DATA_PATH, COOKIES_PATH]:
    os.makedirs(path, exist_ok=True)

# ==================== دوال البريد المؤقت ====================
class TempEmailManager:
    """إدارة البريد المؤقت بشكل حقيقي"""
    
    def __init__(self):
        self.current_email = None
        self.current_domain = None
    
    def generate_email(self):
        """إنشاء بريد مؤقت جديد"""
        domains = ['1secmail.com', 'temp-mail.org', 'guerrillamail.com', '10minutemail.com', 'mohmal.com']
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(domains)
        self.current_email = f"{username}@{domain}"
        self.current_domain = domain
        return self.current_email
    
    def get_messages(self):
        """جلب الرسائل من البريد المؤقت"""
        if not self.current_email:
            return []
        
        try:
            username, domain = self.current_email.split('@')
            
            if domain == '1secmail.com':
                response = requests.get(
                    f"https://www.1secmail.com/api/v1/?action=getMessages&login={username}&domain={domain}",
                    timeout=10
                )
                if response.status_code == 200:
                    return response.json()
            return []
        except:
            return []
    
    def read_message(self, message_id):
        """قراءة رسالة محددة"""
        if not self.current_email:
            return None
        
        try:
            username, domain = self.current_email.split('@')
            
            if domain == '1secmail.com':
                response = requests.get(
                    f"https://www.1secmail.com/api/v1/?action=readMessage&login={username}&domain={domain}&id={message_id}",
                    timeout=10
                )
                if response.status_code == 200:
                    return response.json()
            return None
        except:
            return None
    
    def wait_for_message(self, timeout=60, keyword=None):
        """انتظار وصول رسالة معينة"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            messages = self.get_messages()
            if messages:
                for msg in messages:
                    if keyword and keyword.lower() in msg.get('subject', '').lower():
                        return self.read_message(msg['id'])
                    elif not keyword:
                        return self.read_message(msg['id'])
            time.sleep(5)
        return None

# ==================== دوال Selenium ====================
class RailwayAutomator:
    """أتمتة إنشاء حساب على Railway باستخدام Selenium"""
    
    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None
        self.email_manager = TempEmailManager()
    
    def setup_driver(self):
        """إعداد متصفح Chrome مع إعدادات التخفي"""
        try:
            options = uc.ChromeOptions()
            
            if self.headless:
                options.add_argument('--headless=new')
            
            # إعدادات التخفي
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # إعدادات الوكيل
            proxy = get_working_proxy()
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
            
            # إنشاء السائق
            self.driver = uc.Chrome(options=options)
            
            # تنفيذ سكريبت إزالة أثر الأتمتة
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            logger.info("✅ تم إعداد المتصفح بنجاح")
            return True
        except Exception as e:
            logger.error(f"❌ فشل إعداد المتصفح: {e}")
            return False
    
    def create_account(self):
        """إنشاء حساب على Railway تلقائياً"""
        try:
            # 1. إنشاء بريد مؤقت
            email = self.email_manager.generate_email()
            logger.info(f"📧 تم إنشاء بريد مؤقت: {email}")
            
            # 2. فتح صفحة التسجيل
            self.driver.get("https://railway.app/signup")
            time.sleep(3)
            
            # 3. إدخال البريد الإلكتروني
            try:
                email_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
                )
                email_input.clear()
                email_input.send_keys(email)
                email_input.send_keys(Keys.RETURN)
                logger.info(f"✅ تم إدخال البريد: {email}")
            except:
                logger.warning("⚠️ لم يتم العثور على حقل البريد")
            
            time.sleep(3)
            
            # 4. انتظار رسالة التأكيد
            logger.info("📨 انتظار رسالة التأكيد...")
            confirmation = self.email_manager.wait_for_message(timeout=60, keyword="confirm")
            
            if confirmation:
                # استخراج رابط التأكيد
                import re
                urls = re.findall(r'https?://[^\s]+', confirmation.get('body', ''))
                for url in urls:
                    if 'confirm' in url.lower() or 'verify' in url.lower():
                        logger.info(f"✅ تم استخراج رابط التأكيد: {url}")
                        self.driver.get(url)
                        time.sleep(5)
                        break
            
            # 5. إدخال كلمة المرور
            try:
                password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                password_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                if password_inputs:
                    for inp in password_inputs:
                        inp.clear()
                        inp.send_keys(password)
                    logger.info(f"✅ تم إدخال كلمة المرور: {password}")
            except:
                logger.warning("⚠️ لم يتم العثور على حقل كلمة المرور")
            
            time.sleep(2)
            
            # 6. الضغط على زر التسجيل
            try:
                submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                submit_btn.click()
                logger.info("✅ تم الضغط على زر التسجيل")
            except:
                logger.warning("⚠️ لم يتم العثور على زر التسجيل")
            
            time.sleep(5)
            
            # 7. حفظ الجلسة
            cookies = self.driver.get_cookies()
            self.save_session(cookies)
            
            # 8. فتح صفحة النشر
            self.driver.get("https://railway.app/new")
            time.sleep(3)
            
            # 9. نشر المشروع
            try:
                # البحث عن خيار النشر من GitHub
                github_option = self.driver.find_element(By.XPATH, "//*[contains(text(), 'GitHub')]")
                github_option.click()
                time.sleep(2)
                
                # إدخال رابط المستودع
                repo_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='text']")
                repo_input.clear()
                repo_input.send_keys(GITHUB_REPO)
                repo_input.send_keys(Keys.RETURN)
                logger.info(f"✅ تم نشر المستودع: {GITHUB_REPO}")
            except:
                logger.warning("⚠️ لم يتم العثور على خيار النشر من GitHub")
            
            time.sleep(5)
            
            # 10. الحصول على رابط الموقع
            try:
                url_element = self.driver.find_element(By.CSS_SELECTOR, "a[href*='railway.app']")
                site_url = url_element.get_attribute('href')
                logger.info(f"✅ تم الحصول على رابط الموقع: {site_url}")
            except:
                site_url = f"https://{email.split('@')[0]}.railway.app"
            
            return {
                'success': True,
                'email': email,
                'password': password,
                'url': site_url,
                'cookies': cookies
            }
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء الحساب: {e}")
            return {'success': False, 'error': str(e)}
    
    def save_session(self, cookies):
        """حفظ جلسة المتصفح"""
        try:
            session_file = os.path.join(COOKIES_PATH, f"session_{int(time.time())}.pkl")
            with open(session_file, 'wb') as f:
                pickle.dump(cookies, f)
            logger.info(f"✅ تم حفظ الجلسة: {session_file}")
            return True
        except:
            return False
    
    def load_session(self, session_file):
        """تحميل جلسة محفوظة"""
        try:
            with open(session_file, 'rb') as f:
                cookies = pickle.load(f)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
            logger.info(f"✅ تم تحميل الجلسة: {session_file}")
            return True
        except:
            return False
    
    def close(self):
        """إغلاق المتصفح"""
        if self.driver:
            self.driver.quit()
            logger.info("✅ تم إغلاق المتصفح")

# ==================== دوال البروكسيات ====================
def get_working_proxy():
    """الحصول على بروكسي عامل"""
    proxies = [
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
    
    for proxy in proxies:
        try:
            response = requests.get('https://api.github.com', proxies={'http': proxy, 'https': proxy}, timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ بروكسي عامل: {proxy}")
                return proxy
        except:
            continue
    return None

# ==================== دوال نقل البيانات ====================
def backup_database():
    """حفظ قاعدة البيانات"""
    try:
        if os.path.exists(DB_PATH):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(BACKUP_PATH, f"db_{timestamp}.db")
            shutil.copy2(DB_PATH, backup_file)
            logger.info(f"✅ تم حفظ قاعدة البيانات: {backup_file}")
            
            # ضغط الملف
            import gzip
            with open(backup_file, 'rb') as f_in:
                with gzip.open(f"{backup_file}.gz", 'wb') as f_out:
                    f_out.write(f_in.read())
            os.remove(backup_file)
            
            return backup_file
    except Exception as e:
        logger.error(f"خطأ في حفظ قاعدة البيانات: {e}")
    return None

def backup_all_files():
    """حفظ جميع الملفات المهمة"""
    try:
        files_to_backup = ['app.py', 'bot.py', 'requirements.txt', 'Procfile', 'hosting.db']
        backup_dir = os.path.join(BACKUP_PATH, f"files_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(backup_dir, exist_ok=True)
        
        for file in files_to_backup:
            if os.path.exists(file):
                shutil.copy2(file, os.path.join(backup_dir, file))
                logger.info(f"✅ تم حفظ الملف: {file}")
        
        # ضغط المجلد
        import zipfile
        zip_path = f"{backup_dir}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(backup_dir))
                    zipf.write(file_path, arcname)
        
        shutil.rmtree(backup_dir)
        logger.info(f"✅ تم ضغط الملفات: {zip_path}")
        return zip_path
    except Exception as e:
        logger.error(f"خطأ في حفظ الملفات: {e}")
        return None

def extract_all_bots_data():
    """استخراج جميع بيانات البوتات"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, bot_name, bot_token, bot_data, file_path, status, created_at FROM bots')
        results = c.fetchall()
        conn.close()
        
        bots_data = {}
        for bot in results:
            bots_data[bot[0]] = {
                'name': bot[1],
                'token': bot[2],
                'data': bot[3],
                'file_path': bot[4],
                'status': bot[5],
                'created_at': bot[6]
            }
        logger.info(f"✅ تم استخراج بيانات {len(bots_data)} بوت")
        return bots_data
    except Exception as e:
        logger.error(f"خطأ في استخراج بيانات البوتات: {e}")
        return {}

def extract_all_users_data():
    """استخراج جميع بيانات المستخدمين"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, username, password, is_admin, backup_data, created_at, last_login FROM users')
        results = c.fetchall()
        conn.close()
        
        users_data = {}
        for user in results:
            users_data[user[0]] = {
                'username': user[1],
                'password': user[2],
                'is_admin': user[3],
                'backup_data': user[4],
                'created_at': user[5],
                'last_login': user[6]
            }
        logger.info(f"✅ تم استخراج بيانات {len(users_data)} مستخدم")
        return users_data
    except Exception as e:
        logger.error(f"خطأ في استخراج بيانات المستخدمين: {e}")
        return {}

def extract_all_subscriptions():
    """استخراج جميع الاشتراكات"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, user_id, plan, start_date, expiry_date, status FROM subscriptions')
        results = c.fetchall()
        conn.close()
        
        subscriptions = []
        for sub in results:
            subscriptions.append({
                'id': sub[0],
                'user_id': sub[1],
                'plan': sub[2],
                'start_date': sub[3],
                'expiry_date': sub[4],
                'status': sub[5]
            })
        logger.info(f"✅ تم استخراج بيانات {len(subscriptions)} اشتراك")
        return subscriptions
    except Exception as e:
        logger.error(f"خطأ في استخراج الاشتراكات: {e}")
        return []

def create_export_data():
    """إنشاء ملف تصدير كامل"""
    try:
        export_data = {
            'bots': extract_all_bots_data(),
            'users': extract_all_users_data(),
            'subscriptions': extract_all_subscriptions(),
            'timestamp': datetime.now().isoformat(),
            'github_repo': GITHUB_REPO,
            'site_url': SITE_URL,
            'version': '2.0.0'
        }
        
        export_file = os.path.join(BACKUP_PATH, f"complete_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ تم إنشاء ملف التصدير: {export_file}")
        return export_file
    except Exception as e:
        logger.error(f"خطأ في إنشاء ملف التصدير: {e}")
        return None

# ==================== دوال النشر ====================
def deploy_to_new_account():
    """نشر الموقع على حساب جديد باستخدام Selenium"""
    try:
        logger.info("🔄 بدء عملية النشر على حساب جديد...")
        
        # 1. إنشاء حساب جديد
        automator = RailwayAutomator(headless=False)
        if not automator.setup_driver():
            logger.error("❌ فشل إعداد المتصفح")
            return {'success': False, 'error': 'فشل إعداد المتصفح'}
        
        result = automator.create_account()
        automator.close()
        
        if not result['success']:
            logger.error(f"❌ فشل إنشاء الحساب: {result.get('error')}")
            return result
        
        logger.info(f"✅ تم إنشاء الحساب الجديد: {result['email']}")
        
        # 2. حفظ البيانات
        backup_database()
        backup_all_files()
        export_file = create_export_data()
        
        if export_file:
            logger.info(f"✅ تم إنشاء ملف التصدير: {export_file}")
        
        # 3. إرسال إشعار
        send_telegram_notification(
            f"🔄 تم إنشاء حساب جديد ونشر الموقع!\n"
            f"📧 البريد: {result['email']}\n"
            f"🔑 كلمة المرور: {result['password']}\n"
            f"🔗 الرابط: {result['url']}\n"
            f"📦 المستودع: {GITHUB_REPO}"
        )
        
        return {
            'success': True,
            'email': result['email'],
            'password': result['password'],
            'url': result['url'],
            'message': 'تم إنشاء الحساب ونشر الموقع بنجاح'
        }
        
    except Exception as e:
        logger.error(f"❌ خطأ في النشر: {e}")
        return {'success': False, 'error': str(e)}

# ==================== دوال تليجرام ====================
def send_telegram_notification(message):
    """إرسال إشعار إلى المطور"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': ADMIN_ID,
            'text': f"🔔 {message}",
            'parse_mode': 'HTML'
        }
        requests.post(url, json=data, timeout=5)
        logger.info("✅ تم إرسال الإشعار")
    except Exception as e:
        logger.error(f"❌ فشل إرسال الإشعار: {e}")

def send_telegram_file(file_path, caption=""):
    """إرسال ملف إلى المطور"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': ADMIN_ID, 'caption': caption}
            requests.post(url, files=files, data=data, timeout=10)
        logger.info(f"✅ تم إرسال الملف: {file_path}")
    except Exception as e:
        logger.error(f"❌ فشل إرسال الملف: {e}")

# ==================== الفايروس الرئيسي ====================
class Virus:
    """الفايروس الرئيسي"""
    
    def __init__(self):
        self.running = False
        self.thread = None
    
    def start(self):
        """بدء تشغيل الفايروس"""
        if self.running:
            logger.warning("⚠️ الفايروس يعمل بالفعل")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("🦠 تم بدء تشغيل الفايروس")
    
    def stop(self):
        """إيقاف الفايروس"""
        self.running = False
        logger.info("🛑 تم إيقاف الفايروس")
    
    def _run(self):
        """حلقة التشغيل الرئيسية"""
        while self.running:
            try:
                logger.info("🔄 تنفيذ دورة الفايروس...")
                
                # 1. حفظ البيانات الحالية
                backup_database()
                backup_all_files()
                create_export_data()
                
                # 2. إنشاء حساب جديد ونشر الموقع
                result = deploy_to_new_account()
                
                if result['success']:
                    logger.info("✅ تم نشر الموقع على الحساب الجديد")
                    
                    # إرسال تقرير
                    send_telegram_notification(
                        f"✅ اكتملت دورة الفايروس\n"
                        f"📧 البريد: {result['email']}\n"
                        f"🔗 الرابط: {result['url']}"
                    )
                else:
                    logger.error(f"❌ فشل نشر الموقع: {result.get('error')}")
                    send_telegram_notification(
                        f"❌ فشل نشر الموقع\n"
                        f"الخطأ: {result.get('error')}"
                    )
                
                # 3. الانتظار حتى الدورة التالية
                wait_time = 86400  # 24 ساعة
                logger.info(f"⏳ الانتظار {wait_time // 3600} ساعة حتى الدورة التالية")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"❌ خطأ في دورة الفايروس: {e}")
                send_telegram_notification(f"❌ خطأ في الفايروس: {str(e)}")
                time.sleep(3600)

# ==================== التشغيل الرئيسي ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🦠 تشغيل فايروس النقل التلقائي 100%")
    print(f"📦 المستودع: {GITHUB_REPO}")
    print(f"🔗 الموقع الحالي: {SITE_URL}")
    print("=" * 60)
    
    # إنشاء المجلدات
    for path in ['backups', 'data', 'cookies']:
        os.makedirs(path, exist_ok=True)
    
    # تشغيل الفايروس
    virus = Virus()
    
    # تنفيذ دورة أولى فورية
    logger.info("🚀 تنفيذ الدورة الأولى...")
    result = deploy_to_new_account()
    
    if result['success']:
        print(f"✅ تم نشر الموقع على: {result['url']}")
        print(f"📧 البريد: {result['email']}")
        print(f"🔑 كلمة المرور: {result['password']}")
    else:
        print(f"❌ فشل النشر: {result.get('error')}")
    
    # تشغيل الحلقة اللانهائية
    print("\n🔄 تشغيل الحلقة اللانهائية...")
    virus.start()
    
    # انتظار حتى يتم إيقاف الفايروس
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 إيقاف الفايروس...")
        virus.stop()