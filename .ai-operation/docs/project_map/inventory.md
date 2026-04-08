# Project Inventory (资产清单)

> 上次更新：2026-04-08

## MCP Tools (14 个)

- [Tools] aio__force_architect_save — 两阶段存档 Phase 1（准备 + diff 预览 + 自审清单 + 数据质量检查）
- [Tools] aio__force_architect_save_confirm — 两阶段存档 Phase 2（执行写入 + git commit 非阻塞）
- [Tools] aio__force_architect_read — 读档（优先级读取 + TOC 模式 + 预算控制 + 数据质量警告）
- [Tools] aio__force_garbage_collection — 清理（temp 文件 + git 健康扫描）
- [Tools] aio__force_project_bootstrap_write — 初始化（模板 merge + 3 门控 + conventions 支持）
- [Tools] aio__force_architect_report — 汇报（4 段结构化报告）
- [Tools] aio__force_test_runner — 测试（预清理 + 隔离 + 超时保护）
- [Tools] aio__force_taskspec_submit — taskSpec 提交（6 段计划）
- [Tools] aio__force_taskspec_approve — taskSpec 审批（创建 flag）
- [Tools] aio__force_fast_track — 小改动快速通道（信任评分动态阈值）
- [Tools] aio__inventory_append — 实时资产追加（write-ahead log）
- [Tools] aio__inventory_consolidate — 清单整理（去重排序）
- [Tools] aio__detail_read — 详情读取（project_map + details 子文件）
- [Tools] aio__detail_list — 详情列表

## Enforcement Mechanisms (强制机制 — 18 个)

- [Mechanism] Git Hook Gate 1 — 规则文件自动同步
- [Mechanism] Git Hook Gate 2 — project_map 直接编辑拦截
- [Mechanism] Git Hook Gate 3 — 无 taskSpec 审批的代码提交拦截
- [Mechanism] MCP flag 文件 — .mcp_commit_flag / .taskspec_approved / .fast_track
- [Mechanism] 信息密度校验 — 200 字符 + 文件路径必须
- [Mechanism] NO_CHANGE_BECAUSE — 跳过文件必须写理由
- [Mechanism] 动态文件压缩 — > 8KB 只保留最新 1 条
- [Mechanism] Section 拆分 — > 8KB 的 ## section 拆到子文件
- [Mechanism] Corrections→Conventions 升级 — COUNT >= 3 自动升级为项目契约
- [Mechanism] Conventions 契约层 — conventions.md 存储命名/API/UI/错误处理全局约定
- [Mechanism] Corrections 归档 — > 10KB 瘦身头部 + 旧条目归档
- [Mechanism] 通用 overflow 兜底 — 任何文件 > 16KB 强制拆分
- [Mechanism] TOC 模式读档 — 总量超预算时静态文件只显示标题
- [Mechanism] 信任评分 — corrections 频率动态调整 fast-track 阈值
- [Mechanism] 审计日志 — audit.log 记录所有 MCP 调用
- [Mechanism] 循环检测 — 同工具+同参数 5 分钟内 3 次警告、5 次拒绝
- [Mechanism] 数据质量检查 — 读档时检测 inventory 空白/systemPatterns 过时/conventions 缺失
- [Mechanism] 心理学 WHY — 每条规则附带理由提升 AI 遵守率

## Project Map Files (8 个)

- [File] projectbrief.md — 核心愿景与业务目标 [STATIC]
- [File] systemPatterns.md — 系统架构与模块契约 [STATIC]
- [File] techContext.md — 技术栈与已知坑点 [STATIC]
- [File] conventions.md — 项目一致性契约 [STATIC]
- [File] activeContext.md — 当前工作焦点 [DYNAMIC]
- [File] progress.md — 进度与里程碑 [DYNAMIC]
- [File] inventory.md — 资产清单 [STATIC]
- [File] corrections.md — 经验库 [DYNAMIC]

## Skills (3 个)

- [Skill] project-bootstrap — 5 阶段项目初始化协议
- [Skill] systematic-debugging — 根因调查协议
- [Skill] test-driven-development — TDD 强制协议
