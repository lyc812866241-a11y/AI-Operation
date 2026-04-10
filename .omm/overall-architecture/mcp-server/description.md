MCP Server 入口 — server.py 启动 FastMCP 实例，注册 14 个工具，提供审计日志和循环检测。通过 stdio 传输与 IDE 通信。每个工具调用记录到 audit.log。循环检测：同工具+同参数 5 分钟内 3 次警告、5 次拒绝。
