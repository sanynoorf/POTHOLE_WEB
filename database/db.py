"""
database/db.py - Versi Final dengan dukungan koordinat GPS + timestamp lokal (WIB) + delete
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur  = conn.cursor()
    # Menggunakan datetime('now', 'localtime') agar otomatis menggunakan waktu WIB laptop Mac Anda
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       DATETIME DEFAULT (datetime('now', 'localtime')),
            frame_number    INTEGER DEFAULT 0,
            segment_id      INTEGER DEFAULT 1,
            pothole_count   INTEGER NOT NULL DEFAULT 0,
            confidence_avg  REAL,
            image_original  TEXT,
            image_annotated TEXT,
            location_note   TEXT,
            lat             REAL,
            lng             REAL
        )
    """)
    try:
        cur.execute("ALTER TABLE detections ADD COLUMN lat REAL")
    except: pass
    try:
        cur.execute("ALTER TABLE detections ADD COLUMN lng REAL")
    except: pass
    conn.commit()
    conn.close()
    print(f"[DB] Database siap di: {DB_PATH}")


def insert_detection(frame_number, segment_id, pothole_count,
                     confidence_avg, image_original, image_annotated,
                     location_note=None, lat=None, lng=None, timestamp=None): # <-- Pastikan ada ', timestamp=None' di sini!
    conn = get_connection()
    cur  = conn.cursor()
    
    # Jika Flask mengirimkan data timestamp (WIB), pakai itu. Jika tidak, biarkan default SQLite (UTC).
    if timestamp:
        cur.execute("""
            INSERT INTO detections
                (frame_number, segment_id, pothole_count, confidence_avg,
                 image_original, image_annotated, location_note, lat, lng, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (frame_number, segment_id, pothole_count, confidence_avg,
              image_original, image_annotated, location_note, lat, lng, timestamp))
    else:
        cur.execute("""
            INSERT INTO detections
                (frame_number, segment_id, pothole_count, confidence_avg,
                 image_original, image_annotated, location_note, lat, lng)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (frame_number, segment_id, pothole_count, confidence_avg,
              image_original, image_annotated, location_note, lat, lng))
              
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_all_detections(limit=50):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM detections ORDER BY timestamp DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_detections_with_coords(limit=500):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM detections
        WHERE lat IS NOT NULL AND lng IS NOT NULL
        ORDER BY timestamp DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn  = get_connection()
    stats = conn.execute("""
        SELECT
            COUNT(*)                         AS total_frames,
            COALESCE(SUM(pothole_count), 0)  AS total_pothole,
            COALESCE(AVG(confidence_avg), 0) AS avg_confidence,
            COALESCE(MAX(pothole_count), 0)  AS max_per_frame
        FROM detections
    """).fetchone()
    conn.close()
    return dict(stats) if stats else {}


def delete_detection(detection_id):
    """Hapus satu deteksi berdasarkan ID."""
    conn = get_connection()
    conn.execute("DELETE FROM detections WHERE id = ?", (detection_id,))
    conn.commit()
    conn.close()


def delete_all_detections():
    """Hapus semua data deteksi."""
    conn = get_connection()
    conn.execute("DELETE FROM detections")
    conn.commit()
    conn.close()