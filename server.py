import os
import sys
import json
import shutil
import traceback
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

import backend

app = Flask(__name__, static_folder='web', static_url_path='/web')

# ------------------------------------------------------------------
# 生产级 CORS 配置：支持静态托管 CDN 跨域访问后端 API
# ------------------------------------------------------------------
#   本地开发 / 同源部署  →  保持默认 (通配符 *)，开箱即用
#   前后端分离部署       →  设置环境变量 SPRINTLING_CORS_ORIGINS
#                         多个逗号分隔：https://a.com,https://b.com
#                         例（PowerShell）：
#                           $env:SPRINTLING_CORS_ORIGINS="https://sprintling.github.io,http://localhost:3000"
#                           python server.py
# ------------------------------------------------------------------
_ALLOWED_ORIGINS = os.environ.get("SPRINTLING_CORS_ORIGINS", "").strip()
if _ALLOWED_ORIGINS:
    _origins_list = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": _origins_list}},
         supports_credentials=False,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"])
    print(f"[DEPLOY] CORS restricted to allow origins: {_origins_list}")
else:
    # 默认开发/一体化模式：允许任意来源（配合静态托管 CDN 的临时测试）
    CORS(app, resources={r"/api/*": {"origins": "*"}},
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"])
    print("[DEPLOY] CORS default: allow any origin for /api/* (set SPRINTLING_CORS_ORIGINS in prod)")

HISTORY_DIR = "history_data"
if not os.path.exists(HISTORY_DIR):
    os.makedirs(HISTORY_DIR)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

processing_status = {}
_model_loaded = False


def preload_model():
    """Preload YOLO model on startup so first request won't be stuck"""
    global _model_loaded
    if _model_loaded:
        return
    try:
        import torch
        device = 'CUDA (GPU)' if torch.cuda.is_available() else 'CPU (slow)'
        print(f"[INFO] PyTorch device detected: {device}")
        if not torch.cuda.is_available():
            print(f"[WARNING] CUDA is NOT available! Processing will use CPU and may be EXTREMELY slow.")
            print(f"[WARNING]   - 5-second video on CPU: ~3-8 minutes")
            print(f"[WARNING]   - 10-second video on CPU: ~10-20 minutes")
            print(f"[WARNING] Install NVIDIA CUDA + PyTorch GPU version for 10-50x speedup.")
        print("[INFO] Loading YOLO pose model (this may take a few seconds the first time)...")
        backend.get_yolo_model()
        print("[INFO] YOLO pose model loaded successfully.")
        _model_loaded = True
    except Exception as e:
        print(f"[ERROR] Failed to preload model: {e}")
        print(traceback.format_exc())


def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def get_work_dir(timestamp):
    return os.path.join(HISTORY_DIR, timestamp)


@app.route('/')
def index():
    return send_from_directory('web', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('web', path)


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name', '').strip()
    event = data.get('event', '100m')
    pb = data.get('pb', '')
    if not name:
        return jsonify({'success': False, 'message': 'Please enter a name or choose to skip.'}), 400
    return jsonify({'success': True, 'message': 'Registered successfully', 'athlete': {'name': name, 'event': event, 'pb': pb}})


@app.route('/api/history', methods=['GET'])
def get_history():
    records = sorted([d for d in os.listdir(HISTORY_DIR) if os.path.isdir(os.path.join(HISTORY_DIR, d))], reverse=True)
    return jsonify({'records': records})


@app.route('/api/history/<timestamp>', methods=['GET'])
def get_record(timestamp):
    work_dir = get_work_dir(timestamp)
    if not os.path.exists(work_dir):
        return jsonify({'success': False, 'message': 'Record not found'}), 404

    result = {'timestamp': timestamp, 'files': []}
    for f in os.listdir(work_dir):
        file_path = os.path.join(work_dir, f)
        if os.path.isfile(file_path):
            result['files'].append(f)

    payload_path = os.path.join(work_dir, 'payload.json')
    if os.path.exists(payload_path):
        with open(payload_path, 'r', encoding='utf-8') as f:
            result['payload'] = json.load(f)

    report_md = os.path.join(work_dir, 'report.md')
    if os.path.exists(report_md):
        with open(report_md, 'r', encoding='utf-8') as f:
            result['report_md'] = f.read()

    return jsonify(result)


@app.route('/api/history/<timestamp>', methods=['DELETE'])
def delete_record(timestamp):
    work_dir = get_work_dir(timestamp)
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
        return jsonify({'success': True, 'message': 'Record deleted'})
    return jsonify({'success': False, 'message': 'Record not found'}), 404


@app.route('/api/download/<timestamp>/<filename>', methods=['GET'])
def download_file(timestamp, filename):
    work_dir = get_work_dir(timestamp)
    file_path = os.path.join(work_dir, filename)
    if os.path.exists(file_path):
        mimetypes = {
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'webm': 'video/webm',
            'mp4': 'video/mp4',
            'png': 'image/png',
            'json': 'application/json',
            'md': 'text/markdown'
        }
        ext = filename.split('.')[-1] if '.' in filename else ''
        return send_file(file_path, as_attachment=True, mimetype=mimetypes.get(ext, 'application/octet-stream'))
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/process', methods=['POST'])
def process_videos():
    if 'start_video' not in request.files and 'maxvel_video' not in request.files:
        return jsonify({'success': False, 'message': 'No video files uploaded'}), 400

    athlete_info = {}
    athlete_str = request.form.get('athlete_info', '')
    if athlete_str:
        try:
            athlete_info = json.loads(athlete_str)
        except:
            pass

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = get_work_dir(timestamp)
    os.makedirs(work_dir)

    raw_start = os.path.join(work_dir, "raw_start.mp4")
    raw_maxvel = os.path.join(work_dir, "raw_maxvel.mp4")
    proc_start = os.path.join(work_dir, "proc_start.webm")
    proc_maxvel = os.path.join(work_dir, "proc_maxvel.webm")
    json_start = os.path.join(work_dir, "data_start.json")
    json_maxvel = os.path.join(work_dir, "data_maxvel.json")
    payload_path = os.path.join(work_dir, "payload.json")
    img_path = os.path.join(work_dir, "chart.png")
    report_md = os.path.join(work_dir, "report.md")
    report_docx = os.path.join(work_dir, "report.docx")

    has_start = 'start_video' in request.files
    has_maxvel = 'maxvel_video' in request.files

    if has_start:
        start_file = request.files['start_video']
        if start_file.filename:
            start_file.save(raw_start)

    if has_maxvel:
        maxvel_file = request.files['maxvel_video']
        if maxvel_file.filename:
            maxvel_file.save(raw_maxvel)

    def run_processing():
        status_key = timestamp
        try:
            log(f"[{timestamp}] Processing started. has_start={has_start}, has_maxvel={has_maxvel}")

            if not _model_loaded:
                processing_status[status_key] = {
                    'progress': 5,
                    'stage': 'Loading YOLO model (first run, ~10-30s)...'
                }
                preload_model()

            processing_status[status_key] = {
                'progress': 12,
                'stage': 'Initializing video decoder...'
            }

            if has_start and os.path.exists(raw_start):
                fsize_mb = os.path.getsize(raw_start) / (1024 * 1024)
                log(f"[{timestamp}] Start video saved: {fsize_mb:.1f} MB. Running YOLO inference (CPU mode takes several minutes)...")
                processing_status[status_key] = {
                    'progress': 25,
                    'stage': f'Processing Start Phase (CPU, {fsize_mb:.0f}MB) — this may take 5-20 min on CPU...'
                }
                backend.process_full_kinematics(raw_start, proc_start, json_start)
                log(f"[{timestamp}] Start phase completed.")

            if has_maxvel and os.path.exists(raw_maxvel):
                fsize_mb = os.path.getsize(raw_maxvel) / (1024 * 1024)
                log(f"[{timestamp}] MaxVel video saved: {fsize_mb:.1f} MB. Running YOLO inference...")
                processing_status[status_key] = {
                    'progress': 45,
                    'stage': f'Processing Max Velocity Phase (CPU, {fsize_mb:.0f}MB) — please wait...'
                }
                backend.process_full_kinematics(raw_maxvel, proc_maxvel, json_maxvel)
                log(f"[{timestamp}] MaxVel phase completed.")

            processing_status[status_key] = {
                'progress': 70,
                'stage': 'Fusing Data & Generating Dashboard...'
            }
            start_path = json_start if os.path.exists(json_start) else ''
            maxvel_path = json_maxvel if os.path.exists(json_maxvel) else ''
            backend.extract_combined_features(start_path, maxvel_path, payload_path)
            backend.plot_combined_dashboard(start_path, maxvel_path, img_path)
            log(f"[{timestamp}] Feature extraction and dashboard completed.")

            processing_status[status_key] = {
                'progress': 85,
                'stage': 'AI Generating Actionable Protocol (calling DeepSeek AI)...'
            }

            # 双重兜底：无论内部发生什么异常，都确保 report.md 被写入文件
            # 避免出现 payload/chart 存在但 report 完全缺失的"空白 Tab"情况
            try:
                report_result = backend.generate_training_report(payload_path, report_md, athlete_info)
                log(f"[{timestamp}] AI report result length: {len(str(report_result))} chars")
                if not os.path.exists(report_md):
                    # 极罕见情况：函数返回但文件未写出 -> 强制兜底写入
                    safe_msg = "# AI 教练分析警告\n\n报告文件未自动写出，以下为系统恢复的原始内容：\n\n" + str(report_result or "(empty)")
                    with open(report_md, "w", encoding="utf-8") as f:
                        f.write(safe_msg)
                    log(f"[{timestamp}] ⚠ Safety fallback: wrote report.md manually")
            except Exception as ai_err:
                ai_tb = traceback.format_exc()
                log(f"[{timestamp}] ❌ AI step raised exception (safety fallback): {ai_err}")
                fallback_msg = (
                    "# AI 教练分析错误\n\n"
                    f"**System Exception**: {str(ai_err)}\n\n"
                    "```\n" + ai_tb + "\n```\n\n"
                    "> 请在历史记录中点击「AI Protocol」Tab 的 Regenerate 按钮重新生成报告。"
                )
                try:
                    with open(report_md, "w", encoding="utf-8") as f:
                        f.write(fallback_msg)
                except Exception as io_err:
                    log(f"[{timestamp}] FATAL: Cannot write report.md: {io_err}")

            # Word 导出：独立 try，避免 docx 异常反向影响 report.md
            try:
                if os.path.exists(report_md):
                    backend.create_docx_report(report_md, report_docx)
                    log(f"[{timestamp}] AI report + docx completed. All done.")
                else:
                    log(f"[{timestamp}] Skip docx (report.md still missing).")
            except Exception as docx_err:
                log(f"[{timestamp}] Warning: docx creation failed {docx_err}")

            processing_status[status_key] = {'progress': 100, 'stage': '✅ Complete!', 'done': True}
        except Exception as e:
            tb = traceback.format_exc()
            log(f"[{timestamp}] ERROR during processing: {e}")
            log(tb)
            processing_status[status_key] = {
                'progress': 0,
                'stage': f'Error: {str(e)}',
                'error': True,
                'traceback': tb
            }

    thread = threading.Thread(target=run_processing)
    thread.start()

    return jsonify({
        'success': True,
        'timestamp': timestamp,
        'message': 'Processing started',
        'has_start': has_start and os.path.exists(raw_start),
        'has_maxvel': has_maxvel and os.path.exists(raw_maxvel)
    })


@app.route('/api/status/<timestamp>', methods=['GET'])
def get_status(timestamp):
    return jsonify(processing_status.get(timestamp, {'progress': 0, 'stage': 'Waiting...'}))


@app.route('/api/history/<timestamp>/files', methods=['GET'])
def get_record_files(timestamp):
    work_dir = get_work_dir(timestamp)
    if not os.path.exists(work_dir):
        return jsonify({'success': False, 'message': 'Record not found'}), 404

    files = {}
    for f in os.listdir(work_dir):
        file_path = os.path.join(work_dir, f)
        if os.path.isfile(file_path):
            if f.startswith('proc_') and (f.endswith('.webm') or f.endswith('.mp4')):
                files[f] = {'type': 'video', 'url': f'/api/serve/{timestamp}/{f}'}
            elif f == 'chart.png':
                files[f] = {'type': 'image', 'url': f'/api/serve/{timestamp}/{f}'}
            elif f == 'payload.json':
                files[f] = {'type': 'json', 'url': f'/api/serve/{timestamp}/{f}'}
            elif f == 'report.md':
                files[f] = {'type': 'markdown', 'url': f'/api/serve/{timestamp}/{f}'}
            elif f == 'report.docx':
                files[f] = {'type': 'docx', 'url': f'/api/download/{timestamp}/{f}'}

    return jsonify({'success': True, 'files': files})


@app.route('/api/serve/<timestamp>/<filename>', methods=['GET'])
def serve_file(timestamp, filename):
    work_dir = get_work_dir(timestamp)
    file_path = os.path.join(work_dir, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/history/<timestamp>/regenerate_report', methods=['POST'])
def regenerate_ai_report(timestamp):
    """针对历史记录补生成缺失的 AI 教练报告 (payload.json 存在即可)"""
    work_dir = get_work_dir(timestamp)
    if not os.path.exists(work_dir):
        return jsonify({'success': False, 'message': 'Record not found'}), 404

    payload_path = os.path.join(work_dir, 'payload.json')
    report_md = os.path.join(work_dir, 'report.md')
    report_docx = os.path.join(work_dir, 'report.docx')

    if not os.path.exists(payload_path):
        return jsonify({
            'success': False,
            'message': 'Cannot regenerate: payload.json is missing. Please run the full analysis pipeline from scratch.'
        }), 400

    athlete_info = {}
    try:
        body = request.get_json(silent=True) or {}
        athlete_info = body.get('athlete_info', {})
    except Exception:
        pass

    try:
        log(f"[{timestamp}] 🧠 Regenerating AI report on-demand...")
        result = backend.generate_training_report(payload_path, report_md, athlete_info)
        result_len = len(str(result)) if result else 0
        log(f"[{timestamp}] ✅ Report regenerated ({result_len} chars). Creating docx...")

        if os.path.exists(report_md):
            try:
                backend.create_docx_report(report_md, report_docx)
            except Exception as docx_err:
                log(f"[{timestamp}] Warning: docx failed during regenerate: {docx_err}")

        return jsonify({
            'success': True,
            'message': 'Report regenerated successfully',
            'length': result_len,
            'has_docx': os.path.exists(report_docx)
        })

    except Exception as e:
        tb = traceback.format_exc()
        log(f"[{timestamp}] ❌ Regenerate failed: {e}")
        log(tb)
        return jsonify({
            'success': False,
            'message': str(e),
            'traceback': tb
        }), 500


if __name__ == '__main__':
    print("=" * 50)
    print("  Sprint Analytics AI - Web Server")
    print("  Open http://localhost:5000 in your browser")
    print("  Press Ctrl+C to stop the server")
    print("=" * 50)
    print()
    preload_model()
    print()
    print("[READY] Server starting. You may now upload videos from the web UI.")
    print("        Monitor this console for processing progress and any errors.")
    print()
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
