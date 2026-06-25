import requests
import html
from datetime import datetime
import xml.etree.ElementTree as ET


class SMSService:
    def __init__(self, base_url):
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
                    return token_node.text.strip()

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

            print("MODEM RESPONSE:", response.text)

            return "OK" in response.text or "<response>OK</response>" in response.text

        except Exception as e:
            print("SMS send error:", e)
            return False