# 文件操作经验

- 文件大小检查必须用字节数 len(content.encode("utf-8"))，不能用字符数 len(content)。中文 1 字符 = 3 字节。
- corrections.md 头部说明文字可能占 14KB，实际条目只有 3 条。归档逻辑不能只看条目数，要先瘦身头部。
- 静态文件没有 ===SECTION=== 时回退到 APPEND 模式会导致内容无限膨胀。应该 OVERWRITE 而不是 APPEND。
- inventory_update 参数传 NO_CHANGE_BECAUSE 会被当作内容 OVERWRITE 原文件。所有可选参数都必须检查 NO_CHANGE 前缀。
