# Sub-Directory Rules (.ai-operation/rules.d/)

Place module-specific or directory-specific rule files here.
They will be automatically discovered and merged into the system prompt
by `aio__force_architect_read` during [读档].

## Naming Convention

```
rules.d/
├── api.md          ← Rules for src/api/ directory
├── database.md     ← Rules for database modules
├── frontend.md     ← Rules for frontend code
└── testing.md      ← Rules for test conventions
```

## Format

Each file is plain markdown. Example:

```markdown
# API Module Rules (scope: src/api/)

- All endpoints must return JSON with `status` and `data` fields
- Error responses use HTTP status codes, never 200 with error body
- Rate limiting is handled at gateway level, do not implement in handlers
```

## How It Works

1. During [读档], the MCP tool scans this directory
2. Each .md file is read (subject to 4KB per-file budget)
3. Content is appended to the dynamic context section of the system prompt
4. Most specific rules override general rules (by convention, not enforcement)

## Budget

- Max 4KB per rule file
- Contributes to the 12KB total prompt budget
- Files exceeding budget are truncated with [truncated] marker
