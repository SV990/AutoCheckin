"""通知器实现。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Protocol

from curl_cffi import requests

from .constants import NOTIFICATION_TIMEOUT_SECONDS
from .formatters import render_feishu_card, render_telegram_html, render_wecom_markdown
from .models import NotificationPayload


class Notifier(Protocol):
    def send_message(self, payload: NotificationPayload) -> bool:
        """发送通知。"""


class FeishuNotifier:
    """飞书 Webhook 通知器。"""

    def __init__(self, webhook_url: str, secret: str | None = None):
        self.webhook_url = webhook_url
        self.secret = secret

    def _gen_sign(self, timestamp: str) -> str | None:
        if not self.secret:
            return None
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def send_message(self, payload: NotificationPayload) -> bool:
        try:
            timestamp = str(int(time.time()))
            body = render_feishu_card(payload)
            sign = self._gen_sign(timestamp)
            if sign:
                body["timestamp"] = timestamp
                body["sign"] = sign

            response = requests.post(
                self.webhook_url,
                json=body,
                headers={"Content-Type": "application/json"},
                impersonate="chrome120",
                timeout=NOTIFICATION_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    print("[INFO] 飞书通知发送成功")
                    return True
                print(f"[ERROR] 飞书通知发送失败: {result.get('msg')}")
                return False
            print(f"[ERROR] 飞书通知请求失败: HTTP {response.status_code}")
            return False
        except Exception as exc:
            print(f"[ERROR] 飞书通知发送异常: {exc}")
            return False


class WeComNotifier:
    """企业微信 Webhook 通知器。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_message(self, payload: NotificationPayload) -> bool:
        try:
            markdown = render_wecom_markdown(payload)
            response = requests.post(
                self.webhook_url,
                json={"msgtype": "markdown", "markdown": {"content": markdown}},
                headers={"Content-Type": "application/json"},
                impersonate="chrome120",
                timeout=NOTIFICATION_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print("[INFO] 企业微信通知发送成功")
                    return True
                print(f"[ERROR] 企业微信通知发送失败: {result.get('errmsg')}")
                return False
            print(f"[ERROR] 企业微信通知请求失败: HTTP {response.status_code}")
            return False
        except Exception as exc:
            print(f"[ERROR] 企业微信通知发送异常: {exc}")
            return False


class TelegramNotifier:
    """Telegram Bot 通知器。"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, payload: NotificationPayload) -> bool:
        try:
            html_content = render_telegram_html(payload)
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": html_content,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                headers={"Content-Type": "application/json"},
                impersonate="chrome120",
                timeout=NOTIFICATION_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print("[INFO] Telegram 通知发送成功")
                    return True
                print(f"[ERROR] Telegram 通知发送失败: {result.get('description')}")
                return False
            print(f"[ERROR] Telegram 通知请求失败: HTTP {response.status_code}")
            return False
        except Exception as exc:
            print(f"[ERROR] Telegram 通知发送异常: {exc}")
            return False
