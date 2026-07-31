"""数据模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkInfo:
    """公网网络信息。"""

    ip: str = "未知"
    location: str = "未知"
    isp: str = ""
    source: str = ""


@dataclass(frozen=True)
class CheckinResult:
    """签到结果。"""

    success: bool
    message: str
    points: int = 0


@dataclass(frozen=True)
class NotificationPayload:
    """通知内容上下文。"""

    title: str
    success: bool
    date_str: str
    time_str: str
    username: str
    status_text: str
    points: int
    network_info: NetworkInfo
    footer: str
