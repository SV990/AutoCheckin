"""环境变量配置加载。"""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppConfig:
    username: str
    password: str
    force_checkin: bool = False
    feishu_webhook_url: str = ""
    feishu_secret: str = ""
    wecom_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @property
    def notification_channels(self) -> tuple[str, ...]:
        channels = []
        if self.feishu_webhook_url:
            channels.append("飞书")
        if self.wecom_webhook_url:
            channels.append("企业微信")
        if self.telegram_bot_token and self.telegram_chat_id:
            channels.append("Telegram")
        return tuple(channels)

    @property
    def has_notification_channels(self) -> bool:
        return bool(self.notification_channels)


def load_config() -> AppConfig:
    """从环境变量加载配置。"""

    return AppConfig(
        username=os.environ.get("NODELOC_USERNAME", ""),
        password=os.environ.get("NODELOC_PASSWORD", ""),
        force_checkin=os.environ.get("FORCE_CHECKIN", "").lower() == "true",
        feishu_webhook_url=os.environ.get("FEISHU_WEBHOOK_URL", ""),
        feishu_secret=os.environ.get("FEISHU_SECRET", ""),
        wecom_webhook_url=os.environ.get("WECOM_WEBHOOK_URL", ""),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
    )
