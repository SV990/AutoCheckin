"""应用入口与流程编排。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from .client import NodeLocCheckin
from .config import AppConfig, load_config
from .formatters import build_notification_payload
from .models import NotificationPayload
from .notifiers import FeishuNotifier, Notifier, TelegramNotifier, WeComNotifier
from .utils import get_ip_info, is_in_checkin_window, now_cst, random_checkin_delay


def send_all_notifications(payload: NotificationPayload, config: AppConfig) -> None:
    """并发发送所有已配置通知。"""

    notifiers: list[tuple[str, Notifier]] = []
    if config.feishu_webhook_url:
        notifiers.append(("飞书", FeishuNotifier(config.feishu_webhook_url, config.feishu_secret)))
    if config.wecom_webhook_url:
        notifiers.append(("企业微信", WeComNotifier(config.wecom_webhook_url)))
    if config.telegram_bot_token and config.telegram_chat_id:
        notifiers.append(("Telegram", TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)))

    if not notifiers:
        print("[INFO] 未配置任何通知渠道")
        return

    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=len(notifiers)) as executor:
        future_map = {executor.submit(notifier.send_message, payload): name for name, notifier in notifiers}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = bool(future.result())
            except Exception as exc:
                results[name] = False
                print(f"[ERROR] {name} 通知异常: {exc}")

    success_count = sum(1 for ok in results.values() if ok)
    print(f"[INFO] 通知发送完成: {success_count}/{len(notifiers)} 成功")


def main() -> None:
    """主入口。"""

    config = load_config()
    if not config.username or not config.password:
        print("[ERROR] 请设置 NODELOC_USERNAME 和 NODELOC_PASSWORD 环境变量")
        print("       Windows: $env:NODELOC_USERNAME='email'; $env:NODELOC_PASSWORD='pass'")
        print("       Linux: export NODELOC_USERNAME='email' && export NODELOC_PASSWORD='pass'")
        raise SystemExit(1)

    network_info = get_ip_info()

    if not config.force_checkin:
        random_checkin_delay()
    else:
        current_time = now_cst()
        if not is_in_checkin_window(current_time):
            print("[INFO] FORCE_CHECKIN=true，已跳过签到时段限制")

    client = NodeLocCheckin(config.username, config.password)
    checkin_result = client.run()

    payload = build_notification_payload(
        username=config.username,
        result=checkin_result,
        network_info=network_info,
        now=now_cst(),
    )

    send_all_notifications(payload, config)
    raise SystemExit(0 if checkin_result.success else 1)
