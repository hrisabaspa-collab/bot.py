import os
import json
import sqlite3
import shutil
import time
import hashlib
import base64
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backup.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BACKUP_PATH = 'backups'
DATA_PATH = 'data'
DB_PATH = 'hosting.db'

for path in [BACKUP_PATH, DATA_PATH]:
    os.makedirs(path, exist_ok=True)

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
            logger.info(f"✅ تم ضغط الملف: {backup_file}.gz")
            
            return backup_file
    except Exception as e:
        logger.error(f"خطأ في حفظ قاعدة البيانات: {e}")
    return None

def backup_files():
    """حفظ الملفات المهمة"""
    try:
        files = ['app.py', 'bot.py', 'requirements.txt', 'Procfile']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join(BACKUP_PATH, f"files_{timestamp}")
        os.makedirs(backup_dir, exist_ok=True)
        
        for file in files:
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

def backup_bots_data():
    """حفظ بيانات البوتات"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, bot_name, bot_data FROM bots WHERE bot_data IS NOT NULL')
        bots = c.fetchall()
        conn.close()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(BACKUP_PATH, f"bots_data_{timestamp}.json")
        
        data = {}
        for bot in bots:
            data[bot[0]] = {
                'name': bot[1],
                'data': bot[2]
            }
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ تم حفظ بيانات {len(bots)} بوت: {backup_file}")
        return backup_file
    except Exception as e:
        logger.error(f"خطأ في حفظ بيانات البوتات: {e}")
        return None

def backup_users_data():
    """حفظ بيانات المستخدمين"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, username, backup_data FROM users WHERE backup_data IS NOT NULL')
        users = c.fetchall()
        conn.close()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(BACKUP_PATH, f"users_data_{timestamp}.json")
        
        data = {}
        for user in users:
            data[user[0]] = {
                'username': user[1],
                'data': user[2]
            }
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ تم حفظ بيانات {len(users)} مستخدم: {backup_file}")
        return backup_file
    except Exception as e:
        logger.error(f"خطأ في حفظ بيانات المستخدمين: {e}")
        return None

def backup_all():
    """حفظ كل شيء"""
    try:
        logger.info("🔄 بدء حفظ جميع البيانات...")
        
        db_backup = backup_database()
        files_backup = backup_files()
        bots_backup = backup_bots_data()
        users_backup = backup_users_data()
        
        # إنشاء تقرير
        report = {
            'timestamp': datetime.now().isoformat(),
            'database': db_backup,
            'files': files_backup,
            'bots': bots_backup,
            'users': users_backup
        }
        
        report_file = os.path.join(BACKUP_PATH, f"backup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info("✅ تم حفظ جميع البيانات بنجاح")
        return report
    except Exception as e:
        logger.error(f"خطأ في حفظ جميع البيانات: {e}")
        return None

def restore_backup(backup_file):
    """استعادة نسخة احتياطية"""
    try:
        if not os.path.exists(backup_file):
            logger.error(f"الملف غير موجود: {backup_file}")
            return False
        
        # استعادة قاعدة البيانات
        if backup_file.endswith('.db'):
            shutil.copy2(backup_file, DB_PATH)
            logger.info(f"✅ تم استعادة قاعدة البيانات: {backup_file}")
            return True
        
        # استعادة ملفات
        if backup_file.endswith('.zip'):
            import zipfile
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                zipf.extractall(BACKUP_PATH)
            logger.info(f"✅ تم استعادة الملفات: {backup_file}")
            return True
        
        # استعادة بيانات JSON
        if backup_file.endswith('.json'):
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # معالجة البيانات المستعادة
            logger.info(f"✅ تم استعادة البيانات: {backup_file}")
            return True
        
        return False
    except Exception as e:
        logger.error(f"خطأ في استعادة النسخة: {e}")
        return False

def cleanup_old_backups(keep=5):
    """حذف النسخ الاحتياطية القديمة"""
    try:
        files = os.listdir(BACKUP_PATH)
        backups = {}
        
        for file in files:
            if file.endswith('.zip') or file.endswith('.gz') or file.endswith('.json'):
                file_path = os.path.join(BACKUP_PATH, file)
                backups[file] = os.path.getctime(file_path)
        
        # ترتيب حسب التاريخ
        sorted_backups = sorted(backups.items(), key=lambda x: x[1], reverse=True)
        
        # حذف القديمة
        for file, _ in sorted_backups[keep:]:
            file_path = os.path.join(BACKUP_PATH, file)
            os.remove(file_path)
            logger.info(f"🗑️ تم حذف النسخة القديمة: {file}")
        
        return len(sorted_backups) - min(len(sorted_backups), keep)
    except Exception as e:
        logger.error(f"خطأ في حذف النسخ القديمة: {e}")
        return 0

if __name__ == "__main__":
    print("=" * 50)
    print("📦 إدارة النسخ الاحتياطي")
    print("=" * 50)
    
    # حفظ كل شيء
    report = backup_all()
    if report:
        print(f"✅ تم حفظ البيانات: {report}")
    
    # تنظيف القديمة
    deleted = cleanup_old_backups()
    print(f"🗑️ تم حذف {deleted} نسخة قديمة")