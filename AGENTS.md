# Project Agent Rules & Multi-Model Collaboration

This project has access to a unified **Multi-Model AI Fleet** via local MCP bridges and APIs.

## 1. Available Model Bridges

- **`codex-bridge`** (`/usr/local/bin/codex`):
  - Local OpenAI CLI with **Full Access** (`danger-full-access` and `approval: never`) under ChatGPT Pro.
  - Used for: Workspace file mutations, git diff reviews (`codex_review`), and deep debugging (`codex_reason`).

- **`multi-bridge`** (`auto_route_task`, direct tools):
  - **Tier 1 (Free First)**: APInex free models (`free/qwen-3.8-max`, `free/gpt-6-luna`, `free/gemini-4-hydrogen`, `free/kimi-k3`).
  - **Tier 2 (Paid High Assurance)**: Direct Official DeepSeek API (`deepseek-chat`, `deepseek-reasoner` / R1).
  - **Circuit Breaker**: Protects the user's $50 DeepSeek balance from accidental drain if APInex hits 429.

## 2. Collaboration Heuristics

1. **Coding & Implementation**: Use `auto_route_task(task_type="coding")` or `ask_qwen` for free, fast code generation.
2. **Reviewing Diffs & Commits**: Use `codex_review` to audit git changes before committing.
3. **Complex Reasoning & Bug Fixes**: Use `codex_reason` (`o3-mini`) or `ask_deepseek_direct(model="deepseek-reasoner")`.
4. **Structured Schemas & JSON**: Use `auto_route_task(task_type="schema")` or `ask_gpt`.
5. **Cross-Checking & Consensus**: Use `compare_models` to get a second opinion across Qwen, GPT, and DeepSeek.

## 3. Global Tools & Skills Architecture

All imported MCP servers and skills are installed globally and accessible by **any model** (Antigravity, DeepSeek, Qwen, GPT, etc.):
- **Global MCP Servers**: Registered in `~/.gemini/config/mcp_config.json` (40 servers including Go Language Server `gopls`, Sim.ai, 19 Craft Suite apps, Chrome DevTools, GitHub Copilot, GCloud, Databricks, OpenDots, Paperclip, OpenClaw, Herdr, REA, God's Eye View, ECC Memory, etc.).
- **Global Background Supervisor (`serversctl`)**: Compiled native Go tool (`/Users/nishant/.local/bin/serversctl`) that monitors, starts, and stops all background services (`serversctl status`, `serversctl start`, `serversctl stop`, `serversctl json`).
- **Global Skills**: Registered in `~/.gemini/config/skills/` (46 skills including `sim-ai`, `system-design`, `craft-suite`, `scorm-to-courseware`, `notebook-to-audioscript`, `graphify`, `paperclip`, `opendots`, `openclaw`, `herdr`, `rea`, `gods-eye-view`, `ecc`, and full Addy Osmani engineering skills).
- **System Design Knowledge Vault**: 28-chapter architectural reference notes library installed locally at `/Users/nishant/.local/share/reference-notes/system-design-notes/` and cross-linked into `system-design`, `api-and-interface-design`, `performance-optimization`, `spec-driven-development`, `postgres-patterns`, `observability-and-instrumentation`, and `security-and-hardening`.
- **Codex Auto-Sync**: Whenever new MCP servers or skills are added to Codex, running `/Library/Developer/CommandLineTools/usr/bin/python3 ~/.gemini/config/scripts/sync_codex.py` automatically detects and imports them into Antigravity's global setup.

## 4. Specialized Local Infrastructure & Engines

The following 8 engines are configured globally for deep access:
1. **Graphify** (`graphify` MCP, `graphify` skill, `/Users/nishant/.local/bin/graphify`): Codebase knowledge graph, god nodes, dependency subgraphs, PR impact. Dynamically finds `graphify-out/graph.json` per workspace with fallback.
2. **Paperclip** (`paperclip` MCP, `paperclip` skill, `http://127.0.0.1:3100`): Agent task boards, issue tracking, company and project management.
3. **OpenDots** (`opendots` MCP, `opendots` skill, `http://127.0.0.1:4310`): Collaborative document workspace, wiki, technical specs, and architecture notes.
4. **OpenClaw** (`openclaw` MCP, `openclaw` skill, `ws://127.0.0.1:18789`, `http://127.0.0.1:18789/`): Cross-agent conversation history, session inspection, and multi-agent transcript auditing.
5. **Herdr** (`herdr` MCP, `herdr` skill, `/Users/nishant/.local/bin/herdr`): Terminal multiplexer monitoring, active panes, and background worker agent supervision.
6. **REA** (`rea` MCP, `rea` skill): Reverse engineering assistant, compiled Go and Rust binary build metadata extraction, dependency audit.
7. **God's Eye View** (`gods-eye-view` MCP, `gods-eye-view` skill, `http://127.0.0.1:4173`): Geospatial intelligence, live USGS earthquakes, NASA active fires, and global weather radar layers.
8. **ECC** (`ecc-memory` MCP, `ecc` skill, `/Users/nishant/.local/bin/ecc`): Universal persistent cross-agent memory vault (`memory_search`, `memory_read`, `memory_doctor`), multi-harness state synchronization, and engineering workflows.

## 5. Autonomous AI Company Operating System (AI-COS) & Non-Blocking Gateway

- **Default Workflow Requirement**: For any task, project, research, or engineering request assigned to Antigravity, the Main Agent **MUST NOT** block or wait synchronously for long-running workflows.
- **Instant Gateway Dispatch**: Call `aicos_dispatch(prompt=...)` or `gateway.submit_request(...)`. The task is enqueued into HIVEBrain and handed off to the Second Agent (Paperclip AI CEO) in $<5\text{ms}$.
- **Return Immediate Confirmation**: Immediately reply to the user with the tracking token, run ID, and live dashboard URL (`http://localhost:5174/`).
- **Parallel Fleet & Self-Healing**: The AI CEO micro-plans the task across isolated Herdr lanes (`lane_research`, `lane_schema`, `lane_code`, `lane_audit`), audits sessions via OpenClaw, and auto-heals rate limits by promoting pre-planned backup models from HIVEBrain checkpoints.
- **Process Guardian**: `ProcessGuardian` in `hivebrain_mcp.py` automatically boots all services (telemetry, live viewer, daemon) upon Antigravity startup and terminates them cleanly when Antigravity closes.

