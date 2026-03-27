# Vibe Coding Agent Framework

> An advanced Context Engineering boilerplate for AI Agents (Level 4 "Robotaxi" standard).

## What is this?
This is an abstraction of the "Project Map" / "Memory Bank" paradigm designed to elevate any code repository into a fully AI-native **Vibe Coding** workspace. By providing a structured, progressively disclosed information architecture, it prevents AI context-window pollution and "hallucination loops".

## How to use it in a new project

1. Copy the contents of this folder into your new project's root directory.
   - `.clinerules` (or rename to `.cursorrules` / `.windsurfrules` depending on your IDE) goes in the root.
   - `docs/project_map/` goes into your project structure.
2. Initialize your project's unique vision in `projectbrief.md`.
3. In your chat with the AI Agent, trigger the command `[读档]` (Load State). The AI will immediately orient itself to your custom architecture.

## The Magic Triggers
- `[汇报]` (Report): Stops AI from coding and forces it to give a high-level architecture report.
- `[执行测试]` (Run Tests): Forces the AI to clean up old test artifacts before running isolated tests.
- `[存档]` (Save State): Forces the AI to do Garbage Collection (delete temporary patch scripts) and dynamically rewrite `activeContext.md` and `progress.md` before committing to Git.
- `[清理]` (Garbage Collect): Tells the AI to hunt down and delete messy test scripts.

*The Plan IS the Product.*
