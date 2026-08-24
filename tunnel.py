import ssl
import time
from pyngrok import ngrok

# Bypass SSL Verification
ssl._create_default_https_context = ssl._create_unverified_context

# 1. Set Token yang BENAR (Gunakan token kamu yang valid di sini)
ngrok.set_auth_token("3HEOT4Vdt2Py3x0BYSVTAIIN5jU_6a8dRsTF5VdYAdpSyB3v7")

# 2. Connect ke Port Flask kamu (5001)
tunnel = ngrok.connect(5001)
base_url = tunnel.public_url

print("\n" + "=" * 50)
print(f"URL BARU KAMU : {base_url}")
print(f"URL ESP32     : {base_url}/upload")
print(f"Dashboard     : {base_url}/dashboard")
print("=" * 50 + "\n")

# Biarkan script tetap jalan
try:
  while True:
    time.sleep(1)
except KeyboardInterrupt:
  print("\nTunnel dimatikan.")
