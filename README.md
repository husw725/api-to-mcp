# API to MCP

把任意 REST API 端点快速转换成 MCP tools，让 AI 客户端（Cursor、Claude Desktop 等）直接调用你的内网服务。

## 快速开始

```bash
cd api-to-mcp
pip install -r requirements.txt
python main.py --port 8000
```

- **Web UI**: http://localhost:8000/ui
- **MCP 端点**: http://localhost:8000/mcp

## 使用流程

1. 打开配置页面，点击「添加服务」
2. 填写服务名称、Base URL、请求头
3. 点击「+ 端点」，配置方法、路径、参数、描述
4. **点击「发送测试请求」验证 API 可达**
5. 测试通过后，点击「添加到 MCP」完成注册

## MCP 客户端配置

Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "my-api": {
      "url": "http://your-server:8000/mcp"
    }
  }
}
```

## 配置示例

```yaml
services:
  - name: "user-service"
    base_url: "http://192.168.1.100:8080/api"
    headers:
      Authorization: "Bearer xxx"
    endpoints:
      - name: "get_user"
        method: "GET"
        path: "/users/{user_id}"
        description: "根据用户ID获取用户信息"
        parameters:
          - name: "user_id"
            type: "string"
            required: true
            location: "path"
        verified: true
```

## 架构

```
┌──────────────┐     ┌──────────────┐     ┌────────────────┐
│  Web UI (/ui)│────▶│  main.py     │────▶│  FastMCP Server│
│  配置/测试    │     │  loader.py   │     │  /mcp (HTTP)   │
└──────────────┘     │  http_client │     └────────────────┘
                     └──────────────┘            │
                                                  ▼
                                            MCP Client
```
