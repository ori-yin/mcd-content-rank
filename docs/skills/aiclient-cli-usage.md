# AIClient2API CLI 使用指南

> **来源**: https://github.com/justlovemaki/AIClient-2-API
> **文档日期**: 2026-05-19

## 项目简介

AIClient2API（A2）是一个能将多种仅客户端内使用的大模型 API（Gemini CLI, Antigravity, Codex, Grok, Kiro ...），模拟请求，统一封装为本地 OpenAI 兼容接口的强大代理。

## 快速启动

### Docker 快捷启动（推荐）

`ash
docker run -d -p 3000:3000 -p 8085-8086:8085-8086 -p 1455:1455 -p 19876-19880:19876-19880 --restart=always -v "指定路径/configs:/app/configs" -v "指定路径/plugins:/app/src/plugins-user" --name aiclient2api justlikemaki/aiclient-2-api
`

**参数说明**：
- -d：后台运行容器
- -p 3000:3000：Web UI 端口
- -p 8085-8086：OAuth 回调端口（Gemini: 8085, Antigravity: 8086）
- -p 1455：Codex OAuth 回调端口
- -p 19876-19880：Kiro OAuth 回调端口
- --restart=always：容器自动重启策略
- -v "指定路径/configs:/app/configs"：挂载配置目录
- -v "指定路径/plugins:/app/src/plugins-user"：挂载用户插件目录
- --name aiclient2api：容器名称

### 本地运行（非 Docker）

`ash
# 安装依赖并启动
npm install
npm start

# 查看帮助信息
npm run help

# 查看 API 调用示例
npm run example:api

# 纯后端模式（禁用前端管理界面）
npm start -- --no-ui
`

## 访问控制台

启动后访问：**http://localhost:3000**

**默认密码**: dmin123（登录后可在控制台或修改 pwd 文件变更）

## 支持的提供商

| 提供商 | 说明 | OAuth 回调端口 |
|--------|------|----------------|
| Gemini CLI | Google Gemini API | 8085 |
| Antigravity | Claude Opus 支持 | 8086 |
| Codex | OpenAI Codex | 1455 |
| Kiro | Claude Sonnet/Opus | 19876-19880 |
| Grok | xAI Grok 系列 | - |

## 授权文件存储路径

| 服务 | 默认路径 |
|------|---------|
| Gemini | ~/.gemini/oauth_creds.json |
| Kiro | ~/.aws/sso/cache/kiro-auth-token.json |
| Antigravity | ~/.antigravity/oauth_creds.json |
| Codex | ~/.codex/oauth_creds.json |

## 常用 API 端点

### OpenAI 兼容接口

`ash
curl http://localhost:3000/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer your-api-key" -d "{\"model\": \"gemini-2.5-pro\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}"
`

### 路由前缀

可以通过路径前缀指定提供商：

- /gemini-cli-oauth/v1/chat/completions - 使用 Gemini CLI OAuth
- /gemini-antigravity/v1/chat/completions - 使用 Antigravity
- /claude-kiro-oauth/v1/messages - 使用 Kiro 的 Claude
- /grok-web/v1/chat/completions - 使用 Grok

## 配置文件

主配置文件：configs/config.json

关键配置项：

`json
{
  "PROXY_URL": "http://127.0.0.1:7890",
  "PROXY_ENABLED_PROVIDERS": ["gemini-cli-oauth", "claude-kiro-oauth"],
  "providerFallbackChain": {
    "gemini-cli-oauth": ["gemini-antigravity"],
    "claude-kiro-oauth": ["claude-custom"]
  },
  "TLS_SIDECAR_ENABLED": true,
  "TLS_SIDECAR_PORT": 9090
}
`

## 常见问题排查

### 端口被占用

Windows: netstat -ano | findstr :3000
Linux/macOS: lsof -i :3000

### 429 错误处理

- 配置账号池启用轮询
- 配置 Fallback 链
- 启用 429 短冷却：RATE_LIMIT_COOLDOWN_ENABLED: true

### 403 Forbidden

针对 Grok 等服务，需要开启 TLS Sidecar。

## Kiro 扩展思考

注意：budget_tokens 被限制在 [1024, 24576] 之间，默认值为 20000。

## Web UI 功能

- 仪表盘：系统概览、交互式路由示例
- 配置管理：实时参数修改
- 提供商池：监控活动连接、健康统计
- 配置文件：OAuth 凭据集中管理
- 实时日志：系统日志和请求日志

## 相关链接

- GitHub: https://github.com/justlovemaki/AIClient-2-API
- Docker Hub: https://hub.docker.com/r/justlikemaki/aiclient-2-api
- 完整文档: https://aiproxy.justlikemaki.vip/zh/
