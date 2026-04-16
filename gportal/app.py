# app.py - AI Downloader Server (نسخة متكاملة مع واجهة ويب)
# تشغيل السيرفر: pip install -r requirements.txt ثم python app.py

import os
import time
import json
import uuid
import threading
import subprocess
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response, stream_with_context, send_from_directory
from flask_cors import CORS
import yt_dlp

# ==================== الإعدادات الأساسية ====================
app = Flask(__name__)
CORS(app)  # السماح بالاتصال من المتصفح

# مجلد التحميلات المؤقتة
DOWNLOAD_FOLDER = Path("downloads")
DOWNLOAD_FOLDER.mkdir(exist_ok=True)

# تخزين مؤقت للمهام الجارية
tasks = {}
tasks_lock = threading.Lock()

# ==================== صفحة الويب الرئيسية ====================

@app.route('/')
def serve_html():
    """عرض صفحة mdownload.html من نفس المجلد"""
    return send_from_directory('.', 'mdownload.html')

@app.route('/<path:path>')
def serve_static(path):
    """خدمة أي ملفات ثابتة أخرى (لو احتجنا مستقبلاً)"""
    if os.path.exists(path):
        return send_from_directory('.', path)
    return "الملف غير موجود", 404

# ==================== دوال المساعدة ====================

def clean_old_files():
    """تنظيف الملفات الأقدم من ساعة"""
    now = time.time()
    for file in DOWNLOAD_FOLDER.glob("*"):
        if file.is_file() and now - file.stat().st_mtime > 3600:
            try:
                file.unlink()
            except:
                pass

def get_video_info(url):
    """جلب معلومات الفيديو باستخدام yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                'success': True,
                'title': info.get('title', ''),
                'uploader': info.get('uploader', info.get('channel', '')),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'webpage_url': info.get('webpage_url', url)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

def download_video(url, quality, format, task_id):
    """تنزيل الفيديو في thread منفصل"""
    
    def progress_hook(d):
        """تحديث التقدم"""
        with tasks_lock:
            if task_id not in tasks:
                tasks[task_id] = {}
            
            if d['status'] == 'downloading':
                try:
                    percent = d.get('_percent_str', '0%').replace('%', '').strip()
                    tasks[task_id]['percent'] = float(percent) if percent else 0
                    tasks[task_id]['speed'] = d.get('_speed_str', '...')
                    tasks[task_id]['eta'] = d.get('_eta_str', '--:--')
                    tasks[task_id]['size'] = d.get('_total_bytes_str', '...')
                    tasks[task_id]['status'] = 'downloading'
                except:
                    pass
                    
            elif d['status'] == 'finished':
                tasks[task_id]['percent'] = 100
                tasks[task_id]['status'] = 'finished'
    
    # إعدادات yt-dlp
    format_map = {
        '4k': 'bestvideo[height<=2160]+bestaudio/best',
        '1080p': 'bestvideo[height<=1080]+bestaudio/best',
        '720p': 'bestvideo[height<=720]+bestaudio/best',
        '480p': 'bestvideo[height<=480]+bestaudio/best',
        'mp3': 'bestaudio/best',
        'aac': 'bestaudio/best'
    }
    
    format_quality = quality.lower()
    format_type = format.lower()
    
    output_template = str(DOWNLOAD_FOLDER / f'%(title)s.%(ext)s')
    
    ydl_opts = {
        'outtmpl': output_template,
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
    }
    
    # تحديد الصيغة والجودة
    if format_type in ['mp3', 'aac']:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format_type,
            'preferredquality': '192',
        }]
    else:
        if format_quality in format_map:
            ydl_opts['format'] = format_map[format_quality]
        if format_type != 'mp4':
            ydl_opts['merge_output_format'] = format_type
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # تعديل اسم الملف للصيغ الصوتية
            if format_type in ['mp3', 'aac']:
                filename = filename.rsplit('.', 1)[0] + f'.{format_type}'
            
            with tasks_lock:
                if task_id in tasks:
                    tasks[task_id]['filename'] = filename
                    tasks[task_id]['title'] = info.get('title', 'فيديو')
                    tasks[task_id]['status'] = 'completed'
                    
    except Exception as e:
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = str(e)

# ==================== مسارات API ====================

@app.route('/analyze', methods=['POST'])
def analyze():
    """تحليل الرابط وجلب معلومات الفيديو"""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'success': False, 'error': 'الرابط مطلوب'})
    
    # تنظيف الملفات القديمة
    clean_old_files()
    
    # جلب معلومات الفيديو
    info = get_video_info(url)
    return jsonify(info)

@app.route('/download', methods=['POST'])
def download():
    """بدء تنزيل الفيديو"""
    data = request.json
    url = data.get('url')
    quality = data.get('quality', '1080p')
    format = data.get('format', 'mp4')
    
    if not url:
        return jsonify({'success': False, 'error': 'الرابط مطلوب'})
    
    # إنشاء معرف مهمة فريد
    task_id = str(uuid.uuid4())
    
    with tasks_lock:
        tasks[task_id] = {
            'status': 'starting',
            'percent': 0,
            'task_id': task_id
        }
    
    # بدء التنزيل في thread منفصل
    thread = threading.Thread(
        target=download_video,
        args=(url, quality, format, task_id)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': 'بدأ التنزيل'
    })

@app.route('/progress/<task_id>')
def progress(task_id):
    """بث مباشر لتقدم التنزيل (SSE)"""
    def generate():
        last_status = {}
        while True:
            with tasks_lock:
                task = tasks.get(task_id, {})
            
            if task and task != last_status:
                last_status = task.copy()
                yield f"data: {json.dumps(task)}\n\n"
            
            if task.get('status') in ['completed', 'error']:
                break
                
            time.sleep(0.5)
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/file/<task_id>')
def get_file(task_id):
    """إرسال الملف المحمل إلى المتصفح"""
    with tasks_lock:
        task = tasks.get(task_id, {})
        filename = task.get('filename')
    
    if not filename or not os.path.exists(filename):
        return jsonify({'error': 'الملف غير موجود'}), 404
    
    # إرسال الملف
    response = send_file(
        filename,
        as_attachment=True,
        download_name=os.path.basename(filename)
    )
    
    # حذف الملف بعد الإرسال (اختياري)
    @response.call_on_close
    def cleanup():
        try:
            os.unlink(filename)
        except:
            pass
        with tasks_lock:
            tasks.pop(task_id, None)
    
    return response

@app.route('/status/<task_id>')
def task_status(task_id):
    """الاستعلام عن حالة مهمة"""
    with tasks_lock:
        task = tasks.get(task_id, {})
    return jsonify(task)

@app.route('/ping', methods=['GET', 'POST'])
def ping():
    """اختبار اتصال السيرفر"""
    return jsonify({'success': True, 'message': 'السيرفر شغال ✓'})

# ==================== تشغيل السيرفر ====================
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 AI Downloader Server")
    print("=" * 50)
    print("✅ السيرفر يعمل على: http://localhost:5000")
    print("📁 مجلد التحميلات:", DOWNLOAD_FOLDER.absolute())
    print("=" * 50)
    print("⚠️  تأكد من تثبيت المتطلبات أولاً:")
    print("   pip install flask flask-cors yt-dlp")
    print("=" * 50)
    print("🌐 افتح المتصفح على: http://localhost:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)