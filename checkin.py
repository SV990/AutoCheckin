import os
import sys
import secrets
import time
import random
import hmac
import hashlib
import base64
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, List

try:
    from curl_cffi import requests
except ImportError:
    print("[ERROR] 请先安装 curl_cffi: pip install curl_cffi")
    sys.exit(1)

# 北京时间
CST = timezone(timedelta(hours=8))

# HTTP 状态码常量
HTTP_OK = 200
HTTP_VALIDATION_ERROR = 422
HTTP_TEMPORARY_ERRORS = (429, 502, 503)


def now_cst() -> datetime:
    """获取当前北京时间"""
    return datetime.now(CST)


def get_ip_info(max_retries: int = 2) -> str:
    """获取当前公网IP信息，支持重试"""
    apis: List[str] = [
        "https://api.ip.sb/geoip",
        "https://ipapi.co/json/",
        "https://api.myip.com",
    ]
    for api_url in apis:
        for attempt in range(max_retries + 1):
            try:
                resp = requests.get(api_url, timeout=10, impersonate="chrome120")
                if resp.status_code == HTTP_OK:
                    data = resp.json()
                    ip = data.get("ip", data.get("IPv4", ""))
                    if not ip:
                        break
                    location_parts: List[str] = []
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
                elif attempt < max_retries:
                    time.sleep(1)
                    continue
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                print(f"[WARNING] IP接口 {api_url} 失败: {e}")
                break
    return "**IP**: 未知"


class FeishuNotifier:
    """飞书 Webhook 通知器"""

    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret

    def _gen_sign(self, timestamp: str) -> Optional[str]:
        if not self.secret:
            return None
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def send_message(self, title: str, content: str) -> bool:
        try:
            timestamp = str(int(time.time()))
            is_success = "成功" in title
            template = "green" if is_success else "red"
            
            now = now_cst()
            footer_text = f"🕐 {now.strftime('%Y-%m-%d %H:%M:%S')} | NodeLoc 自动签到"

            payload = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": title},
                        "template": template,
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {"tag": "lark_md", "content": content},
                        },
                        {"tag": "hr"},
                        {
                            "tag": "note",
                            "elements": [
                                {
                                    "tag": "plain_text",
                                    "content": footer_text,
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

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_message(self, title: str, content: str) -> bool:
        try:
            now = now_cst()
            footer = f"\n\n---\n> 🕐 {now.strftime('%Y-%m-%d %H:%M:%S')} | NodeLoc 自动签到"
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"## {title}\n\n{content}{footer}"
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

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, title: str, content: str) -> bool:
        try:
            now = now_cst()
            # Markdown → Telegram HTML 转换
            import re
            html_content = content
            html_content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html_content)
            html_content = re.sub(r'`([^`]+)`', r'<code>\1</code>', html_content)
            html_content = html_content.replace("---", "━━━━━━━━━━━━")
            text = (
                f"<b>{title}</b>\n\n"
                f"{html_content}\n\n"
                f"━━━━━━━━━━━━\n"
                f"<i>🕐 {now.strftime('%Y-%m-%d %H:%M:%S')} | NodeLoc 自动签到</i>"
            )
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
    """NodeLoc 签到客户端"""

    def __init__(self, username: str, password: str):
        self.base_url: str = "https://www.nodeloc.com"
        self.username: str = username
        self.password: str = password
        self.session: requests.Session = requests.Session(impersonate="chrome120")
        self.csrf_token: Optional[str] = None
        self.user_id: Optional[str] = None

    def get_csrf_token(self) -> bool:
        try:
            response = self.session.get(
                f"{self.base_url}/session/csrf.json",
                headers={
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=15,
            )
            if response.status_code == HTTP_OK:
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

    def login(self) -> bool:
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
            elif response.status_code == HTTP_VALIDATION_ERROR:
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

    def checkin(self, max_retries: int = 2) -> Tuple[bool, str, int]:
        """执行签到，支持重试机制。返回 (是否成功, 消息, 获得能量)"""
        last_error: Optional[str] = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    print(f"[RETRY] 第 {attempt} 次重试签到...")
                    time.sleep(2 * attempt)  # 递增等待时间

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

                if response.status_code == HTTP_OK:
                    result = response.json()
                    message: str = result.get("message", "")
                    errors = result.get("errors", "")
                    points: int = result.get("points", 0)
                    msg_str = str(message or errors)
                    
                    # 打印原始响应用于调试
                    if attempt == 0:
                        print(f"[DEBUG] API响应: success={result.get('success')}, message={msg_str}, points={points}")

                    # 签到成功
                    if result.get("success"):
                        print(f"[SUCCESS] 签到成功！获得 {points} 点能量")
                        return True, msg_str or f"签到成功，获得 {points} 点能量", points

                    # 已签到状态（今天签过了）
                    if any(kw in msg_str for kw in ["已签到", "重复", "今天", "已经"]):
                        print(f"[INFO] {msg_str}")
                        return True, msg_str, points

                    # 签到限制（不是真正的失败）
                    if any(kw in msg_str for kw in ["限制", "频繁", "冷却"]):
                        last_error = msg_str
                        if attempt < max_retries:
                            continue

                    print(f"[ERROR] 签到失败: {msg_str}")
                    return False, msg_str, 0

                elif response.status_code in HTTP_TEMPORARY_ERRORS:
                    # 临时错误（限流、服务不可用、网关错误）
                    last_error = f"HTTP {response.status_code}"
                    if attempt < max_retries:
                        continue
                    print(f"[ERROR] 服务临时不可用: HTTP {response.status_code}")
                    return False, last_error, 0

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
                last_error = str(e)
                if attempt < max_retries:
                    print(f"[WARNING] 签到异常: {e}，准备重试...")
                    continue
                print(f"[ERROR] 签到异常: {e}")
                return False, str(e), 0

        return False, last_error or "重试次数已用完", 0

    def run(self) -> Tuple[bool, str, int]:
        """运行完整签到流程，返回 (是否成功, 消息, 获得能量)"""
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


def is_in_checkin_time() -> bool:
    """检查当前是否在签到时间段 (00:00-06:00 北京时间)"""
    now = now_cst()
    return 0 <= now.hour < 6


def random_delay() -> int:
    """随机延迟，返回延迟秒数"""
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


def send_all_notifications(title: str, content: str, config: Dict[str, str]) -> None:
    """并发发送所有已配置的通知"""
    threads: List[threading.Thread] = []

    def _send(notifier, name: str):
        try:
            notifier.send_message(title, content)
        except Exception as e:
            print(f"[ERROR] {name} 通知异常: {e}")

    # 飞书
    feishu_webhook = config.get("feishu_webhook", "")
    feishu_secret = config.get("feishu_secret", "")
    if feishu_webhook:
        notifier = FeishuNotifier(feishu_webhook, feishu_secret)
        t = threading.Thread(target=_send, args=(notifier, "飞书"))
        threads.append(t)

    # 企业微信
    wecom_webhook = config.get("wecom_webhook", "")
    if wecom_webhook:
        notifier = WeComNotifier(wecom_webhook)
        t = threading.Thread(target=_send, args=(notifier, "企业微信"))
        threads.append(t)

    # Telegram
    tg_bot_token = config.get("tg_bot_token", "")
    tg_chat_id = config.get("tg_chat_id", "")
    if tg_bot_token and tg_chat_id:
        notifier = TelegramNotifier(tg_bot_token, tg_chat_id)
        t = threading.Thread(target=_send, args=(notifier, "Telegram"))
        threads.append(t)

    # 并发启动所有通知
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    if not threads:
        print("[INFO] 未配置任何通知渠道")


def main() -> None:
    """主入口"""
    username: str = os.environ.get("NODELOC_USERNAME", "")
    password: str = os.environ.get("NODELOC_PASSWORD", "")
    force_checkin: bool = os.environ.get("FORCE_CHECKIN", "").lower() == "true"

    # 通知配置
    config: Dict[str, str] = {
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
    ip_info: str = get_ip_info()

    # 签到时段随机延迟，其他时段直接签到
    if not force_checkin:
        random_delay()

    # 执行签到
    checkin_client = NodeLocCheckin(username, password)
    success: bool
    message: str
    points: int
    success, message, points = checkin_client.run()

    # 构建通知内容
    now: datetime = now_cst()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    if success:
        title: str = "🎉 NodeLoc 签到成功"
        content: str = (
            f"📅 **签到日期**: {date_str}\n"
            f"⏰ **签到时间**: {time_str}\n"
            f"👤 **账号**: `{username}`\n"
            f"✨ **状态**: {message}\n"
            f"⚡ **获得能量**: **{points}** 点\n"
            f"---\n"
            f"{ip_info}"
        )
    else:
        title = "⚠️ NodeLoc 签到失败"
        content = (
            f"📅 **日期**: {date_str}\n"
            f"⏰ **时间**: {time_str}\n"
            f"👤 **账号**: `{username}`\n"
            f"❌ **错误**: {message}\n"
            f"---\n"
            f"{ip_info}"
        )

    # 发送所有通知
    send_all_notifications(title, content, config)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
