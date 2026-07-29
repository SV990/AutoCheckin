# NodeLoc 每日自动签到

NodeLoc 论坛 (https://www.nodeloc.com/) 每日自动签到脚本，支持 GitHub Actions 定时执行、多种通知渠道和 IP 信息获取。

## 功能

- 自动登录 NodeLoc 账号
- 每日 00:00-06:00 时间段随机签到（每天仅触发一次）
- **签到重试机制**：签到失败时自动重试 2 次，递增等待时间
- **并发通知**：所有通知渠道并发发送，互不阻塞
- 支持飞书 / 企业微信 / Telegram 通知
- 签到时获取公网 IP 信息（IP、位置、ISP），支持多 IP 接口重试
- 使用 curl_cffi 模拟浏览器 TLS 指纹，绕过 Cloudflare 检测
- 所有请求设置超时，防止卡死
- 完整类型提示，代码结构清晰

## 环境要求

- Python 3.10+
- 依赖：curl_cffi

## 本地运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置环境变量

**Windows PowerShell:**
```powershell
$env:NODELOC_USERNAME='your-email@example.com'
$env:NODELOC_PASSWORD='your-password'
python checkin.py
```

**Linux / macOS:**
```bash
export NODELOC_USERNAME='your-email@example.com'
export NODELOC_PASSWORD='your-password'
python checkin.py
```

### 3. 强制签到（忽略时间段限制）

```bash
$env:FORCE_CHECKIN='true'  # Windows
export FORCE_CHECKIN='true'  # Linux/macOS
python checkin.py
```

## 配置说明

### 环境变量

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `NODELOC_USERNAME` | 是 | NodeLoc 账号（邮箱） |
| `NODELOC_PASSWORD` | 是 | NodeLoc 密码 |
| `FEISHU_WEBHOOK_URL` | 否 | 飞书机器人 Webhook 地址 |
| `FEISHU_SECRET` | 否 | 飞书机器人签名密钥 |
| `WECOM_WEBHOOK_URL` | 否 | 企业微信群机器人 Webhook 地址 |
| `TELEGRAM_BOT_TOKEN` | 否 | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 否 | Telegram 接收消息的 Chat ID |
| `FORCE_CHECKIN` | 否 | 设为 `true` 强制签到，忽略时间段限制 |

### 飞书机器人配置

1. 在飞书群聊中添加"自定义机器人"
2. 复制 Webhook 地址
3. （可选）开启签名校验并复制密钥
4. 将 Webhook 地址配置到 `FEISHU_WEBHOOK_URL`

### 企业微信机器人配置

1. 在企业微信群聊中添加"群机器人"
2. 复制 Webhook 地址
3. 将 Webhook 地址配置到 `WECOM_WEBHOOK_URL`

### Telegram Bot 配置

1. 使用 `@BotFather` 创建 Bot，获取 Token
2. 将 Bot 添加到目标群组或对话
3. 获取 Chat ID（发送消息给 `@userinfobot` 或访问 `https://api.telegram.org/bot<token>/getUpdates`）
4. 配置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`

## 部署到 GitHub

### 1. 创建 GitHub 仓库

在 GitHub 上创建一个新的仓库，然后将代码推送到仓库中。

### 2. 设置 Secrets

在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 页面，添加以下 Repository secrets：

| Secret 名称 | 必填 | 说明 |
|------------|------|------|
| `NODELOC_USERNAME` | 是 | NodeLoc 账号（邮箱） |
| `NODELOC_PASSWORD` | 是 | NodeLoc 密码 |
| `FEISHU_WEBHOOK_URL` | 否 | 飞书机器人 Webhook 地址 |
| `FEISHU_SECRET` | 否 | 飞书机器人签名密钥 |
| `WECOM_WEBHOOK_URL` | 否 | 企业微信群机器人 Webhook 地址 |
| `TELEGRAM_BOT_TOKEN` | 否 | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 否 | Telegram Chat ID |

### 3. 启用 Actions

1. 进入仓库的 **Actions** 页面
2. 点击 **I understand my workflows, go ahead and enable them**
3. 找到 **NodeLoc 每日签到** 工作流
4. 点击 **Run workflow** 手动触发测试

### 4. 定时执行

工作流配置为每天 UTC 16:00（北京时间 00:00）触发一次，脚本会在 00:00-06:00 时间段内随机延迟后执行签到。

如需修改触发时间，编辑 `.github/workflows/checkin.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '0 16 * * *'  # UTC 16:00 = 北京时间 00:00
```

## 签到通知示例

### 成功通知

```
🎉 NodeLoc 签到成功

📅 签到日期: 2026-07-28
⏰ 签到时间: 00:15:30
👤 账号: user@example.com
✨ 状态: 签到成功，获得 10 点能量
⚡ 获得能量: 10 点
---
🌐 网络信息
IP: 1.2.3.4
位置: 中国 / 山西 / 太原
ISP: China Unicom
```

### 失败通知

```
⚠️ NodeLoc 签到失败

📅 日期: 2026-07-28
⏰ 时间: 00:15:30
👤 账号: user@example.com
❌ 错误: 账号或密码错误
---
🌐 网络信息
IP: 1.2.3.4
位置: 中国 / 山西 / 太原
ISP: China Unicom
```

## 项目结构

```
自动签到/
├── checkin.py                    # 签到主脚本
├── requirements.txt              # Python 依赖
├── .gitignore                    # Git 忽略规则
├── README.md                     # 说明文档
└── .github/
    └── workflows/
        └── checkin.yml           # GitHub Actions 工作流配置
```

## 技术说明

- **curl_cffi**: 用于模拟 Chrome 浏览器 TLS 指纹，绕过 Cloudflare 检测
- **Discourse API**: NodeLoc 使用 Discourse 论坛系统，签到插件为 `discourse-checkin`
- **API 流程**: 获取 CSRF Token → 登录 → 调用 `/checkin` 接口签到
- **随机签到**: 脚本会在触发后随机延迟一段时间（最多 1 小时），模拟真人签到习惯
- **时区处理**: 统一使用北京时间（UTC+8），避免时区混乱
- **重试机制**: 签到失败后自动重试 2 次，每次递增等待时间（2秒、4秒）；IP 获取支持重试
- **并发通知**: 使用多线程并发发送通知，提高执行效率
- **状态码常量化**: HTTP 状态码统一管理，便于维护

## 注意事项

- 请勿将账号密码硬编码在代码中，务必使用 GitHub Secrets
- 签到接口需要登录态，脚本会自动处理
- 如果签到失败，可以查看 GitHub Actions 的运行日志排查问题
- 多种通知渠道互相独立，配置任意一个即可使用
- 本地运行时会获取本机 IP 信息，GitHub Actions 运行时会获取服务器 IP
- GitHub Actions 工作流使用 Node.js 24，需保持 action 版本为最新
