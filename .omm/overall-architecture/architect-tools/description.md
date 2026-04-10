核心工具集 — architect.py 单文件 2200+ 行，包含全部 14 个 MCP 工具。负责存档（两阶段+自审清单）、读档（优先级+预算控制）、初始化（模板 merge+3 门控）、taskSpec 审批、垃圾回收、资产管理等。所有文件 I/O 通过此模块完成，直接编辑 project_map 被 Git Hook 拦截。
