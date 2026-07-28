# NodeLoc 每日自动签到

NodeLoc 论坛 (https://www.nodeloc.com/) 每日自动签到脚本，支持 GitHub Actions 定时执行和飞书通知。

## 功能

- 自动登录 NodeLoc 账号
- 每日 00:00-06:00 时间段随机签到
- 支持飞书 Webhook 推送签到结果
- 支持 GitHub Actions 定时调度
- 使用 curl_cffi 模拟浏览器 TLS 指纹，绕过 Cloudflare 检测

## 本地使用

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行签到

```bash
# 普通运行（仅限 00:00-06:00 时间段执行）
python checkin.py

# 强制签到（忽略时间段限制）
FORCE_CHECKIN=true python checkin.py

# 使用自定义账号密码
NODELOC_USERNAME="your@email.com" NODELOC_PASSWORD="your_password" python checkin.py

# 带上飞书通知
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" python checkin.py
```

## 配置说明

### 环境变量

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `NODELOC_USERNAME` | 是 | NodeLoc 账号（邮箱） |
| `NODELOC_PASSWORD` | 是 | NodeLoc 密码 |
| `FEISHU_WEBHOOK_URL` | 否 | 飞书机器人 Webhook 地址 |
| `FEISHU_SECRET` | 否 | 飞书机器人签名密钥（可选） |
| `FORCE_CHECKIN` | 否 | 设为 `true` 强制签到，忽略时间段限制 |

### 飞书机器人配置

1. 在飞书群聊中添加"自定义机器人"
2. 复制 Webhook 地址
3. （可选）开启签名校验并复制密钥
4. 将 Webhook 地址配置到 `FEISHU_WEBHOOK_URL`

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

### 3. 启用 Actions

1. 进入仓库的 **Actions** 页面
2. 点击 **I understand my workflows, go ahead and enable them**
3. 找到 **NodeLoc 每日签到** 工作流
4. 点击 **Run workflow** 手动触发测试

### 4. 定时执行

工作流配置为每天 UTC 16:00（北京时间 00:00）触发，脚本会在 00:00-06:00 时间段内随机延迟后执行签到。

如需修改触发时间，编辑 `.github/workflows/checkin.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '0 16 * * *'  # UTC 16:00 = 北京时间 00:00
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

## 注意事项

- 请勿将账号密码硬编码在代码中，务必使用 GitHub Secrets
- 签到接口需要登录态，脚本会自动处理
- 如果签到失败，可以查看 GitHub Actions 的运行日志排查问题
- 飞书通知为可选功能，不配置 `FEISHU_WEBHOOK_URL` 时不会发送通知