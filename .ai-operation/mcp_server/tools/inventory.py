"""
Inventory tools — real-time inventory append and consolidation.
Contains: aio__inventory_append, aio__inventory_consolidate
"""

from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *


def register_inventory_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register inventory-related tools onto the MCP server instance."""

    @mcp.tool()
    def aio__inventory_append(
        category: str,
        item: str,
    ) -> str:
        """
        [REAL-TIME PERSISTENCE TOOL] Immediately append one item to inventory.md.

        Call this tool THE MOMENT you discover, create, or decompose a new item
        (skill, module, API endpoint, data model, etc). Do NOT wait for [存档].

        WHY: If you discover 40 skills across a long conversation, your context
        window may only remember the last 10 by save time. By appending each
        item immediately when discovered, ALL items are persisted regardless
        of context window limits.

        This tool does NOT require taskSpec approval — it is a write-ahead log,
        not a code change.

        Args:
            category: The inventory category (e.g., "Skills", "API Endpoints", "Data Models").
            item: One-line description of the item. Include name and key details.
                  Example: "scene_detect — 从视频中检测场景切换点，输入 video_path，输出 List[Timestamp]"

        Returns:
            Confirmation with current count in that category.
        """
        import datetime

        if not category or not category.strip():
            return "REJECTED: category cannot be empty."
        if not item or not item.strip():
            return "REJECTED: item cannot be empty."

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        inventory_path = PROJECT_MAP_DIR / "inventory.md"

        # Read existing content
        existing = ""
        if inventory_path.exists():
            existing = inventory_path.read_text(encoding="utf-8")

        # If file doesn't exist or is empty, create with header
        if not existing.strip():
            existing = (
                f"# Project Inventory (资产清单)\n\n"
                f"> 本文件为实时追加模式。每发现一个资产立即写入，不等 [存档]。\n"
                f"> 定期运行 [整理清单] 去重整理。\n"
            )

        # Check if this exact item already exists (prevent duplicates)
        item_text = item.strip()
        if item_text in existing:
            # Count items in this category
            cat_count = existing.count(f"[{category.strip()}]")
            return f"SKIPPED: Item already exists in inventory. Category '{category.strip()}' has {cat_count} items."

        # Append the item
        entry = f"- [{category.strip()}] {item_text}  _(added {timestamp})_\n"

        with open(inventory_path, "a", encoding="utf-8") as f:
            f.write(entry)

        # Count items in this category after append
        updated = inventory_path.read_text(encoding="utf-8")
        cat_count = updated.count(f"[{category.strip()}]")
        total_count = updated.count("- [")

        _audit("aio__inventory_append", "SUCCESS", f"cat={category.strip()}, total={total_count}")
        return (
            f"SUCCESS: Appended to inventory.\n"
            f"Category: {category.strip()} ({cat_count} items)\n"
            f"Total inventory: {total_count} items\n"
            f"Item: {item_text[:100]}"
        )

    @mcp.tool()
    def aio__inventory_consolidate() -> str:
        """
        [MAINTENANCE TOOL] Read, deduplicate, and organize inventory.md.

        Call this when inventory has accumulated many entries and needs cleanup.
        Reads all entries, groups by category, removes exact duplicates,
        sorts alphabetically within each category, and rewrites the file.

        This is the "整理" step after many "追加" steps.

        Returns:
            Consolidation report with category counts.
        """
        import datetime

        inventory_path = PROJECT_MAP_DIR / "inventory.md"
        if not inventory_path.exists():
            return "SKIPPED: inventory.md does not exist. Nothing to consolidate."

        content = inventory_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Extract all inventory entries (lines starting with "- [")
        entries = {}  # category → set of items
        non_entry_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- [") and "]" in stripped:
                # Parse category and item
                bracket_end = stripped.index("]")
                category = stripped[3:bracket_end]
                item_part = stripped[bracket_end+1:].strip()
                # Remove timestamp suffix if present
                if "_(added " in item_part:
                    item_part = item_part[:item_part.index("_(added ")].strip()
                if category not in entries:
                    entries[category] = set()
                entries[category].add(item_part)
            else:
                if not stripped.startswith(">") and stripped != "---" and not stripped.startswith("# "):
                    continue  # Skip old headers/metadata

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Rebuild file grouped by category
        output = [
            "# Project Inventory (资产清单)\n",
            f"> 上次整理：{timestamp}",
            f"> 本文件为实时追加模式。每发现一个资产立即写入，不等 [存档]。",
            "> 定期运行 aio__inventory_consolidate 去重整理。\n",
        ]

        total = 0
        for category in sorted(entries.keys()):
            items = sorted(entries[category])
            output.append(f"## {category} ({len(items)} items)\n")
            for item in items:
                output.append(f"- {item}")
            output.append("")
            total += len(items)

        inventory_path.write_text("\n".join(output), encoding="utf-8")

        report_lines = [f"SUCCESS: Inventory consolidated."]
        report_lines.append(f"Total: {total} items across {len(entries)} categories\n")
        for cat in sorted(entries.keys()):
            report_lines.append(f"  {cat}: {len(entries[cat])} items")

        _audit("aio__inventory_consolidate", "SUCCESS", f"total={total}")
        return "\n".join(report_lines)
