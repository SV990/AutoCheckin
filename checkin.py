"""
NodeLoc 每日自动签到脚本
- 使用 curl_cffi 模拟浏览器 TLS 指纹，绕过 Cloudflare 检测
- 支持每日 00:00-06:00 时间段随机签到
- 支持飞书/企业微信/Telegram Webhook 推送签到结果
- 支持获取签到IP信息
"""

import os
import sys
import secrets
import time
import random
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone, timedelta

try:
    from curl_cffi import requests
except ImportError:
    print("[ERROR] 请先安装 curl_cffi: pip install curl_cffi")
    sys.exit(1)

# 北京时间
CST = timezone(timedelta(hours=8))


def now_cst():
    """获取当前北京时间"""
    return datetime.now(CST)


def mask_account(account):
    """脱敏账号：保留首尾字符"""
    if not account or "@" not in account:
        return account[:3] + "***" if len(account) > 3 else "***"
    local, domain = account.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def get_ip_info():
    """获取当前公网IP信息"""
    apis = [
        "https://api.ip.sb/geoip",
        "https://ipapi.co/json/",
    ]
    for api_url in apis:
        try:
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                ip = data.get("ip", data.get("IPv4", "未知"))
                if not ip or ip == "未知":
                    continue
                location_parts = []
                if data.get("country"):
                    location_parts.append(data["country"])
                if data.get("region"):
                    location_parts.append(data["region"])
                if data.get("city"):
                    location_parts.append(data["city"])
                location = " / ".join(location_parts) if location_parts else "未知"
                isp = data.get("isp", data.get("org", ""))
                info = f"**IP**: {ip}\n**位置**: {location}"
                if isp:
                    info += f"\n**ISP**: {isp}"
                return info
        except Exception as e:
            print(f"[WARNING] IP接口 {api_url} 失败: {e}")
            continue
    return "**IP**: 未知"


class FeishuNotifier:
    """飞书 Webhook 通知器"""

    def __init__(self, webhook_url, secret=None):
        self.webhook_url = webhook_url
        self.secret = secret

    def _gen_sign(self, timestamp):
        if not self.secret:
            return None
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def send_message(self, title, content):
        try:
            timestamp = str(int(time.time()))
            payload = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": title},
                        "template": "blue" if "成功" in title else "red",
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {"tag": "lark_md", "content": content},
                        },
                        {
                            "tag": "note",
                            "elements": [
                                {
                                    "tag": "plain_text",
                                    "content": f"签到时间: {now_cst().strftime('%Y-%m-%d %H:%M:%S')}",
                                }
                            ],
                        },
                    ],
                },
            }

            sign = self._gen_sign(timestamp)
            if sign:
                payload["timestamp"] = timestamp
                payload["sign"] = sign

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                impersonate="chrome120",
                timeout=10,
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    print("[INFO] 飞书通知发送成功")
                    return True
                else:
                    print(f"[ERROR] 飞书通知发送失败: {result.get('msg')}")
                    return False
            else:
                print(f"[ERROR] 飞书通知请求失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] 飞书通知发送异常: {e}")
            return False


class WeComNotifier:
    """企业微信 Webhook 通知器"""

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send_message(self, title, content):
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"## {title}\n{content}\n> 签到时间: {now_cst().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            }
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                impersonate="chrome120",
                timeout=10,
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print("[INFO] 企业微信通知发送成功")
                    return True
                else:
                    print(f"[ERROR] 企业微信通知发送失败: {result.get('errmsg')}")
                    return False
            else:
                print(f"[ERROR] 企业微信通知请求失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] 企业微信通知发送异常: {e}")
            return False


class TelegramNotifier:
    """Telegram Bot 通知器"""

    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, title, content):
        try:
            text = f"<b>{title}</b>\n\n{content}\n\n<i>签到时间: {now_cst().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                headers={"Content-Type": "application/json"},
                impersonate="chrome120",
                timeout=10,
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print("[INFO] Telegram通知发送成功")
                    return True
                else:
                    print(f"[ERROR] Telegram通知发送失败: {result.get('description')}")
                    return False
            else:
                print(f"[ERROR] Telegram通知请求失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] Telegram通知发送异常: {e}")
            return False


class NodeLocCheckin:
    def __init__(self, username, password):
        self.base_url = "https://www.nodeloc.com"
        self.username = username
        self.password = password
        self.session = requests.Session(impersonate="chrome120")
        self.csrf_token = None
        self.user_id = None

    def get_csrf_token(self):
        try:
            response = self.session.get(
                f"{self.base_url}/session/csrf.json",
                headers={
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                self.csrf_token = data.get("csrf", "")
                if self.csrf_token:
                    print("[INFO] 获取 CSRF Token 成功")
                    return True
            print(f"[ERROR] 获取 CSRF Token 失败: HTTP {response.status_code}")
            return False
        except Exception as e:
            print(f"[ERROR] 获取 CSRF Token 异常: {e}")
            return False

    def login(self):
        try:
            if not self.csrf_token:
                if not self.get_csrf_token():
                    return False

            login_data = {
                "login": self.username,
                "password": self.password,
                "second_factor": "",
                "security_token": "",
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-CSRF-Token": self.csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/login",
                "Accept": "application/json, text/plain, */*",
            }

            response = self.session.post(
                f"{self.base_url}/session.json",
                data=login_data,
                headers=headers,
                timeout=15,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("user") and result["user"].get("username"):
                    user = result["user"]
                    self.user_id = user.get("id")
                    username = user.get("username")
                    print(f"[INFO] 登录成功: {username}")
                    return True
                elif result.get("success"):
                    username = result.get("user_name", self.username)
                    self.user_id = result.get("user_id")
                    print(f"[INFO] 登录成功: {username}")
                    return True
                else:
                    errors = result.get("errors", "登录失败")
                    error_msg = errors if isinstance(errors, str) else str(errors)
                    print(f"[ERROR] 登录失败: {error_msg}")
                    return False
            elif response.status_code == 422:
                result = response.json()
                errors = result.get("errors", "验证失败")
                print(f"[ERROR] 登录验证失败: {errors}")
                return False
            else:
                print(f"[ERROR] 登录请求失败: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"[ERROR] 登录异常: {e}")
            return False

    def checkin(self):
        try:
            if not self.get_csrf_token():
                print("[WARNING] 无法获取新的 CSRF Token，尝试使用现有 token")

            nonce = secrets.token_urlsafe(16)
            timestamp = int(time.time() * 1000)

            checkin_data = {
                "nonce": nonce,
                "timestamp": timestamp,
            }

            headers = {
                "Content-Type": "application/json",
                "X-CSRF-Token": self.csrf_token,
                "X-Discourse-Checkin": "true",
                "X-Checkin-Nonce": nonce,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/",
                "Accept": "application/json, text/plain, */*",
            }

            response = self.session.post(
                f"{self.base_url}/checkin",
                json=checkin_data,
                headers=headers,
                timeout=15,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    points = result.get("points", 0)
                    message = result.get("message", "")
                    print(f"[SUCCESS] 签到成功！获得 {points} 点能量")
                    return True, message or f"签到成功，获得 {points} 点能量", points
                else:
                    message = result.get("message", "未知错误")
                    msg_str = str(message)
                    # 成功状态：包含"签到"关键词且不是失败/错误
                    if ("签到" in msg_str
                            and "失败" not in msg_str
                            and "错误" not in msg_str
                            and "限制" not in msg_str):
                        print(f"[INFO] {message}")
                        return True, message, 0
                    print(f"[ERROR] 签到失败: {message}")
                    return False, message, 0
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    msg = error_data.get("message", "")
                    if msg:
                        error_msg = str(msg)[:100]
                except Exception:
                    pass
                print(f"[ERROR] 签到请求失败: {error_msg}")
                return False, error_msg, 0

        except Exception as e:
            print(f"[ERROR] 签到异常: {e}")
            return False, str(e), 0

    def run(self):
        print(f"{'=' * 50}")
        print(f"NodeLoc 自动签到脚本")
        print(f"运行时间: {now_cst().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 50}")
        print()

        print("[STEP 1] 获取 CSRF Token...")
        if not self.get_csrf_token():
            return False, "获取 CSRF Token 失败", 0

        print("\n[STEP 2] 登录...")
        if not self.login():
            return False, "登录失败", 0

        print("\n[STEP 3] 执行签到...")
        success, message, points = self.checkin()

        print(f"\n{'=' * 50}")
        print(f"签到结果: {message}")
        print(f"{'=' * 50}")

        return success, message, points


def is_in_checkin_time():
    """检查当前是否在签到时间段 (00:00-06:00 北京时间)"""
    now = now_cst()
    return 0 <= now.hour < 6


def random_delay():
    now = now_cst()
    if not is_in_checkin_time():
        print(f"[INFO] 当前时间 {now.strftime('%H:%M')} 非签到时段，直接签到")
        return 0

    end_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
    remaining = (end_time - now).total_seconds()
    max_wait = min(remaining * 0.5, 3600)
    if max_wait <= 0:
        return 0

    wait_seconds = random.randint(0, int(max_wait))
    print(f"[INFO] 签到时段，随机延迟 {wait_seconds} 秒后签到...")
    time.sleep(wait_seconds)
    return wait_seconds


def send_all_notifications(title, content, config):
    """发送所有已配置的通知"""
    # 飞书
    feishu_webhook = config.get("feishu_webhook", "")
    feishu_secret = config.get("feishu_secret", "")
    if feishu_webhook:
        notifier = FeishuNotifier(feishu_webhook, feishu_secret)
        notifier.send_message(title, content)

    # 企业微信
    wecom_webhook = config.get("wecom_webhook", "")
    if wecom_webhook:
        notifier = WeComNotifier(wecom_webhook)
        notifier.send_message(title, content)

    # Telegram
    tg_bot_token = config.get("tg_bot_token", "")
    tg_chat_id = config.get("tg_chat_id", "")
    if tg_bot_token and tg_chat_id:
        notifier = TelegramNotifier(tg_bot_token, tg_chat_id)
        notifier.send_message(title, content)


def main():
    username = os.environ.get("NODELOC_USERNAME", "")
    password = os.environ.get("NODELOC_PASSWORD", "")
    force_checkin = os.environ.get("FORCE_CHECKIN", "").lower() == "true"

    # 通知配置
    config = {
        "feishu_webhook": os.environ.get("FEISHU_WEBHOOK_URL", ""),
        "feishu_secret": os.environ.get("FEISHU_SECRET", ""),
        "wecom_webhook": os.environ.get("WECOM_WEBHOOK_URL", ""),
        "tg_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "tg_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    }

    if not username or not password:
        print("[ERROR] 请设置 NODELOC_USERNAME 和 NODELOC_PASSWORD 环境变量")
        print("       Windows: $env:NODELOC_USERNAME='email'; $env:NODELOC_PASSWORD='pass'")
        print("       Linux: export NODELOC_USERNAME='email' && export NODELOC_PASSWORD='pass'")
        sys.exit(1)

    # 获取IP信息
    ip_info = get_ip_info()

    # 签到时段随机延迟，其他时段直接签到
    if not force_checkin:
        random_delay()

    # 执行签到
    checkin = NodeLocCheckin(username, password)
    success, message, points = checkin.run()

    # 构建通知内容（账号脱敏）
    masked_account = mask_account(username)
    now = now_cst()
    if success:
        title = "✅ NodeLoc 签到成功"
        content = (
            f"**账号**: {masked_account}\n"
            f"**状态**: {message}\n"
            f"**获得能量**: {points} 点\n"
            f"**时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"---\n{ip_info}"
        )
    else:
        title = "❌ NodeLoc 签到失败"
        content = (
            f"**账号**: {masked_account}\n"
            f"**错误信息**: {message}\n"
            f"**时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"---\n{ip_info}"
        )

    # 发送所有通知
    send_all_notifications(title, content, config)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
