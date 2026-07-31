"""NodeLoc 签到客户端。"""

from __future__ import annotations

import secrets
import time
from typing import Optional

from curl_cffi import requests

from .constants import (
    CHECKIN_MAX_RETRIES,
    HTTP_OK,
    HTTP_TEMPORARY_ERRORS,
    HTTP_VALIDATION_ERROR,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_SLEEP_SECONDS,
)
from .models import CheckinResult
from .utils import now_cst


class NodeLocCheckin:
    """NodeLoc 签到客户端。"""

    def __init__(self, username: str, password: str):
        self.base_url = "https://www.nodeloc.com"
        self.username = username
        self.password = password
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
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == HTTP_OK:
                data = response.json()
                self.csrf_token = data.get("csrf", "")
                if self.csrf_token:
                    print("[INFO] 获取 CSRF Token 成功")
                    return True
            print(f"[ERROR] 获取 CSRF Token 失败: HTTP {response.status_code}")
            return False
        except Exception as exc:
            print(f"[ERROR] 获取 CSRF Token 异常: {exc}")
            return False

    def login(self) -> bool:
        try:
            if not self.csrf_token and not self.get_csrf_token():
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
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            if response.status_code == HTTP_OK:
                result = response.json()
                if result.get("user") and result["user"].get("username"):
                    user = result["user"]
                    self.user_id = user.get("id")
                    print(f"[INFO] 登录成功: {user.get('username')}")
                    return True
                if result.get("success"):
                    self.user_id = result.get("user_id")
                    print(f"[INFO] 登录成功: {result.get('user_name', self.username)}")
                    return True

                errors = result.get("errors", "登录失败")
                error_msg = errors if isinstance(errors, str) else str(errors)
                print(f"[ERROR] 登录失败: {error_msg}")
                return False

            if response.status_code == HTTP_VALIDATION_ERROR:
                result = response.json()
                errors = result.get("errors", "验证失败")
                print(f"[ERROR] 登录验证失败: {errors}")
                return False

            print(f"[ERROR] 登录请求失败: HTTP {response.status_code}")
            return False
        except Exception as exc:
            print(f"[ERROR] 登录异常: {exc}")
            return False

    def checkin(self, max_retries: int = CHECKIN_MAX_RETRIES) -> CheckinResult:
        """执行签到，支持重试。"""

        last_error: Optional[str] = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    print(f"[RETRY] 第 {attempt} 次重试签到...")
                    time.sleep(RETRY_SLEEP_SECONDS * attempt)

                if not self.get_csrf_token():
                    print("[WARNING] 无法获取新的 CSRF Token，尝试使用现有 token")

                nonce = secrets.token_urlsafe(16)
                timestamp = int(time.time() * 1000)
                checkin_data = {"nonce": nonce, "timestamp": timestamp}
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
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

                if response.status_code == HTTP_OK:
                    result = response.json()
                    message = result.get("message", "")
                    errors = result.get("errors", "")
                    points = int(result.get("points", 0) or 0)
                    msg_str = str(message or errors)

                    if attempt == 0:
                        print(f"[DEBUG] API响应: success={result.get('success')}, message={msg_str}, points={points}")

                    if result.get("success"):
                        print(f"[SUCCESS] 签到成功！获得 {points} 点能量")
                        return CheckinResult(
                            success=True,
                            message=msg_str or f"签到成功，获得 {points} 点能量",
                            points=points,
                        )

                    if any(keyword in msg_str for keyword in ("已签到", "重复", "今天", "已经")):
                        print(f"[INFO] {msg_str}")
                        return CheckinResult(success=True, message=msg_str, points=points)

                    if any(keyword in msg_str for keyword in ("限制", "频繁", "冷却")):
                        last_error = msg_str
                        if attempt < max_retries:
                            continue

                    print(f"[ERROR] 签到失败: {msg_str}")
                    return CheckinResult(success=False, message=msg_str, points=0)

                if response.status_code in HTTP_TEMPORARY_ERRORS:
                    last_error = f"HTTP {response.status_code}"
                    if attempt < max_retries:
                        continue
                    print(f"[ERROR] 服务临时不可用: HTTP {response.status_code}")
                    return CheckinResult(success=False, message=last_error, points=0)

                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    message = error_data.get("message", "")
                    if message:
                        error_msg = str(message)[:100]
                except Exception:
                    pass
                print(f"[ERROR] 签到请求失败: {error_msg}")
                return CheckinResult(success=False, message=error_msg, points=0)
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    print(f"[WARNING] 签到异常: {exc}，准备重试...")
                    continue
                print(f"[ERROR] 签到异常: {exc}")
                return CheckinResult(success=False, message=str(exc), points=0)

        return CheckinResult(success=False, message=last_error or "重试次数已用完", points=0)

    def run(self) -> CheckinResult:
        """运行完整签到流程。"""

        print("=" * 50)
        print("NodeLoc 自动签到脚本")
        print(f"运行时间: {now_cst().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        print()

        print("[STEP 1] 获取 CSRF Token...")
        if not self.get_csrf_token():
            return CheckinResult(False, "获取 CSRF Token 失败", 0)

        print("\n[STEP 2] 登录...")
        if not self.login():
            return CheckinResult(False, "登录失败", 0)

        print("\n[STEP 3] 执行签到...")
        result = self.checkin()

        print(f"\n{'=' * 50}")
        print(f"签到结果: {result.message}")
        print(f"{'=' * 50}")

        return result
