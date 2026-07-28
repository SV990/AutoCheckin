"""
NodeLoc 每日自动签到脚本
- 使用 curl_cffi 模拟浏览器 TLS 指纹，绕过 Cloudflare 检测
- 支持每日 00:00-06:00 时间段随机签到
- 支持飞书 Webhook 推送签到结果
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
from datetime import datetime

try:
    from curl_cffi import requests
except ImportError:
    print("[ERROR] 请先安装 curl_cffi: pip install curl_cffi")
    sys.exit(1)


class FeishuNotifier:
    """飞书 Webhook 通知器"""

    def __init__(self, webhook_url, secret=None):
        self.webhook_url = webhook_url
        self.secret = secret

    def _gen_sign(self, timestamp):
        """生成飞书签名（如果开启了签名校验）"""
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
        """发送飞书消息"""
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
                            "text": {
                                "tag": "lark_md",
                                "content": content,
                            },
                        },
                        {
                            "tag": "note",
                            "elements": [
                                {
                                    "tag": "plain_text",
                                    "content": f"签到时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                }
                            ],
                        },
                    ],
                },
            }

            # 如果设置了签名密钥，添加签名
            sign = self._gen_sign(timestamp)
            if sign:
                payload["timestamp"] = timestamp
                payload["sign"] = sign

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                impersonate="chrome120",
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


class NodeLocCheckin:
    def __init__(self, username, password):
        self.base_url = "https://www.nodeloc.com"
        self.username = username
        self.password = password
        self.session = requests.Session(impersonate="chrome120")
        self.csrf_token = None
        self.user_id = None

    def get_csrf_token(self):
        """通过 Discourse API 获取 CSRF Token"""
        try:
            response = self.session.get(
                f"{self.base_url}/session/csrf.json",
                headers={
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                }
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
        """登录 NodeLoc"""
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
        """执行签到"""
        try:
            # 登录后重新获取 CSRF token
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
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    points = result.get("points", 0)
                    print(f"[SUCCESS] 签到成功！获得 {points} 点能量")
                    return True, f"签到成功，获得 {points} 点能量", points
                else:
                    message = result.get("message", "未知错误")
                    if "already" in str(message).lower() or "签到" in str(message):
                        print(f"[INFO] {message}")
                        return True, message, 0
                    print(f"[ERROR] 签到失败: {message}")
                    return False, message, 0
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = str(error_data)[:100]
                except:
                    pass
                print(f"[ERROR] 签到请求失败: {error_msg}")
                return False, error_msg, 0

        except Exception as e:
            print(f"[ERROR] 签到异常: {e}")
            return False, str(e), 0

    def run(self):
        """运行完整的签到流程"""
        print(f"{'=' * 50}")
        print(f"NodeLoc 自动签到脚本")
        print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 50}")
        print()

        # Step 1: 获取 CSRF Token
        print("[STEP 1] 获取 CSRF Token...")
        if not self.get_csrf_token():
            return False, "获取 CSRF Token 失败", 0

        # Step 2: 登录
        print("\n[STEP 2] 登录...")
        if not self.login():
            return False, "登录失败", 0

        # Step 3: 签到
        print("\n[STEP 3] 执行签到...")
        success, message, points = self.checkin()

        print(f"\n{'=' * 50}")
        print(f"签到结果: {message}")
        print(f"{'=' * 50}")

        return success, message, points


def is_in_checkin_time():
    """检查当前是否在签到时间段 (00:00-06:00)"""
    now = datetime.now()
    return 0 <= now.hour < 6


def random_delay():
    """在签到时间段内随机等待一段时间（模拟随机签到）"""
    now = datetime.now()
    if not is_in_checkin_time():
        return 0  # 不在签到时间段，不等待

    # 计算到 06:00 还剩多少秒
    end_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
    remaining = (end_time - now).total_seconds()

    # 随机等待时间：0 到 剩余时间的 50%
    max_wait = min(remaining * 0.5, 3600)  # 最多等待 1 小时
    if max_wait <= 0:
        return 0

    wait_seconds = random.randint(0, int(max_wait))
    print(f"[INFO] 随机延迟 {wait_seconds} 秒后签到...")
    time.sleep(wait_seconds)
    return wait_seconds


def main():
    # 从环境变量获取配置
    username = os.environ.get("NODELOC_USERNAME", "")
    password = os.environ.get("NODELOC_PASSWORD", "")
    feishu_webhook = os.environ.get("FEISHU_WEBHOOK_URL", "")
    feishu_secret = os.environ.get("FEISHU_SECRET", "")
    force_checkin = os.environ.get("FORCE_CHECKIN", "").lower() == "true"

    if not username or not password:
        print("[ERROR] 请设置 NODELOC_USERNAME 和 NODELOC_PASSWORD 环境变量")
        print("       Windows PowerShell: $env:NODELOC_USERNAME='your@email.com'; $env:NODELOC_PASSWORD='your_password'")
        print("       Linux/macOS: export NODELOC_USERNAME='your@email.com' && export NODELOC_PASSWORD='your_password'")
        sys.exit(1)

    # 检查签到时间
    if not force_checkin and not is_in_checkin_time():
        now = datetime.now()
        print(f"[INFO] 当前时间 {now.strftime('%H:%M:%S')} 不在签到时间段 (00:00-06:00)，跳过签到")
        # 非签到时间段发送通知
        if feishu_webhook:
            notifier = FeishuNotifier(feishu_webhook, feishu_secret)
            notifier.send_message(
                "⏰ NodeLoc 签到跳过",
                f"**当前时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}\n**状态**: 非签到时间段 (00:00-06:00)，跳过签到"
            )
        sys.exit(0)

    # 随机延迟
    if not force_checkin:
        random_delay()

    # 执行签到
    checkin = NodeLocCheckin(username, password)
    success, message, points = checkin.run()

    # 飞书通知
    if feishu_webhook:
        notifier = FeishuNotifier(feishu_webhook, feishu_secret)
        now = datetime.now()

        if success:
            title = "✅ NodeLoc 签到成功"
            content = (
                f"**账号**: {username}\n"
                f"**状态**: {message}\n"
                f"**获得能量**: {points} 点\n"
                f"**时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            title = "❌ NodeLoc 签到失败"
            content = (
                f"**账号**: {username}\n"
                f"**错误信息**: {message}\n"
                f"**时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        notifier.send_message(title, content)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()