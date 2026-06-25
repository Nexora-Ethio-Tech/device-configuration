from flask import Flask, request
import requests
import random
import html
from datetime import datetime
import xml.etree.ElementTree as ET

app = Flask(__name__)

MODEM_URL = "http://192.168.8.1"

MESSAGES = [
    "Hello! Have a great day.",
    "Here's a random message from our website.",
    "Thanks for signing up!",
    "Wishing you an awesome day.",
    "A surprise SMS just arrived."
]


class SMSService:
    def __init__(self, base_url=MODEM_URL):
        self.base_url = base_url

    def _get_token(self):
        try:
            response = requests.get(
                f"{self.base_url}/api/webserver/token",
                timeout=5
            )

            if response.status_code == 200:
                root = ET.fromstring(response.text)

                token_node = root.find("token")

                if token_node is not None:
                    token = token_node.text.strip()
                    print("TOKEN:", token)
                    return token

                print("Unexpected token response:")
                print(response.text)

        except Exception as e:
            print("Token error:", e)

        return None

    def send_sms(self, phone, message):
        token = self._get_token()

        if not token:
            print("Failed to get modem token.")
            return False

        payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<request>
    <Index>-1</Index>
    <Phones>
        <Phone>{phone}</Phone>
    </Phones>
    <Sca></Sca>
    <Content>{html.escape(message)}</Content>
    <Length>{len(message)}</Length>
    <Reserved>1</Reserved>
    <Date>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</Date>
</request>"""

        headers = {
            "__RequestVerificationToken": token,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/sms/send-sms",
                data=payload.encode("utf-8"),
                headers=headers,
                timeout=10
            )

            print("\n===== MODEM RESPONSE =====")
            print("Status:", response.status_code)
            print(response.text)
            print("==========================\n")

            if "OK" in response.text:
                return True

            if "<response>OK</response>" in response.text:
                return True

            return False

        except Exception as e:
            print("SMS send error:", e)
            return False


sms_service = SMSService()


@app.route("/", methods=["GET", "POST"])
def home():
    result = ""

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()

        if not phone:
            result = "Please enter a phone number."
        else:
            message = random.choice(MESSAGES)

            print(f"Sending to: {phone}")
            print(f"Message: {message}")

            if sms_service.send_sms(phone, message):
                result = f"SMS sent to {phone}"
            else:
                result = "Failed to send SMS. Check terminal output."

    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Huawei SMS Sender</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
        }}

        h2 {{
            margin-bottom: 20px;
        }}

        input {{
            width: 100%;
            padding: 12px;
            box-sizing: border-box;
            margin-bottom: 12px;
        }}

        button {{
            padding: 12px 24px;
            cursor: pointer;
        }}

        .result {{
            margin-top: 20px;
            font-weight: bold;
        }}
    </style>
</head>
<body>

    <h2>Receive a Random SMS</h2>

    <form method="post">
        <input
            type="text"
            name="phone"
            placeholder="Enter phone number"
            required
        >


        <button type="submit">
            Send SMS
        </button>
    </form>

    <div class="result">
        {html.escape(result)}
    </div>

</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
