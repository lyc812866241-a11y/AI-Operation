"""
Project design tools -- two-phase greenfield conception protocol (full schema).

Tools:
  - aio__force_project_design_draft   (Phase 1: validate + stage, no canonical write)
  - aio__force_project_design_confirm (Phase 2: read staging, write canonical files)

Sibling of bootstrap.py:
  - bootstrap.py handles "接管已有代码库" (scan -> populate project_map).
  - design.py    handles "项目从无到有" (crystallize intent into a functional
                  tree with IO specs BEFORE any code exists).

Schema v2 (P0-P6 fully enforced):
  Each function node:
    name, purpose, input, processing, output      -- P1+P2 (always required)
    priority   ('must-have'|'nice-to-have'|'out-of-scope')   -- P6 (top-level required)
    consumes   (list[str], names of nodes whose output this node depends on)  -- P5
    children   (list[node], optional sub-tree, max depth 4)  -- P3

  Top-level data_dict (separate JSON):
    { TypeName: { field_name: field_type_str, ... }, ... }   -- P4

Cross-cutting validation:
  - Names globally unique across the whole tree
  - All `consumes` references resolve to a defined node
  - Dependency graph (consumes edges) MUST be acyclic (DAG)
  - At least 1 must-have at top level; out-of-scope count >= must-have count
"""

import json
import re
import datetime
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import (
    PROJECT_MAP_DIR,
    git_commit_nonblocking,
)

CONCEPTION_DIR = Path(".ai-operation/docs/conception")
DESIGN_FILE = CONCEPTION_DIR / "design.md"
DESIGN_STAGING_FILE = Path(".ai-operation/.design_staging.json")
DESIGN_STAGING_MAX_AGE_SECONDS = 24 * 3600  # 24h

REQUIRED_NODE_FIELDS = ("name", "purpose", "input", "processing", "output")

VALID_PRIORITIES = ("must-have", "nice-to-have", "out-of-scope")

# Phrases that signal vague thinking. Reject so the user is forced to write
# something concrete.
BANNED_VAGUE_PHRASES = (
    "高效", "智能", "一站式", "全方位", "一键",
    "any", "看情况", "tbd", "todo", "待定", "等等",
)

MIN_FUNCTIONS = 3
MAX_FUNCTIONS = 12
MAX_TREE_DEPTH = 4   # depth 0 = top-level, depth 3 = deepest child
MIN_PURPOSE_CHARS = 10
MAX_ANCHOR_SENTENCES = 3
MIN_FIELD_CHARS = 5

SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Helpers (pure functions)
# ---------------------------------------------------------------------------


def _count_sentences(text: str) -> int:
    parts = re.split(r"[.。!！?？]+", text)
    return sum(1 for p in parts if p.strip())


def _check_banned(value: str, field_name: str) -> str | None:
    low = value.lower()
    for phrase in BANNED_VAGUE_PHRASES:
        if phrase.lower() in low:
            return (
                f"{field_name} contains vague phrase '{phrase}'. "
                f"Rewrite with a concrete, verifiable description."
            )
    return None


def _validate_anchor_and_neg(root_anchor: str, negative_scope: str):
    """Run anchor + negative_scope gates. Returns (anchor, neg, sent_count) or REJECTED string."""
    anchor = root_anchor.strip()
    if not anchor:
        return "REJECTED: root_anchor is empty. Write 1-3 sentences explaining why this project exists."
    sent_count = _count_sentences(anchor)
    if sent_count == 0:
        return "REJECTED: root_anchor has no sentence terminators. End sentences with . 。 ! ! ? ?."
    if sent_count > MAX_ANCHOR_SENTENCES:
        return (
            f"REJECTED: root_anchor has {sent_count} sentences (max {MAX_ANCHOR_SENTENCES}). "
            f"This is an anchor, not a PRD. Compress."
        )
    err = _check_banned(anchor, "root_anchor")
    if err:
        return f"REJECTED: {err}"

    neg = negative_scope.strip()
    if not neg:
        return (
            "REJECTED: negative_scope is empty. Write 1 sentence stating who/what "
            "this project is NOT for. Reverse boundaries are required."
        )
    if len(neg) < MIN_FIELD_CHARS:
        return f"REJECTED: negative_scope is too short ({len(neg)} chars). Be specific."

    return anchor, neg, sent_count


def _validate_node(node, depth, names_seen, errors_label="function_tree"):
    """Recursively validate a single node and its children. Returns error str or None.

    Mutates names_seen with this node's name (for cross-tree uniqueness).
    """
    if not isinstance(node, dict):
        return f"{errors_label} contains non-object at depth {depth} (got {type(node).__name__})."

    # -- required fields presence + type ------------------------------------
    for field in REQUIRED_NODE_FIELDS:
        if field not in node:
            return (
                f"{errors_label} node at depth {depth} missing required field '{field}'. "
                f"Each node needs all of: {list(REQUIRED_NODE_FIELDS)}."
            )
        val = node[field]
        if not isinstance(val, str) or not val.strip():
            return (
                f"{errors_label} node at depth {depth}, field '{field}' is empty or non-string. "
                f"Every IO field must be a concrete string."
            )

    name = node["name"].strip()
    if name in names_seen:
        return f"duplicate function name '{name}' (depth {depth}). Names must be globally unique across the tree."
    names_seen.add(name)

    # -- purpose + IO field length and banned-phrase scan -------------------
    purpose = node["purpose"].strip()
    if len(purpose) < MIN_PURPOSE_CHARS:
        return (
            f"node '{name}' purpose is only {len(purpose)} chars (min {MIN_PURPOSE_CHARS}). "
            f"Describe what it does."
        )
    err = _check_banned(purpose, f"node '{name}' purpose")
    if err:
        return err

    for field in ("input", "processing", "output"):
        v = node[field].strip()
        if len(v) < MIN_FIELD_CHARS:
            return (
                f"node '{name}'.{field} is only {len(v)} chars (min {MIN_FIELD_CHARS}). "
                f"Be specific about types and contents."
            )
        err = _check_banned(v, f"node '{name}'.{field}")
        if err:
            return err

    # -- priority (P6) ------------------------------------------------------
    priority_raw = node.get("priority", "")
    priority = priority_raw.strip() if isinstance(priority_raw, str) else ""
    if depth == 0:
        if priority not in VALID_PRIORITIES:
            return (
                f"top-level node '{name}' must have priority in {list(VALID_PRIORITIES)}, "
                f"got '{priority_raw}'."
            )
    else:
        if priority and priority not in VALID_PRIORITIES:
            return f"node '{name}' has invalid priority '{priority_raw}'."

    # -- consumes (P5) ------------------------------------------------------
    consumes_raw = node.get("consumes", [])
    if not isinstance(consumes_raw, list):
        return f"node '{name}' consumes must be a list of node names (got {type(consumes_raw).__name__})."
    for j, c in enumerate(consumes_raw):
        if not isinstance(c, str) or not c.strip():
            return f"node '{name}' consumes[{j}] is empty or non-string."

    # -- children (P3) ------------------------------------------------------
    children_raw = node.get("children", [])
    if not isinstance(children_raw, list):
        return f"node '{name}' children must be a list (got {type(children_raw).__name__})."

    if children_raw and depth + 1 >= MAX_TREE_DEPTH:
        return (
            f"node '{name}' has children at depth {depth + 1}, exceeding MAX_TREE_DEPTH={MAX_TREE_DEPTH}. "
            f"Flatten or merge sub-functions."
        )

    for child in children_raw:
        err = _validate_node(child, depth + 1, names_seen, errors_label=errors_label)
        if err:
            return err

    return None


def _flatten_tree(tree):
    """Walk tree, return ordered list of (depth, name, node) and adjacency dict."""
    flat = []
    adjacency = {}

    def walk(node, depth):
        name = node["name"].strip()
        flat.append((depth, name, node))
        adjacency[name] = [c.strip() for c in node.get("consumes", [])]
        for child in node.get("children", []) or []:
            walk(child, depth + 1)

    for n in tree:
        walk(n, 0)
    return flat, adjacency


def _detect_cycle(graph):
    """3-color DFS. Returns the cycle path as a list of node names, or None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    cycle_holder = [None]

    def dfs(start):
        # Iterative DFS so we don't blow Python recursion limits on large trees.
        stack = [(start, iter(graph.get(start, [])))]
        path = [start]
        color[start] = GRAY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if nxt not in color:
                    continue  # unresolved reference -- handled by separate gate
                if color[nxt] == GRAY:
                    cycle_holder[0] = path[path.index(nxt):] + [nxt]
                    return
                if color[nxt] == WHITE:
                    color[nxt] = GRAY
                    path.append(nxt)
                    stack.append((nxt, iter(graph.get(nxt, []))))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                path.pop()
                stack.pop()

    for n in list(color.keys()):
        if color[n] == WHITE:
            dfs(n)
            if cycle_holder[0]:
                return cycle_holder[0]
    return None


def _validate_data_dict(data_dict_json: str):
    """Parse + structurally validate the data dictionary. Returns parsed dict or REJECTED string."""
    raw = data_dict_json.strip()
    if not raw:
        return {}
    try:
        data_dict = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"REJECTED: data_dict_json is not valid JSON: {e}"

    if not isinstance(data_dict, dict):
        return "REJECTED: data_dict_json must be a JSON object (TypeName -> field map)."

    for type_name, fields in data_dict.items():
        if not isinstance(type_name, str) or not type_name.strip():
            return f"REJECTED: data_dict has empty type name."
        if not isinstance(fields, dict):
            return (
                f"REJECTED: data_dict.{type_name} must be a dict of field-name to field-type "
                f"(got {type(fields).__name__})."
            )
        if not fields:
            return f"REJECTED: data_dict.{type_name} has no fields. Define at least 1 or remove the type."
        for field_name, field_type in fields.items():
            if not isinstance(field_name, str) or not field_name.strip():
                return f"REJECTED: data_dict.{type_name} has empty field name."
            if not isinstance(field_type, str) or not field_type.strip():
                return (
                    f"REJECTED: data_dict.{type_name}.{field_name} must be a string type description "
                    f"(got {type(field_type).__name__})."
                )

    return data_dict


def _validate_priority_balance(tree):
    """Top-level priority balance. Returns error string or None."""
    counts = {p: 0 for p in VALID_PRIORITIES}
    for n in tree:
        p_raw = n.get("priority", "")
        p = p_raw.strip() if isinstance(p_raw, str) else ""
        if p in counts:
            counts[p] += 1

    if counts["must-have"] == 0:
        return (
            "no must-have function at top level. A project with zero commitments is not a project. "
            "Mark at least 1 top-level node as 'must-have'."
        )
    if counts["out-of-scope"] < counts["must-have"]:
        return (
            f"priority imbalance: {counts['out-of-scope']} out-of-scope vs {counts['must-have']} must-have. "
            f"For every commitment, articulate a non-commitment. "
            f"Required: top-level out-of-scope count >= must-have count. "
            f"Add explicit out-of-scope items or downgrade must-haves."
        )
    return None


def _validate_inputs(root_anchor: str, negative_scope: str, function_tree_json: str, data_dict_json: str):
    """Run gates 2-6 plus P3/P4/P5/P6 on the full schema.

    Returns (anchor, neg, tree, data_dict, sent_count) on success or REJECTED string on first failure.
    """
    res = _validate_anchor_and_neg(root_anchor, negative_scope)
    if isinstance(res, str):
        return res
    anchor, neg, sent_count = res

    # -- function_tree JSON parse -------------------------------------------
    try:
        tree = json.loads(function_tree_json)
    except json.JSONDecodeError as e:
        return (
            f"REJECTED: function_tree_json is not valid JSON: {e}\n"
            f"Expected: a JSON array of node objects."
        )
    if not isinstance(tree, list):
        return "REJECTED: function_tree_json must be a JSON array (list of node objects)."

    if len(tree) < MIN_FUNCTIONS:
        return (
            f"REJECTED: only {len(tree)} top-level functions (min {MIN_FUNCTIONS}). "
            f"Either decompose your idea further, or this project is too small to need this skill."
        )
    if len(tree) > MAX_FUNCTIONS:
        return (
            f"REJECTED: {len(tree)} top-level functions (max {MAX_FUNCTIONS}). "
            f"Group related functions or split into sub-projects."
        )

    # -- recursive node validation (P1+P2+P3+P5+P6 shape) -------------------
    names_seen: set = set()
    for i, node in enumerate(tree):
        err = _validate_node(node, depth=0, names_seen=names_seen, errors_label=f"function_tree[{i}]")
        if err:
            return f"REJECTED: {err}"

    # -- DAG: consumes references resolve + no cycles (P5) ------------------
    flat, adjacency = _flatten_tree(tree)
    all_names = set(adjacency.keys())
    for name, consumes in adjacency.items():
        for c in consumes:
            if c not in all_names:
                return (
                    f"REJECTED: node '{name}' consumes '{c}' which is not a defined node name. "
                    f"Either add the node or remove the consumes entry. "
                    f"Defined names: {sorted(all_names)}"
                )
    cycle = _detect_cycle(adjacency)
    if cycle:
        return (
            f"REJECTED: dependency cycle detected: {' -> '.join(cycle)}. "
            f"Break the cycle by removing one consumes edge or merging the nodes."
        )

    # -- priority balance (P6) ----------------------------------------------
    err = _validate_priority_balance(tree)
    if err:
        return f"REJECTED: {err}"

    # -- data dictionary (P4) -----------------------------------------------
    dd_result = _validate_data_dict(data_dict_json)
    if isinstance(dd_result, str):
        return dd_result
    data_dict = dd_result

    return anchor, neg, tree, data_dict, sent_count


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _priority_badge(node) -> str:
    p_raw = node.get("priority", "")
    p = p_raw.strip() if isinstance(p_raw, str) else ""
    if p in VALID_PRIORITIES:
        return f"〔{p}〕"
    return ""


def _render_tree_section(tree, prefix="4") -> list[str]:
    """Render the functional tree as nested markdown sections. Returns list of lines."""
    lines: list[str] = []

    def render_node(node, path):
        depth = len(path) - 1
        # Heading: ### for depth 0, #### for depth 1, etc.
        header_hashes = "#" * (3 + depth)
        path_str = ".".join(str(p) for p in path)
        badge = _priority_badge(node)
        lines.append(f"{header_hashes} {prefix}.{path_str} `{node['name'].strip()}` {badge}".rstrip() + "\n")
        lines.append(f"**职责**：{node['purpose'].strip()}\n")
        lines.append(f"- **Input** — {node['input'].strip()}")
        lines.append(f"- **Processing** — {node['processing'].strip()}")
        lines.append(f"- **Output** — {node['output'].strip()}")
        consumes = [c.strip() for c in node.get("consumes", []) if str(c).strip()]
        if consumes:
            lines.append(f"- **Consumes** — {', '.join(consumes)}")
        lines.append("")

        children = node.get("children", []) or []
        for j, child in enumerate(children, 1):
            render_node(child, path + [j])

    for i, node in enumerate(tree, 1):
        render_node(node, [i])
    return lines


def _render_data_dict_section(data_dict: dict, section_num: int) -> list[str]:
    """Render data dictionary as a markdown table. Returns list of lines (empty if no types)."""
    if not data_dict:
        return []
    lines = [f"## {section_num}. 数据字典 (Data Dictionary)\n"]
    lines.append("| 类型 | 字段定义 |")
    lines.append("|---|---|")
    for type_name, fields in data_dict.items():
        field_strs = [f"{fn} ({ft})" for fn, ft in fields.items()]
        lines.append(f"| `{type_name}` | {', '.join(field_strs)} |")
    lines.append("")
    return lines


def _render_priority_summary(tree) -> list[str]:
    flat, _ = _flatten_tree(tree)
    top_counts = {p: 0 for p in VALID_PRIORITIES}
    for n in tree:
        p_raw = n.get("priority", "")
        p = p_raw.strip() if isinstance(p_raw, str) else ""
        if p in top_counts:
            top_counts[p] += 1
    total_nodes = len(flat)
    max_depth = max(d for d, _, _ in flat) if flat else 0

    return [
        f"- 一级 must-have: {top_counts['must-have']}",
        f"- 一级 nice-to-have: {top_counts['nice-to-have']}",
        f"- 一级 out-of-scope: {top_counts['out-of-scope']}",
        f"- 总节点数: {total_nodes}",
        f"- 树深: {max_depth + 1} 层 (max {MAX_TREE_DEPTH})",
        "",
    ]


def _render_dependency_section(adjacency: dict, section_num: int) -> list[str]:
    """Compact dependency-graph listing. Returns list of lines."""
    edges = [(src, dst_list) for src, dst_list in adjacency.items() if dst_list]
    if not edges:
        return []
    lines = [
        f"## {section_num}. 依赖图 (Dependency Edges)\n",
        "```",
    ]
    name_w = max(len(s) for s, _ in edges) if edges else 1
    for src, dst_list in edges:
        lines.append(f"{src.ljust(name_w)} → {', '.join(dst_list)}")
    lines.append("```")
    lines.append("")
    return lines


def _render_design_md(anchor, neg, tree, data_dict, timestamp, status) -> str:
    """Compose the full design.md (or staging preview) content."""
    _, adjacency = _flatten_tree(tree)
    section = 1

    parts: list[str] = []
    parts.append(f"# 项目设计稿 (Project Design)\n")
    parts.append(
        f"> 由 project-design 技能写入于 {timestamp}。\n"
        f"> 这是项目实现前的设计稿。代码完成后由 bootstrap 产出实现稿，\n"
        f"> 二者可通过 audit_design_vs_implementation 对比偏差。\n"
        f"> 状态：{status}\n"
    )

    parts.append(f"## {section}. 根锚 (Root Anchor)\n")
    parts.append(anchor + "\n")
    section += 1

    parts.append(f"## {section}. 反向边界 (Negative Scope)\n")
    parts.append("**不是给谁/不是干什么的**：" + neg + "\n")
    section += 1

    if data_dict:
        parts.extend(_render_data_dict_section(data_dict, section))
        section += 1

    parts.append(f"## {section}. 功能树 (Functional Tree)\n")
    flat, _ = _flatten_tree(tree)
    parts.append(
        f"共 {len(tree)} 个一级功能 / {len(flat)} 个总节点 / 最大深度 "
        f"{(max(d for d, _, _ in flat) + 1) if flat else 0} 层。"
        f"每个节点的 input/processing/output 是合约，实现时不得偏离。\n"
    )
    parts.extend(_render_tree_section(tree, prefix=str(section)))
    func_section = section
    section += 1

    parts.append(f"## {section}. 优先级统计\n")
    parts.extend(_render_priority_summary(tree))
    section += 1

    dep_lines = _render_dependency_section(adjacency, section)
    if dep_lines:
        parts.extend(dep_lines)
        section += 1

    parts.append(f"## {section}. 元信息\n")
    parts.append(f"- 写入时间：{timestamp}")
    parts.append(f"- schema 版本：v{SCHEMA_VERSION}")
    parts.append(f"- 一级节点数：{len(tree)}")
    parts.append(f"- 状态：{status}\n")

    # Note about func_section to silence linter -- the variable is intentionally
    # captured (downstream tooling may want to know which section is the tree).
    _ = func_section

    return "\n".join(parts)


def _render_brief_md(anchor, neg, tree, data_dict, timestamp) -> str:
    """projectbrief.md: root anchor + negative scope + top-level summary + pointer."""
    top_lines = []
    for n in tree:
        badge = _priority_badge(n)
        top_lines.append(f"- {badge} **{n['name'].strip()}** — {n['purpose'].strip()}")

    counts = {p: 0 for p in VALID_PRIORITIES}
    for n in tree:
        p_raw = n.get("priority", "")
        p = p_raw.strip() if isinstance(p_raw, str) else ""
        if p in counts:
            counts[p] += 1

    return (
        f"# 项目愿景 (Project Brief)\n\n"
        f"> 由 project-design 写入于 {timestamp}。详细设计见 "
        f"`.ai-operation/docs/conception/design.md`。\n\n"
        f"## 1. 核心愿景 (Vision)\n\n{anchor}\n\n"
        f"## 2. 反向边界 (Not For)\n\n{neg}\n\n"
        f"## 3. 一级功能概览\n\n"
        + "\n".join(top_lines) + "\n\n"
        f"## 4. 优先级与状态\n\n"
        f"- 阶段：DESIGN (设计稿，未实现)\n"
        f"- 一级 must-have / nice-to-have / out-of-scope: "
        f"{counts['must-have']} / {counts['nice-to-have']} / {counts['out-of-scope']}\n"
        f"- 数据字典类型数：{len(data_dict)}\n"
        f"- 详细 IO 合约：见 `conception/design.md`\n"
    )


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_design_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register the two-phase design tools onto the MCP server instance."""

    @mcp.tool()
    def aio__force_project_design_draft(
        root_anchor: str,
        negative_scope: str,
        function_tree_json: str,
        data_dict_json: str = "",
    ) -> str:
        """
        [PHASE 1: STAGE] Validate the design and write a staging file. Nothing
        canonical is written yet -- the user MUST review the preview returned
        by this tool, then call aio__force_project_design_confirm.

        Schema (v2): each function node may include
          - priority   ('must-have' | 'nice-to-have' | 'out-of-scope')   [REQUIRED at top level]
          - consumes   (list of node names this depends on)
          - children   (sub-tree, max depth 4)

        Cross-cutting checks:
          - Globally unique node names
          - All `consumes` references resolve
          - Dependency graph is a DAG (no cycles)
          - At least 1 must-have at top level
          - Top-level out-of-scope count >= must-have count

        Args:
            root_anchor: 1-3 sentences on what kind of product + what need it solves.
            negative_scope: 1 sentence. Who/what this is NOT for.
            function_tree_json: JSON array. Each node MUST have name, purpose,
                input, processing, output. Top-level nodes additionally MUST have
                priority. Optional: consumes (list[str]), children (list[node]).
                Example:
                  [{"name": "auth", "purpose": "...", "input": "...",
                    "processing": "...", "output": "...",
                    "priority": "must-have", "consumes": ["db"],
                    "children": [...]}]
            data_dict_json: Optional JSON object mapping TypeName -> {field: type}.
                Example: {"User": {"id": "int", "email": "str"}}.

        Returns:
            PENDING_REVIEW with full preview markdown + instructions to call
            confirm, OR a REJECTED message indicating which gate failed.
        """
        _audit("aio__force_project_design_draft", "CALLED")

        loop_msg = _loop_guard("aio__force_project_design_draft", function_tree_json[:200])
        if loop_msg and "BLOCKED" in loop_msg:
            _audit("aio__force_project_design_draft", "LOOP_BLOCKED")
            return loop_msg

        if not PROJECT_MAP_DIR.exists():
            return (
                f"FAILED: {PROJECT_MAP_DIR} does not exist.\n"
                f"Run setup.sh / setup.ps1 first to scaffold the framework into this project."
            )

        result = _validate_inputs(root_anchor, negative_scope, function_tree_json, data_dict_json)
        if isinstance(result, str):
            _audit("aio__force_project_design_draft", "REJECTED", result[:200])
            return result
        anchor, neg, tree, data_dict, sent_count = result

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        flat, _adj = _flatten_tree(tree)
        staging_payload = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": timestamp,
            "epoch": datetime.datetime.now().timestamp(),
            "root_anchor": anchor,
            "negative_scope": neg,
            "function_tree": tree,
            "data_dict": data_dict,
            "sentence_count": sent_count,
            "node_count": len(flat),
        }
        DESIGN_STAGING_FILE.parent.mkdir(parents=True, exist_ok=True)
        DESIGN_STAGING_FILE.write_text(
            json.dumps(staging_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        preview_md = _render_design_md(
            anchor, neg, tree, data_dict, timestamp,
            status="DRAFT (staged, not committed)",
        )

        _audit(
            "aio__force_project_design_draft",
            "STAGED",
            f"top={len(tree)} total={len(flat)} types={len(data_dict)}",
        )

        return (
            f"PENDING_REVIEW: Design draft staged. NOTHING has been written to canonical files yet.\n\n"
            f"Staging:  {DESIGN_STAGING_FILE}\n"
            f"Validation: P0+P1+P2+P3+P4+P5+P6 all passed.\n"
            f"  - top-level functions: {len(tree)}\n"
            f"  - total nodes (incl. children): {len(flat)}\n"
            f"  - data dictionary types: {len(data_dict)}\n"
            f"  - dependency graph: acyclic ✓\n\n"
            f"========== PREVIEW (this is exactly what design.md will contain) ==========\n\n"
            f"{preview_md}\n"
            f"========================== END PREVIEW ==========================\n\n"
            f"Show this preview to the user. After they explicitly approve, call:\n"
            f"   aio__force_project_design_confirm(user_confirmed=True)\n\n"
            f"To revise: call aio__force_project_design_draft again with corrected fields.\n"
            f"The staging file will be overwritten and the new draft re-validated.\n"
        )

    @mcp.tool()
    def aio__force_project_design_confirm(
        user_confirmed: bool,
    ) -> str:
        """
        [PHASE 2: COMMIT] Apply the staged design to canonical files.

        Reads the staging file, runs defense-in-depth re-validation, writes
        design.md + projectbrief.md, and creates a git commit. Cleans up
        staging on success.

        Args:
            user_confirmed: MUST be True. Set only after explicit user approval
                of the preview returned by the draft tool.

        Returns:
            SUCCESS with file paths and git commit status, OR REJECTED if no
            staging exists / staging is stale / re-validation fails.
        """
        _audit("aio__force_project_design_confirm", "CALLED")

        loop_msg = _loop_guard("aio__force_project_design_confirm")
        if loop_msg and "BLOCKED" in loop_msg:
            _audit("aio__force_project_design_confirm", "LOOP_BLOCKED")
            return loop_msg

        if not user_confirmed:
            return (
                "REJECTED: user_confirmed must be True.\n"
                "You MUST present the draft preview (from aio__force_project_design_draft) "
                "to the user and receive explicit approval before calling this tool."
            )

        if not DESIGN_STAGING_FILE.exists():
            return (
                "REJECTED: No design staging found.\n"
                "You must call aio__force_project_design_draft first to prepare and preview the design."
            )

        try:
            staging_payload = json.loads(DESIGN_STAGING_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return (
                f"REJECTED: staging file is corrupted ({e}).\n"
                f"Delete {DESIGN_STAGING_FILE} and call aio__force_project_design_draft again."
            )

        # -- schema version check -------------------------------------------
        version = staging_payload.get("schema_version", 1)
        if version != SCHEMA_VERSION:
            DESIGN_STAGING_FILE.unlink(missing_ok=True)
            return (
                f"REJECTED: staging schema_version={version}, expected v{SCHEMA_VERSION}. "
                f"Stale staging deleted. Call draft again."
            )

        # -- staleness ------------------------------------------------------
        staging_epoch = staging_payload.get("epoch", 0)
        age_seconds = datetime.datetime.now().timestamp() - staging_epoch
        if age_seconds > DESIGN_STAGING_MAX_AGE_SECONDS:
            DESIGN_STAGING_FILE.unlink(missing_ok=True)
            return (
                f"REJECTED: staging is stale ({age_seconds/3600:.1f} hours old, "
                f"max {DESIGN_STAGING_MAX_AGE_SECONDS/3600:.0f}h). "
                f"Stale staging deleted. Call aio__force_project_design_draft again."
            )

        # -- defense-in-depth re-validation ---------------------------------
        try:
            tree_json_str = json.dumps(staging_payload["function_tree"], ensure_ascii=False)
            data_dict_json_str = json.dumps(
                staging_payload.get("data_dict", {}), ensure_ascii=False,
            )
            result = _validate_inputs(
                staging_payload["root_anchor"],
                staging_payload["negative_scope"],
                tree_json_str,
                data_dict_json_str,
            )
        except KeyError as e:
            DESIGN_STAGING_FILE.unlink(missing_ok=True)
            return (
                f"REJECTED: staging file is missing required field {e}. "
                f"Stale staging deleted. Call draft again."
            )
        if isinstance(result, str):
            DESIGN_STAGING_FILE.unlink(missing_ok=True)
            _audit("aio__force_project_design_confirm", "REVALIDATION_FAILED", result[:200])
            return f"REJECTED (re-validation): {result}\nStale staging deleted."
        anchor, neg, tree, data_dict, _ = result

        if not PROJECT_MAP_DIR.exists():
            return (
                f"FAILED: {PROJECT_MAP_DIR} does not exist.\n"
                f"Run setup.sh / setup.ps1 first to scaffold the framework into this project."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        CONCEPTION_DIR.mkdir(parents=True, exist_ok=True)

        DESIGN_FILE.write_text(
            _render_design_md(anchor, neg, tree, data_dict, timestamp, status="COMMITTED (design v1)"),
            encoding="utf-8",
        )
        brief_path = PROJECT_MAP_DIR / "projectbrief.md"
        brief_path.write_text(
            _render_brief_md(anchor, neg, tree, data_dict, timestamp),
            encoding="utf-8",
        )

        files_to_commit = [str(DESIGN_FILE), str(brief_path)]
        flat, _adj = _flatten_tree(tree)
        commit_msg = (
            f"chore: project-design commit [{timestamp}] "
            f"-- {len(tree)} top / {len(flat)} total / {len(data_dict)} types"
        )
        git_status, _ = git_commit_nonblocking(files_to_commit, commit_msg)

        DESIGN_STAGING_FILE.unlink(missing_ok=True)

        _audit(
            "aio__force_project_design_confirm",
            "SUCCESS",
            f"top={len(tree)} total={len(flat)} types={len(data_dict)} git={git_status}",
        )

        counts = {p: 0 for p in VALID_PRIORITIES}
        for n in tree:
            p_raw = n.get("priority", "")
            p = p_raw.strip() if isinstance(p_raw, str) else ""
            if p in counts:
                counts[p] += 1

        return (
            f"SUCCESS: Project design committed.\n\n"
            f"Files written:\n"
            f"  - {DESIGN_FILE}\n"
            f"  - {brief_path}\n\n"
            f"Staging cleaned up: {DESIGN_STAGING_FILE} deleted.\n\n"
            f"Summary:\n"
            f"  - Root anchor sentences: {staging_payload.get('sentence_count', '?')}\n"
            f"  - Negative scope chars: {len(neg)}\n"
            f"  - Top-level functions: {len(tree)} "
            f"(must={counts['must-have']}, nice={counts['nice-to-have']}, out={counts['out-of-scope']})\n"
            f"  - Total nodes (incl. children): {len(flat)}\n"
            f"  - Data dictionary types: {len(data_dict)}\n\n"
            f"Git: {git_status}\n\n"
            f"Next:\n"
            f"  1. Implement code per the IO contracts in design.md.\n"
            f"  2. Each function node = one module/function in code.\n"
            f"  3. After implementation, run [初始化项目] to populate systemPatterns.md\n"
            f"     from actual code, then audit design vs implementation.\n"
        )
