"""
models/detector.py
Wrapper untuk YOLOv8 – memuat model best.pt dan menjalankan deteksi
pada gambar yang diterima dari ESP32-CAM.
"""

import os
import cv2
import numpy as np
from ultralytics import YOLO

# Path model relatif terhadap root proyek
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'best.pt')

# Confidence threshold – turunkan jika terlalu banyak miss, naikkan jika banyak false positive
CONF_THRESHOLD = 0.40


class PotholeDetector:
    """Singleton wrapper untuk model YOLOv8."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
        return cls._instance

    def load(self):
        """Muat model sekali saat server start. Aman dipanggil berkali-kali."""
        if self._model is None:
            if not os.path.exists(MODEL_PATH):
                raise FileNotFoundError(
                    f"Model tidak ditemukan di: {MODEL_PATH}\n"
                    "Pastikan file best.pt ada di root folder proyek."
                )
            print(f"[Detector] Memuat model dari {MODEL_PATH} ...")
            self._model = YOLO(MODEL_PATH)
            print("[Detector] Model siap.")
        return self

    def detect(self, image_path: str, save_annotated_path: str) -> dict:
        """
        Jalankan deteksi YOLOv8 pada satu gambar.

        Parameters
        ----------
        image_path          : path gambar asli dari ESP32
        save_annotated_path : path tujuan gambar anotasi (bounding box)

        Returns
        -------
        dict berisi:
            pothole_count   – jumlah bounding box terdeteksi
            confidence_avg  – rata-rata confidence (0.0 jika tidak ada)
            detections      – list detail tiap box [{'confidence', 'x1','y1','x2','y2'}]
            annotated_path  – path gambar hasil anotasi
        """
        if self._model is None:
            self.load()

        # Baca gambar
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Gambar tidak dapat dibaca: {image_path}")

        # Jalankan inferensi
        results = self._model(img, conf=CONF_THRESHOLD, verbose=False)[0]

        detections = []
        confidences = []

        for box in results.boxes:
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            detections.append({
                'confidence': round(conf, 3),
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2
            })
            confidences.append(conf)

            # Gambar bounding box manual agar kontrol tampilan penuh
            color = _severity_color(conf)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            label = f"Pothole {conf:.0%}"
            cv2.putText(img, label, (x1, max(y1 - 8, 0)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # Tambahkan info ringkasan di pojok kanan atas
        summary = f"Terdeteksi: {len(detections)} lubang"
        cv2.putText(img, summary, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # Simpan gambar anotasi
        os.makedirs(os.path.dirname(save_annotated_path), exist_ok=True)
        cv2.imwrite(save_annotated_path, img)

        avg_conf = round(float(np.mean(confidences)), 3) if confidences else 0.0

        return {
            'pothole_count':  len(detections),
            'confidence_avg': avg_conf,
            'detections':     detections,
            'annotated_path': save_annotated_path
        }


def _severity_color(confidence: float) -> tuple:
    """
    Warna bounding box berdasarkan confidence:
    hijau (tinggi) → kuning (sedang) → merah (rendah).
    Format: BGR untuk OpenCV.
    """
    if confidence >= 0.70:
        return (0, 220, 0)     # Hijau
    elif confidence >= 0.50:
        return (0, 200, 255)   # Kuning (BGR)
    else:
        return (0, 0, 220)     # Merah


# Singleton global – import dan gunakan di app.py
detector = PotholeDetector()
