AI-Operation 是一个 AI Agent 行为治理框架（脚手架），通过三层强制机制（规则文本 → MCP 工具硬校验 → Git Hook 物理拦截）确保 AI 编码助手在开发过程中保持纪律。核心架构围绕 project_map（8 个文件的项目记忆系统）展开，所有读写操作必须通过 MCP 工具链完成。
