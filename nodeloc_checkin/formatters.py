"""通知内容格式化。"""

from __future__ import annotations

from datetime import datetime
from html import escape

from .models import CheckinResult, NetworkInfo, NotificationPayload
from .utils import now_cst


def build_notification_payload(
    username: str,
    result: CheckinResult,
    network_info: NetworkInfo,
    now: datetime | None = None,
) -> NotificationPayload:
    """构建统一通知上下文。"""

    now = now or now_cst()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    success = result.success
    title = "🎉 NodeLoc 签到成功" if success else "⚠️ NodeLoc 签到失败"
    if success:
        if result.points > 0:
            status_text = result.message or f"签到成功，获得 {result.points} 点能量"
        else:
            status_text = result.message or "签到成功"
    else:
        status_text = result.message or "签到失败"
    footer = f"🕐 {date_str} {time_str} | NodeLoc 自动签到"
    return NotificationPayload(
        title=title,
        success=success,
        date_str=date_str,
        time_str=time_str,
        username=username,
        status_text=status_text,
        points=result.points,
        network_info=network_info,
        footer=footer,
    )


def render_network_markdown(network_info: NetworkInfo) -> str:
    lines = [
        "### 🌐 网络信息",
        f"- **IP**: {network_info.ip}",
        f"- **位置**: {network_info.location}",
    ]
    if network_info.isp:
        lines.append(f"- **ISP**: {network_info.isp}")
    if network_info.source:
        lines.append(f"- **来源**: `{network_info.source}`")
    return "\n".join(lines)


def render_feishu_card(payload: NotificationPayload) -> dict:
    template = "green" if payload.success else "red"
    points_text = f"**{payload.points}** 点" if payload.success else "—"
    network_info = payload.network_info

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": payload.title},
                "template": template,
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**日期**\n{payload.date_str}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**时间**\n{payload.time_str}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**账号**\n`{payload.username}`"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**能量**\n{points_text}"}},
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"### 📣 状态\n{payload.status_text}"},
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**IP**\n{network_info.ip}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**位置**\n{network_info.location}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**ISP**\n{network_info.isp or '—'}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**来源**\n{network_info.source or '—'}"}},
                    ],
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": payload.footer}],
                },
            ],
        },
    }


def render_wecom_markdown(payload: NotificationPayload) -> str:
    network_info = payload.network_info
    points_text = f"**{payload.points}** 点" if payload.success else "**0** 点"
    lines = [
        f"## {payload.title}",
        "",
        f"> **日期**：{payload.date_str}",
        f"> **时间**：{payload.time_str}",
        f"> **账号**：`{payload.username}`",
        f"> **状态**：{payload.status_text}",
        f"> **能量**：{points_text}",
        "",
        render_network_markdown(network_info),
        "",
        f"> {payload.footer}",
    ]
    return "\n".join(lines)


def render_telegram_html(payload: NotificationPayload) -> str:
    network_info = payload.network_info
    network_lines = [
        f"IP: {network_info.ip}",
        f"位置: {network_info.location}",
    ]
    if network_info.isp:
        network_lines.append(f"ISP: {network_info.isp}")
    if network_info.source:
        network_lines.append(f"来源: {network_info.source}")
    network_block = "\n".join(network_lines)
    points = payload.points if payload.success else 0

    lines = [
        f"<b>{escape(payload.title)}</b>",
        "",
        "<b>📌 签到信息</b>",
        f"• 日期：{escape(payload.date_str)}",
        f"• 时间：{escape(payload.time_str)}",
        f"• 账号：<code>{escape(payload.username)}</code>",
        f"• 状态：{escape(payload.status_text)}",
        f"• 获得能量：<b>{points}</b> 点",
        "",
        "<b>🌐 网络信息</b>",
        f"<pre>{escape(network_block)}</pre>",
        "",
        f"<i>{escape(payload.footer)}</i>",
    ]
    return "\n".join(lines)
