import os
import time
import requests
from zk import ZK
from datetime import datetime
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(dotenv_path=SCRIPT_DIR / '.env')

# --- Configuration ---
DEVICE_IP = os.getenv('ZK_DEVICE_IP', '192.168.1.201')
DEVICE_PORT = int(os.getenv('ZK_DEVICE_PORT', '4370'))

API_URL = os.getenv('API_URL', 'http://localhost:5000/api/machine/attendance')
API_KEY = os.getenv('API_KEY') # Removed hardcoded key for security

SYNC_INTERVAL_SECONDS = int(os.getenv('SYNC_INTERVAL_SECONDS', '60'))
LAST_SYNC_FILE = 'last_sync_uid.txt'

def get_last_sync_uid():
    if os.path.exists(LAST_SYNC_FILE):
        with open(LAST_SYNC_FILE, 'r') as f:
            try:
                return int(f.read().strip() or '0')
            except ValueError:
                return 0
    return 0

def set_last_sync_uid(uid):
    with open(LAST_SYNC_FILE, 'w') as f:
        f.write(str(uid))

def sync_from_device():
    if not API_KEY:
        print(f"[{datetime.now()}] ❌ Configuration Error: API_KEY is missing from environment variables.")
        return

    zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=15, force_udp=False)
    conn = None

    try:
        conn = zk.connect()
        print(f"[{datetime.now()}] Connected to ZKTeco device at {DEVICE_IP}:{DEVICE_PORT}")
        
        # Disable device to isolate operations safely
        try:
            conn.disable_device()
        except Exception as e:
            print(f"[{datetime.now()}] Warning: Could not disable user interaction: {e}")
        
        logs = conn.get_attendance()
        last_uid = get_last_sync_uid()
        new_logs = []
        max_uid = last_uid

        for log in logs:
            if log.uid > last_uid:
                new_logs.append({
                    "zkDeviceId": str(log.user_id).strip(),
                    "timestamp": log.timestamp.isoformat()
                })
                if log.uid > max_uid:
                    max_uid = log.uid

        if new_logs:
            print(f"[{datetime.now()}] Found {len(new_logs)} new attendance records. Sending to server...")
            
            headers = {
                'x-api-key': API_KEY,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(API_URL, json={'logs': new_logs}, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                print(f"[{datetime.now()}] ✅ Successfully synced {len(new_logs)} records to server.")
                set_last_sync_uid(max_uid)
            else:
                print(f"[{datetime.now()}] ❌ Failed to sync to server. Status: {response.status_code}, Response: {response.text}")
        else:
            print(f"[{datetime.now()}] No new attendance records found.")

    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error during sync execution: {e}")

    finally:
        if conn:
            try:
                conn.enable_device()
            except Exception:
                pass # Suppress failures on dead connections to ensure disconnect runs
            try:
                conn.disconnect()
                print(f"[{datetime.now()}] Disconnected from ZKTeco device safely.")
            except Exception:
                print(f"[{datetime.now()}] Forcefully dropped device connection state.")

if __name__ == "__main__":
    print(f"Starting ZKTeco Machine Sync Service...")
    print(f"Target API: {API_URL}")
    print(f"Syncing every {SYNC_INTERVAL_SECONDS} seconds.\n")
    
    while True:
        sync_from_device()
        time.sleep(SYNC_INTERVAL_SECONDS)