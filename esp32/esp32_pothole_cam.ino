/*
 * esp32/receiver.py → ini adalah kode untuk ESP32-CAM (Arduino .ino)
 * Simpan sebagai: esp32_pothole_cam.ino
 *
 * Fungsi:
 * 1. Terhubung ke WiFi
 * 2. Ambil foto dari kamera OV2640
 * 3. Kirim ke Flask server via HTTP POST setiap N detik
 * 4. Tampilkan respons (jumlah pothole terdeteksi) via Serial Monitor
 *
 * Board   : AI Thinker ESP32-CAM
 * Library : ESP32 Arduino Core (oleh Espressif)
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <Arduino.h>

// ─── KONFIGURASI – SESUAIKAN INI ─────────────────────────────────────────────
const char* WIFI_SSID     = "TI";
const char* WIFI_PASSWORD = "@NusaPutra2025#";

// IP laptop/server Flask Anda (jalankan: ipconfig di Windows atau ifconfig di Linux)
const char* SERVER_URL    = "http://172.20.10.5:5001/upload";

// Interval pengambilan gambar (ms). 3000 = tiap 3 detik
const int   CAPTURE_INTERVAL_MS = 3000;
// ──────────────────────────────────────────────────────────────────────────────

// Pin kamera untuk board AI Thinker ESP32-CAM
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

int frameNumber = 0;  // Nomor frame, auto-increment

// ─── Setup kamera ─────────────────────────────────────────────────────────────
bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Kualitas gambar – SVGA cukup untuk deteksi, lebih ringan dari UXGA
  config.frame_size   = FRAMESIZE_SVGA;  // 800x600
  config.jpeg_quality = 12;              // 0-63, makin kecil makin bagus
  config.fb_count     = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[Camera] Init gagal: 0x%x\n", err);
    return false;
  }
  Serial.println("[Camera] Siap.");
  return true;
}

// ─── Kirim gambar ke Flask ────────────────────────────────────────────────────
void captureAndSend() {
  // Ambil frame dari kamera
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[Camera] Gagal mengambil gambar.");
    return;
  }

  frameNumber++;
  Serial.printf("[Frame %d] Ukuran: %d bytes\n", frameNumber, fb->len);

  // Kirim via HTTP multipart/form-data
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.setTimeout(10000);  // timeout 10 detik

    // Buat boundary untuk multipart
    String boundary = "----ESP32Boundary";
    String contentType = "multipart/form-data; boundary=" + boundary;
    http.addHeader("Content-Type", contentType);

    // Susun body multipart
    String bodyStart = "--" + boundary + "\r\n"
      "Content-Disposition: form-data; name=\"frame_number\"\r\n\r\n"
      + String(frameNumber) + "\r\n"
      "--" + boundary + "\r\n"
      "Content-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\n"
      "Content-Type: image/jpeg\r\n\r\n";

    String bodyEnd = "\r\n--" + boundary + "--\r\n";

    // Hitung total panjang body
    int totalLen = bodyStart.length() + fb->len + bodyEnd.length();
    uint8_t* body = (uint8_t*)malloc(totalLen);

    if (!body) {
      Serial.println("[HTTP] Alokasi memori gagal.");
      esp_camera_fb_return(fb);
      return;
    }

    // Gabungkan body
    memcpy(body, bodyStart.c_str(), bodyStart.length());
    memcpy(body + bodyStart.length(), fb->buf, fb->len);
    memcpy(body + bodyStart.length() + fb->len, bodyEnd.c_str(), bodyEnd.length());

    // Kirim POST
    int httpCode = http.POST(body, totalLen);
    free(body);

    if (httpCode == 200) {
      String response = http.getString();
      Serial.printf("[HTTP] Respon: %s\n", response.c_str());
      // Anda bisa parse JSON di sini jika perlu (gunakan ArduinoJson library)
    } else {
      Serial.printf("[HTTP] Error: %d\n", httpCode);
    }

    http.end();
  } else {
    Serial.println("[WiFi] Tidak terhubung.");
  }

  // Kembalikan buffer kamera
  esp_camera_fb_return(fb);
}

// ─── Setup & Loop ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Sistem Deteksi Pothole – ESP32-CAM ===");

  // Init kamera
  if (!initCamera()) {
    Serial.println("FATAL: Kamera tidak bisa diinisialisasi. Cek wiring.");
    while (true) delay(1000);
  }

  // Sambung WiFi
  Serial.printf("[WiFi] Menghubungkan ke %s ...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 20) {
    delay(500);
    Serial.print(".");
    timeout++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Terhubung! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WiFi] Gagal terhubung. Cek SSID/Password.");
  }
}

void loop() {
  captureAndSend();
  delay(CAPTURE_INTERVAL_MS);
}
