# NodeLoc 每日自动签到

一个用于 NodeLoc 论坛的自动签到脚本，支持本地运行和 GitHub Actions 定时执行，并可同时推送飞书、企业微信、Telegram 通知。

## 特性

- 自动获取 CSRF Token 并完成登录
- 自动执行签到，支持失败重试
- 支持北京时间 `00:00-06:00` 随机延迟签到
- 支持 `FORCE_CHECKIN=true` 强制签到，跳过时间窗口
- 获取并展示公网 IP、位置和 ISP 信息
- 通知并发发送，互不阻塞
- 通知样式已统一优化：
  - 飞书：卡片式信息面板
  - 企业微信：结构化 Markdown
  - Telegram：HTML 富文本
- 统一使用 `curl_cffi` 模拟浏览器请求指纹

## 项目结构

```text
NodeLoc自动签到/
├── nodeloc_checkin/            # 核心代码包
│   ├── __init__.py
│   ├── __main__.py             # 支持 python -m nodeloc_checkin
│   ├── app.py                  # 程序入口与流程编排
│   ├── client.py               # NodeLoc 登录与签到客户端
│   ├── config.py               # 环境变量配置加载
│   ├── constants.py            # 常量定义
│   ├── formatters.py           # 通知内容格式化
│   ├── models.py               # 数据模型
│   ├── notifiers.py            # 飞书 / 企业微信 / Telegram 通知器
│   └── utils.py                # 时间、IP、延迟等工具函数
├── requirements.txt            # Python 依赖
├── README.md                   # 项目说明
└── .github/workflows/checkin.yml  # GitHub Actions 工作流
```

## 环境要求

- Python 3.10+
- 依赖：`curl_cffi`

## 本地运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置环境变量

**Windows PowerShell**

```powershell
$env:NODELOC_USERNAME='your-email@example.com'
$env:NODELOC_PASSWORD='your-password'
python -m nodeloc_checkin
```

**Linux / macOS**

```bash
export NODELOC_USERNAME='your-email@example.com'
export NODELOC_PASSWORD='your-password'
python -m nodeloc_checkin
```

### 3. 强制签到（可选）

如果你想忽略 `00:00-06:00` 的时间限制：

```powershell
$env:FORCE_CHECKIN='true'
python -m nodeloc_checkin
```

## 环境变量

| 变量名 | 必填 | 说明 |
| --- | --- | --- |
| `NODELOC_USERNAME` | 是 | NodeLoc 账号，通常是邮箱 |
| `NODELOC_PASSWORD` | 是 | NodeLoc 密码 |
| `FEISHU_WEBHOOK_URL` | 否 | 飞书机器人 Webhook |
| `FEISHU_SECRET` | 否 | 飞书机器人签名密钥 |
| `WECOM_WEBHOOK_URL` | 否 | 企业微信机器人 Webhook |
| `TELEGRAM_BOT_TOKEN` | 否 | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 否 | Telegram 接收消息的 Chat ID |
| `FORCE_CHECKIN` | 否 | 设置为 `true` 时强制签到 |

## 通知效果

### 飞书

- 采用交互式卡片
- 显示签到日期、时间、账号、能量、IP 和网络信息
- 成功 / 失败使用不同颜色模板

### 企业微信

- 使用 Markdown 消息
- 采用分段标题和引用块，信息更清晰

### Telegram

- 使用 HTML 格式发送
- 已处理转义，避免常见特殊字符导致消息失败
- 关键信息以加粗 / 代码块方式展示

## GitHub Actions 部署

1. Fork 或推送项目到你的 GitHub 仓库
2. 在仓库的 **Settings → Secrets and variables → Actions** 中配置上述环境变量
3. 进入 **Actions** 页面启用工作流
4. 手动运行一次验证，确认账号和通知都正常

### 定时执行

工作流默认在每天 **UTC 16:00** 触发，换算为 **北京时间 00:00**。

如果需要修改时间，请编辑 `.github/workflows/checkin.yml` 中的 cron：

```yaml
schedule:
  - cron: '0 16 * * *'
```

## 运行逻辑

1. 加载环境变量
2. 获取公网 IP 信息
3. 如未开启 `FORCE_CHECKIN`，则在签到窗口内随机延迟
4. 登录 NodeLoc
5. 调用签到接口
6. 按平台格式化通知并并发发送

## 说明

- 账号密码不会写入代码，建议始终使用环境变量或 GitHub Secrets
- 如果签到失败，请先查看本地输出或 GitHub Actions 日志
- 本地运行时获取的是你当前网络的公网 IP；GitHub Actions 运行时获取的是运行机 IP
