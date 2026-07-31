"""通用工具函数。"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from curl_cffi import requests

from .constants import (
    CHECKIN_END_HOUR,
    CHECKIN_START_HOUR,
    IP_API_ENDPOINTS,
    IP_MAX_RETRIES,
    IP_REQUEST_TIMEOUT_SECONDS,
    MAX_RANDOM_DELAY_SECONDS,
)
from .models import NetworkInfo


def now_cst() -> datetime:
    """获取当前北京时间。"""

    return datetime.now(timezone(timedelta(hours=8)))


def is_in_checkin_window(now: datetime | None = None) -> bool:
    """判断是否处于签到时间窗口。"""

    now = now or now_cst()
    return CHECKIN_START_HOUR <= now.hour < CHECKIN_END_HOUR


def random_checkin_delay(now: datetime | None = None) -> int:
    """在签到窗口内随机延迟一段时间。"""

    now = now or now_cst()
    if not is_in_checkin_window(now):
        print(f"[INFO] 当前时间 {now.strftime('%H:%M')} 非签到时段，直接签到")
        return 0

    end_time = now.replace(
        hour=CHECKIN_END_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    )
    remaining_seconds = max(0.0, (end_time - now).total_seconds())
    max_wait = min(remaining_seconds * 0.5, MAX_RANDOM_DELAY_SECONDS)
    if max_wait <= 0:
        return 0

    wait_seconds = random.randint(0, int(max_wait))
    print(f"[INFO] 签到时段，随机延迟 {wait_seconds} 秒后签到...")
    time.sleep(wait_seconds)
    return wait_seconds


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _join_location(parts: list[Any]) -> str:
    values = [_clean_text(part) for part in parts if _clean_text(part)]
    return " / ".join(values) if values else "未知"


def _parse_ip_payload(source: str, data: dict[str, Any]) -> NetworkInfo:
    ip = _clean_text(data.get("ip") or data.get("IPv4") or data.get("address")) or "未知"

    if source == "api.ip.sb":
        location = _join_location([data.get("country"), data.get("region"), data.get("city")])
        isp = _clean_text(data.get("isp") or data.get("org"))
    elif source == "ipapi.co":
        location = _join_location(
            [data.get("country_name") or data.get("country"), data.get("region"), data.get("city")]
        )
        isp = _clean_text(data.get("org") or data.get("asn_org") or data.get("asn"))
    else:
        location = _join_location([data.get("country"), data.get("region"), data.get("city"), data.get("cc")])
        isp = _clean_text(data.get("isp") or data.get("org"))

    return NetworkInfo(ip=ip, location=location, isp=isp, source=source)


def get_ip_info(max_retries: int = IP_MAX_RETRIES) -> NetworkInfo:
    """获取当前公网 IP 信息，支持多接口重试。"""

    for source, api_url in IP_API_ENDPOINTS:
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(
                    api_url,
                    timeout=IP_REQUEST_TIMEOUT_SECONDS,
                    impersonate="chrome120",
                )
                if response.status_code == 200:
                    data = response.json()
                    info = _parse_ip_payload(source, data)
                    if info.ip != "未知":
                        return info
                    break
                if attempt < max_retries:
                    time.sleep(1)
                    continue
            except Exception as exc:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                print(f"[WARNING] IP 接口 {api_url} 失败: {exc}")
                break
    return NetworkInfo()
