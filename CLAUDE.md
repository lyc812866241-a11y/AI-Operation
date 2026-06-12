# AI-Operation Framework Rules (Claude Code)

> Auto-generated from `.clinerules`. Do NOT edit directly.
> To modify: edit `.clinerules`, then run `bash .ai-operation/scripts/sync-rules.sh`.

---

# AI-Operation

## 开机自检 + 源文件索引

每次新对话:先读 ★ 文件,调 `aio__confirm_read` 传 SESSION_KEY(从 corrections.md 末尾获取)。未 confirm 工具会被 hook 拦截。


### 项目记忆（★ 开机必读）

| 文件 | 内容 |
|---|---|
| ★ `~/.ai-operation/wisdom.md` | **二阶 跨项目通用智慧**（用户级共享, 求导思维等普适方法论）|
| ★ `.ai-operation/docs/project_map/activeContext.md` | 当前焦点、下一步 |
| ★ `.ai-operation/docs/project_map/systemPatterns.md` | 项目架构、模块关系 |
| ★ `.ai-operation/docs/project_map/corrections.md` | **一阶 项目级一切**（§1 项目契约 / §2 具体踩坑 / §3 习惯指令）|
| ★ `.ai-operation/docs/conception/design.md` | 项目设计稿（IO 合约 + 功能树 + 愿景 + 反向边界）— 立项产出，编码合约。不存在则跳过 |
| `.ai-operation/docs/project_map/techContext.md` | 技术栈、已知坑点 |
| `.ai-operation/docs/project_map/inventory.md` | 资产清单 |

### 规范与协议（按需查阅）

| 要找什么 | 去哪里 |
|---|---|
| 填写规范 | `.ai-operation/docs/template_reference.md` |
| 调试协议 | `.ai-operation/skills/systematic-debugging/SKILL.md` |
| TDD 协议 | `.ai-operation/skills/test-driven-development/SKILL.md` |
| MCP 工具协议 | `.ai-operation/skills/mcp_protocols/` |

## 指令路由

| 指令 | 去哪里 |
|---|---|
| [读档] | `aio__force_architect_read` |
| [存档] | `aio__force_architect_save` → `_confirm` |
| [立项] / [开题] / [design] | `.ai-operation/skills/project-design/SKILL.md` → `aio__force_project_design_draft` → `_confirm` |
| [初始化项目] | `.ai-operation/skills/project-bootstrap/SKILL.md` |
| [架构扫描] | `.ai-operation/skills/omm-scan/SKILL.md` |
| [整理] | `.ai-operation/skills/consolidate/SKILL.md` |
| 学到教训 / 被纠正 / 踩坑 | `.ai-operation/skills/lesson-distill/SKILL.md` |
| 完成子步骤 / 做出决策 / 发现卡点 | `.ai-operation/skills/state-checkpoint/SKILL.md` |
| [提取契约] / 反推契约(接管已有项目) | `.ai-operation/skills/conventions-extract/SKILL.md` |
| [前端设计] / 做界面 / 换皮 / 灌坑 / 读 Figma 位置 / Figma 排版 | `.ai-operation/skills/frontend-design/SKILL.md` |
| 离线解析 .fig / 设计稿装机 / UI 还原 | `.ai-operation/skills/figma-to-flutter/SKILL.md` |
| [提需] / 功能开发 | `aio__force_taskspec_propose`(列 ≥2 方案带 trade-off)→ 用户选 id → `aio__force_taskspec_submit`(传 chosen_proposal_id)→ `_approve` → 执行 → [验收] → [存档] |
| [验收] / 跑验收 | `aio__force_acceptance_propose`(单元 / 集成 / 业务流程 3 类清单)→ 用户审 → `aio__force_acceptance_approve` → `aio__force_acceptance_run`(失败自循环 fix,上限 3 轮,超限停下问用户)|
| [设计翻译] / [视觉立项] | `aio__force_designer_translate_propose`(把用户口语描述压成 designer spec,自由文本)→ 用户审 → `aio__force_designer_translate_approve` → spec 落档至 `.ai-operation/docs/designer_spec.md`,下游 WORKER 据此写前端代码 |
| [视觉验收] / 视觉验收 | `aio__force_visual_propose`(列视觉关键点 checklist)→ 用户审 → `aio__force_visual_approve` → AI 调 Playwright MCP 截图 + 多模态自看截图 → `aio__force_visual_verify`(失败自循环 fix,上限 3 轮,独立计数器)|
