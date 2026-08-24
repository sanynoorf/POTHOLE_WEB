"""
app.py – PotholeWatch Versi Final (Bypass Live Stream + Waktu WIB)
Flask + YOLOv8 + ESP32-CAM + GPS iPhone + Peta
"""

import os
import socket
import time
import shutil
from datetime import datetime
from ultralytics import YOLO
import pytz  # ← Mengatur zona waktu agar jam sesuai (WIB)

latest_frame = None
from flask import Flask, request, jsonify, render_template

from database.db import (init_db, insert_detection, get_all_detections,
                          get_detections_with_coords, get_stats, get_connection)

# ─── OVERRIDE INSERT DETECTION (FIX TIMESTAMP WIB) ────────────────────────────
def insert_detection(frame_number, segment_id, pothole_count,
                     confidence_avg, image_original, image_annotated,
                     location_note=None, lat=None, lng=None, timestamp=None):
    conn = get_connection()
    cur  = conn.cursor()
    
    # Otomatis gunakan waktu WIB jika timestamp tidak dikirim
    if not timestamp:
        timestamp = datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S')
    
    cur.execute("""
        INSERT INTO detections
            (frame_number, segment_id, pothole_count, confidence_avg,
             image_original, image_annotated, location_note, lat, lng, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (frame_number, segment_id, pothole_count, confidence_avg,
          image_original, image_annotated, location_note, lat, lng, timestamp))
              
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id

from models.detector import detector

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER    = os.path.join(BASE_DIR, 'static', 'uploads')
DETECTION_FOLDER = os.path.join(BASE_DIR, 'static', 'detections')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DETECTION_FOLDER'] = DETECTION_FOLDER

os.makedirs(UPLOAD_FOLDER,    exist_ok=True)
os.makedirs(DETECTION_FOLDER, exist_ok=True)

# Definisikan timezone Asia/Jakarta (WIB)
WIB = pytz.timezone('Asia/Jakarta')

# ─── State Global ─────────────────────────────────────────────────────────────
stream_active = False
stream_start_time = None   # waktu saat stream dimulai

gps_state = {
    'total_dist':    0.0,
    'total_holes':   0,
    'segment_count': 0,
    'last_lat':      None,
    'last_lng':      None,
}

# ─── Fallback Model YOLO ──────────────────────────────────────────────────────
model_path = os.path.join(BASE_DIR, 'best.pt')
try:
    safety_model = YOLO(model_path)
    print("[SUCCESS] Safety Model YOLO berhasil dimuat!")
except Exception as e:
    print(f"[WARNING] Gagal memuat safety model YOLO dari {model_path}: {e}")
    safety_model = None

# ─── Helper ───────────────────────────────────────────────────────────────────
def get_status(count):
    if count == 0:   return {'label': 'Aman',    'color': 'green'}
    elif count <= 2: return {'label': 'Waspada', 'color': 'yellow'}
    else:            return {'label': 'Bahaya',  'color': 'red'}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

def detect_potholes(image_path):
    active_model = None
    if 'detector' in globals() and hasattr(detector, 'model') and detector.model is not None:
        active_model = detector.model
    else:
        active_model = safety_model

    if active_model is None:
        raise ValueError("Model YOLO tidak terdeteksi! Pastikan file best.pt diletakkan di folder proyek Anda.")

    results = active_model(image_path)
    result = results[0]
    
    pothole_count = len(result.boxes)
    confidences = result.boxes.conf.tolist() if pothole_count > 0 else []
    confidence_avg = float(sum(confidences) / len(confidences)) if confidences else 0.0
    
    filename = os.path.basename(image_path).replace("ori_", "det_")
    annotated_path = os.path.join(DETECTION_FOLDER, filename)
    
    result.save(filename=annotated_path)
    
    return {
        "pothole_count": pothole_count,
        "confidence_avg": round(confidence_avg, 2),
        "annotated_path": annotated_path
    }

# ─── Startup ──────────────────────────────────────────────────────────────────
with app.app_context():
    init_db()
    try:
        detector.load()
    except FileNotFoundError as e:
        print(f"[WARNING] {e}")

# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/gps')
def gps_page():
    return render_template('gps.html')

@app.route('/map')
def map_page():
    return render_template('map.html')

@app.route('/history')
def history_page():
    return render_template('history.html')

# ══════════════════════════════════════════════════════════════════════════════
# STREAM CONTROL (KONTROL STREAM)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/stream/start', methods=['POST'])
def stream_start():
    global stream_active, stream_start_time, latest_frame
    stream_active     = True
    stream_start_time = datetime.now(WIB)
    latest_frame      = None  # reset foto lama agar tidak muncul di stream baru
    print(f"[Stream] AKTIF sejak {stream_start_time}")
    return jsonify({'streaming': True, 'start_time': stream_start_time.isoformat()})

@app.route('/api/stream/stop', methods=['POST'])
def stream_stop():
    global stream_active, latest_frame
    stream_active = False
    latest_frame  = None
    print("[Stream] BERHENTI")
    return jsonify({'streaming': False})
 
@app.route('/api/latest/stream')
def api_latest_stream():
    global latest_frame
    
    if latest_frame is None:
        return jsonify({'available': False})
 
    count = latest_frame.get('pothole_count', 0)
    status = get_status(count)
 
    return jsonify({
        'available':     True,
        'pothole_count': count,
        'status':        status['label'],
        'color':         status['color'],
        'confidence':    latest_frame.get('confidence_avg'),
        'timestamp':     "Real-Time",
        'annotated_url': latest_frame.get('image_url'), 
        'lat':           latest_frame.get('lat'),
        'lng':           latest_frame.get('lng'),
    })

# ══════════════════════════════════════════════════════════════════════════════
# JALUR 1: UPLOAD DARI ESP32-CAM (OTOMATIS / LIVE STREAM)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/upload', methods=['POST'])
def upload_esp32():
    global latest_frame, gps_state, stream_active
    
    if not stream_active:
        return jsonify({'status': 'ignored', 'message': 'Stream belum aktif'}), 200
    
    file = request.files.get('file') or request.files.get('image')
    frame_raw = request.form.get('frame_number') or request.form.get('frame', '0')
    
    if not file:
        print("[Warning] Flask menerima request tapi tidak menemukan file gambar!")
        return jsonify({"status": "fail", "message": "No image partition found"}), 400
        
    time_suffix = int(time.time())
    ori_name = f"ori_esp32_{frame_raw}_{time_suffix}.jpg"
    ori_path = os.path.join(UPLOAD_FOLDER, ori_name)
    file.save(ori_path)

    try:
        result = detect_potholes(ori_path)
        count = result.get('pothole_count', 0)
        conf_avg = result.get('confidence_avg', 0.0)
        annotated_source = result.get('annotated_path')
    except Exception as e:
        print(f"[Error 500 - YOLO ESP32] Deteksi Gagal: {e}")
        return jsonify({"status": "fail", "message": f"Detection model error: {e}"}), 500

    det_name = f"det_esp32_{frame_raw}_{time_suffix}.jpg"
    det_path = os.path.join(DETECTION_FOLDER, det_name)
    
    if annotated_source and os.path.exists(annotated_source):
        if annotated_source != det_path:
            try:
                shutil.copy(annotated_source, det_path)
                os.remove(annotated_source)
            except Exception as e:
                print(f"[Warning File System] Gagal memindahkan file, fallback salin: {e}")
                shutil.copy(ori_path, det_path)
    else:
        shutil.copy(ori_path, det_path)

    lat = gps_state.get('last_lat')
    lng = gps_state.get('last_lng')

    try:
        insert_detection(
            frame_number   = int(frame_raw) if str(frame_raw).isdigit() else 0,
            segment_id     = gps_state.get('segment_count', 1),
            pothole_count  = count,
            confidence_avg = conf_avg,
            image_original = f"uploads/{ori_name}",
            image_annotated= f"detections/{det_name}",
            location_note  = 'esp32_cam',
            lat            = lat,
            lng            = lng,
            timestamp      = datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S') 
        )
    except Exception as e:
        print(f"[Error 500 - Database] Gagal menyimpan ke Database: {e}")
        return jsonify({"status": "fail", "message": f"Database error: {e}"}), 500

    latest_frame = {
        "pothole_count": count,
        "confidence_avg": conf_avg,
        "image_url": f"/static/detections/{det_name}",
        "lat": lat,
        "lng": lng
    }

    print(f"[Sukses] Frame {frame_raw} diproses! Menemukan {count} lubang.")
    return jsonify({"status": "success", "potholes": count}), 200

# ══════════════════════════════════════════════════════════════════════════════
# JALUR 2: UPLOAD MANUAL VIA WEB DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/upload/manual', methods=['POST'])
@app.route('/upload_manual', methods=['POST'])
def upload_manual():
    global latest_frame
    
    # Fleksibel membaca berbagai alternatif nama key file dari frontend
    file = request.files.get('image') or request.files.get('file') or request.files.get('image_file')
    lat  = request.form.get('lat')
    lng  = request.form.get('lng')

    try:
        lat = float(lat) if lat else None
        lng = float(lng) if lng else None
    except ValueError:
        lat, lng = None, None

    if not file:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    timestamp_str = str(int(time.time()))
    ori_name = f"ori_manual_{timestamp_str}.jpg"
    ori_path = os.path.join(UPLOAD_FOLDER, ori_name)
    file.save(ori_path)

    try:
        result = detect_potholes(ori_path)
        count = result['pothole_count']
        conf_avg = result['confidence_avg']
        annotated_source = result['annotated_path']
    except Exception as e:
        print(f"[Error 500 - YOLO Manual] Deteksi Gagal: {e}")
        return jsonify({"status": "error", "message": f"Model error: {e}"}), 500

    det_name = f"det_manual_{timestamp_str}.jpg"
    det_path = os.path.join(DETECTION_FOLDER, det_name)
    
    if annotated_source and os.path.exists(annotated_source):
        if annotated_source != det_path:
            try:
                shutil.copy(annotated_source, det_path)
                os.remove(annotated_source)
            except Exception as e:
                print(f"[Warning File System] Gagal memindahkan hasil manual, fallback salin: {e}")
                shutil.copy(ori_path, det_path)
    else:
        shutil.copy(ori_path, det_path)

    try:
        insert_detection(
            frame_number   = 0,
            segment_id     = 1,
            pothole_count  = count,
            confidence_avg = conf_avg,
            image_original = f"uploads/{ori_name}",
            image_annotated= f"detections/{det_name}",
            location_note  = 'manual',
            lat            = lat,
            lng            = lng,
            timestamp      = datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S')
        )
    except Exception as e:
        print(f"[Error 500 - DB Manual] Gagal simpan ke DB: {e}")
        return jsonify({"status": "error", "message": f"Database error: {e}"}), 500

    latest_frame = {
        "pothole_count": count,
        "confidence_avg": conf_avg,
        "image_url": f"/static/detections/{det_name}",
        "lat": lat,
        "lng": lng
    }

    return jsonify({
        "status": "success", 
        "potholes": count,
        "pothole_count": count,
        "poles": count,
        "confidence": conf_avg,
        "confidence_avg": conf_avg,
        "annotated_url": f"/static/detections/{det_name}"
    }), 200

# ══════════════════════════════════════════════════════════════════════════════
# API DATA
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/latest')
def api_latest():
    rows = get_all_detections(limit=1)
    if not rows:
        return jsonify({'available': False})
    d      = rows[0]
    count  = d['pothole_count']
    status = get_status(count)
    return jsonify({
        'available':     True,
        'pothole_count': count,
        'potholes':      count,
        'status':        status['label'],
        'color':         status['color'],
        'confidence_avg': d.get('confidence_avg'),
        'confidence':    d.get('confidence_avg'),
        'timestamp':     d['timestamp'],
        'annotated_url': f"/static/{d['image_annotated']}" if d['image_annotated'] else None,
        'lat':           d.get('lat'),
        'lng':           d.get('lng'),
    })

@app.route('/api/history')
def api_history():
    rows   = get_all_detections(limit=1000)
    result = []
    for d in rows:
        s = get_status(d['pothole_count'])
        result.append({
            'id':             d['id'],
            'pothole_count':  d['pothole_count'],
            'status':         s['label'],
            'color':          s['color'],
            'timestamp':      d['timestamp'],
            'confidence_avg': d.get('confidence_avg'),
            'lat':            d.get('lat'),
            'lng':            d.get('lng'),
            'annotated_url':  f"/static/{d['image_annotated']}" if d['image_annotated'] else None,
            'location_note':  d.get('location_note'),
        })
    return jsonify(result)

@app.route('/api/map/markers')
def api_map_markers():
    rows   = get_detections_with_coords(limit=500)
    result = []
    for d in rows:
        if d['pothole_count'] == 0:
            continue
        s = get_status(d['pothole_count'])
        result.append({
            'id':            d['id'],
            'lat':           d['lat'],
            'lng':           d['lng'],
            'pothole_count': d['pothole_count'],
            'status':        s['label'],
            'color':         s['color'],
            'timestamp':     d['timestamp'],
            'confidence_avg': d.get('confidence_avg'),
            'annotated_url': f"/static/{d['image_annotated']}" if d['image_annotated'] else None,
        })
    return jsonify(result)

# ══════════════════════════════════════════════════════════════════════════════
# GPS DARI IPHONE
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/gps', methods=['POST'])
def api_gps():
    global gps_state
    data      = request.get_json() or {}
    lat       = data.get('lat')
    lng       = data.get('lng')
    dist_step = data.get('dist_step', 0)

    if lat is None or lng is None:
        return jsonify({'success': False, 'message': 'Koordinat tidak valid'}), 400

    gps_state['total_dist'] += dist_step
    new_segment = int(gps_state['total_dist'] // 100)
    if new_segment > gps_state['segment_count']:
        gps_state['segment_count'] = new_segment
        print(f"[GPS] Segmen {new_segment} | Jarak: {gps_state['total_dist']:.0f}m")

    gps_state['last_lat'] = lat
    gps_state['last_lng'] = lng

    return jsonify({
        'success':       True,
        'total_dist':    round(gps_state['total_dist']),
        'total_holes':   gps_state['total_holes'],
        'segment_count': gps_state['segment_count'],
    })

@app.route('/api/gps/reset', methods=['POST'])
def api_gps_reset():
    global gps_state
    gps_state = {'total_dist':0.0,'total_holes':0,'segment_count':0,'last_lat':None,'last_lng':None}
    return jsonify({'success': True})

@app.route('/api/gps/status')
def api_gps_status():
    """
    Status GPS + total lubang diambil langsung dari database SQLite
    agar selalu akurat (persisten meskipun gps_state ter-reset).
    """
    total_holes = 0
    try:
        conn = get_connection()
        result = conn.execute("""
            SELECT COALESCE(SUM(pothole_count), 0) as total
            FROM detections
            WHERE lat IS NOT NULL AND pothole_count > 0
        """).fetchone()
        total_holes = result['total'] if result else 0
        conn.close()
    except Exception as e:
        print(f"[Warning GPS Status DB] Gagal menghitung total lubang: {e}")
        total_holes = gps_state.get('total_holes', 0)

    return jsonify({
        'total_dist':    round(gps_state['total_dist']),
        'total_holes':   total_holes,
        'segment_count': gps_state['segment_count'],
        'last_lat':      gps_state['last_lat'],
        'last_lng':      gps_state['last_lng'],
    })

# ══════════════════════════════════════════════════════════════════════════════
# HAPUS DATA
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/delete/<int:detection_id>', methods=['DELETE'])
def api_delete_one(detection_id):
    try:
        conn = get_connection()
        conn.execute("DELETE FROM detections WHERE id = ?", (detection_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete/all', methods=['DELETE'])
def api_delete_all():
    try:
        conn = get_connection()
        conn.execute("DELETE FROM detections")
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

def _run_http():
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

def _run_https():
    app.run(host='0.0.0.0', port=5443, debug=False,
            use_reloader=False, ssl_context='adhoc')

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

if __name__ == '__main__':
    import threading
    ip = get_local_ip()

    print("=" * 55)
    print("  PotholeWatch – Siap Pengujian (WIB Active)")
    print("=" * 55)
    print(f"  Dashboard  : http://localhost:5001/dashboard")
    print(f"  Riwayat    : http://localhost:5001/history")
    print(f"  Peta       : http://localhost:5001/map")
    print(f"  GPS iPhone : https://{ip}:5443/gps")
    print(f"  ESP32 URL  : http://{ip}:5001/upload")
    print("=" * 55)

    t = threading.Thread(target=_run_https, daemon=True)
    t.start()
    _run_http()