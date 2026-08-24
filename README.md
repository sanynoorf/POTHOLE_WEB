# 🛣️ Sistem Deteksi Lubang Jalan – YOLOv8 + ESP32-CAM + Flask

Skripsi: Deteksi Lubang Jalan Menggunakan YOLOv8, ESP32-CAM, dan Website Monitoring

---

## 📁 Struktur Folder

```
Pothole-Web/
├── app.py                  ← Entry point Flask (jalankan ini)
├── best.pt                 ← Model YOLOv8 terlatih (taruh di sini)
├── database.db             ← SQLite (dibuat otomatis)
├── requirements.txt
│
├── database/
│   └── db.py               ← Koneksi + CRUD SQLite
│
├── models/
│   └── detector.py         ← Wrapper YOLOv8
│
├── esp32/
│   └── esp32_pothole_cam.ino  ← Kode Arduino untuk ESP32-CAM
│
├── static/
│   ├── css/style.css
│   ├── uploads/            ← Gambar asli dari ESP32
│   └── detections/         ← Gambar hasil anotasi YOLOv8
│
└── templates/
    ├── dashboard.html      ← Halaman monitoring utama
    └── history.html        ← Riwayat semua deteksi
```

---

## ⚙️ Cara Instalasi dan Menjalankan

### 1. Install dependensi Python
```bash
pip install -r requirements.txt
```

### 2. Taruh file model
Salin `best.pt` ke folder root proyek (sejajar dengan `app.py`).

### 3. Jalankan server Flask
```bash
python app.py
```
Server berjalan di `http://localhost:5000`

### 4. Akses dashboard
Buka browser → `http://localhost:5000/dashboard`

---

## 📡 Konfigurasi ESP32-CAM

Edit file `esp32/esp32_pothole_cam.ino`:
```cpp
const char* WIFI_SSID     = "NAMA_WIFI_ANDA";
const char* WIFI_PASSWORD = "PASSWORD_WIFI_ANDA";
const char* SERVER_URL    = "http://IP_LAPTOP_ANDA:5000/upload";
```

Untuk mencari IP laptop:
- Windows: buka CMD → `ipconfig` → lihat "IPv4 Address"
- Linux/Mac: `ifconfig` atau `ip addr`

Upload kode ke ESP32-CAM menggunakan Arduino IDE.

---

## 🔢 Cara Kerja Penghitungan Per 100 Meter

### Konsep Segmen
Sistem membagi perjalanan survei menjadi **segmen 100 meter**.
Setiap segmen terdiri dari sejumlah frame kamera.

### Rumus Konversi Frame → Segmen
```python
FRAMES_PER_SEGMENT = 6  # sesuaikan dengan kondisi lapangan

def frame_to_segment(frame_number):
    return (frame_number - 1) // FRAMES_PER_SEGMENT + 1
```

### Cara Menentukan `FRAMES_PER_SEGMENT`
```
FRAMES_PER_SEGMENT = 100 meter / (kecepatan_mps × interval_detik)

Contoh:
- Kecepatan kendaraan : 20 km/h ≈ 5.6 m/s
- Interval kamera     : 3 detik
- Jarak per frame     : 5.6 × 3 = 16.8 meter
- Frame per 100m      : 100 / 16.8 ≈ 6 frame
→ FRAMES_PER_SEGMENT = 6
```

### Tingkat Keparahan Otomatis
| Total Lubang per Segmen | Tingkat |
|------------------------|---------|
| 0–4                    | Rendah  |
| 5–9                    | Sedang  |
| ≥ 10                   | Tinggi  |

---

## 🌐 Daftar Endpoint API

| Method | URL               | Fungsi                              |
|--------|-------------------|-------------------------------------|
| GET    | /dashboard        | Halaman monitoring                  |
| GET    | /history          | Riwayat semua deteksi               |
| POST   | /upload           | Terima gambar dari ESP32-CAM        |
| GET    | /api/stats        | JSON statistik ringkasan            |
| GET    | /api/detections   | JSON daftar deteksi terbaru         |
| GET    | /api/segments     | JSON semua segmen 100m              |

### Contoh Request dari ESP32 (HTTP POST /upload)
```
Form data:
  file         : [file gambar .jpg]
  frame_number : 42
  location     : Jl. Raya Bogor KM 5
```

### Contoh Response
```json
{
  "success": true,
  "frame_number": 42,
  "segment_number": 7,
  "pothole_count": 2,
  "confidence_avg": 0.76,
  "image_url": "/static/uploads/frame_0042_20240101_120000.jpg",
  "annotated_url": "/static/detections/det_0042_20240101_120000.jpg",
  "message": "2 lubang terdeteksi di segmen 7"
}
```

---

## 🗃️ Skema Database

### Tabel `detections`
| Kolom           | Tipe    | Keterangan                    |
|-----------------|---------|-------------------------------|
| id              | INTEGER | Primary key                   |
| timestamp       | DATETIME| Waktu deteksi                 |
| frame_number    | INTEGER | Nomor urut frame ESP32        |
| segment_id      | INTEGER | FK ke tabel segments          |
| pothole_count   | INTEGER | Jumlah lubang di frame ini    |
| confidence_avg  | REAL    | Rata-rata confidence score    |
| image_original  | TEXT    | Path gambar asli              |
| image_annotated | TEXT    | Path gambar anotasi           |

### Tabel `segments`
| Kolom          | Tipe    | Keterangan                    |
|----------------|---------|-------------------------------|
| id             | INTEGER | Primary key                   |
| segment_number | INTEGER | Urutan segmen (1, 2, 3…)     |
| total_pothole  | INTEGER | Akumulasi lubang di segmen    |
| total_frames   | INTEGER | Jumlah frame masuk            |
| severity       | TEXT    | Rendah / Sedang / Tinggi      |

---

## 📋 Tahapan Implementasi untuk Skripsi

### Fase 1 – Persiapan (Minggu 1)
- [x] Dataset pothole selesai
- [x] Model YOLOv8 terlatih (best.pt tersedia)
- [ ] Install Python dependencies
- [ ] Uji model: `python -c "from ultralytics import YOLO; m=YOLO('best.pt'); print(m.info())"`

### Fase 2 – Backend Flask (Minggu 2)
- [ ] Jalankan `app.py` dan pastikan server berjalan
- [ ] Uji endpoint `/upload` dengan tool seperti Postman atau cURL
- [ ] Verifikasi data tersimpan di `database.db`

### Fase 3 – Integrasi ESP32-CAM (Minggu 3)
- [ ] Upload kode Arduino ke ESP32-CAM
- [ ] Konfirmasi koneksi WiFi dan pengiriman gambar
- [ ] Pantau Serial Monitor Arduino IDE

### Fase 4 – Website dan Dashboard (Minggu 4)
- [ ] Buka `http://localhost:5000/dashboard`
- [ ] Verifikasi auto-refresh setiap 5 detik bekerja
- [ ] Cek halaman `/history` menampilkan data lengkap

### Fase 5 – Uji Lapangan (Minggu 5-6)
- [ ] Survei jalan sesungguhnya dengan kendaraan
- [ ] Rekam dan analisis akurasi model
- [ ] Bandingkan deteksi otomatis vs manual

### Fase 6 – Penulisan Skripsi (Minggu 7-8)
- [ ] Screenshot dashboard untuk bab hasil
- [ ] Catat metrik: presisi, recall, F1-score
- [ ] Buat tabel perbandingan per segmen

---

## 🔧 Tips Troubleshooting

**ESP32 tidak bisa konek ke WiFi:**
→ Pastikan SSID/password benar. Gunakan hotspot ponsel jika WiFi kampus memblokir.

**Model tidak terdeteksi:**
→ Pastikan `best.pt` ada di folder root (sejajar `app.py`).

**Upload gagal (error 500):**
→ Cek terminal Flask untuk pesan error. Biasanya masalah path atau format gambar.

**Dashboard tidak update:**
→ Buka DevTools browser (F12) → Console, cek error JavaScript.
