import time
import requests
from sms_service import SMSService

API_BASE = "https://abdi-adama.com/api/sms"
API_KEY = "hST9ZCM2yVXZT4fKBsARzUlzralimcS8uP9xMCW0Vu0ocR5gFkzxc4m1mHgi5o7e" 

sms_service = SMSService("http://192.168.8.1")

def headers():
    return {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    }


def get_pending():
    try:
        res = requests.get(
            f"{API_BASE}/pending",
            headers=headers(),
            timeout=10
        )
        return res.json()
    except Exception as e:
        print("❌ Fetch error:", e)
        return []


def mark_sent(sms_id):
    try:
        requests.post(
            f"{API_BASE}/{sms_id}/sent",
            headers=headers(),
            timeout=10
        )
    except Exception as e:
        print("❌ Mark sent error:", e)


def mark_failed(sms_id):
    try:
        requests.post(
            f"{API_BASE}/{sms_id}/failed",
            headers=headers(),
            timeout=10
        )
    except Exception as e:
        print("❌ Mark failed error:", e)


def run_worker():
    print("🚀 SMS Worker started...")

    while True:
        try:
            jobs = get_pending()

            if not jobs:
                time.sleep(5)
                continue

            print(f"📦 {len(jobs)} SMS jobs found")

            for job in jobs:
                sms_id = job["id"]
                phone = job["parent_phone"]
                message = job["message"]

                print(f"📤 Sending {sms_id} → {phone}")

                success = sms_service.send_sms(phone, message)

                if success:
                    mark_sent(sms_id)
                    print(f"✅ Sent {sms_id}")
                else:
                    mark_failed(sms_id)
                    print(f"❌ Failed {sms_id}")

                time.sleep(1)  # small delay to avoid modem overload

        except Exception as e:
            print("⚠️ Worker crash:", e)

        time.sleep(3)


if __name__ == "__main__":
    run_worker()