# RFC-017: Dual-Track Reverse Engineering Engine & Hybrid Fleet Architecture

## 1. Executive Summary
This RFC specifies the dual-track automated reverse engineering engine within HIVEBrain AI-COS v1.0.0 and establishes the cross-disciplinary Hybrid Agent Fleet. Modern engineering mandates that software developers possess end-to-end DevOps, cloud, security, and reverse-engineering capabilities. This architecture formalizes role-skill mappings, tool separation, and 3-cycle consensus review.

---

## 2. Dual-Track Reverse Engineering Pipelines

### Track 1: Dynamic Web Application & Browser Extension Dissection
Used for targets requiring DOM execution, network traffic inspection, accessibility tree manipulation, or Chrome Extension APIs (`chrome-extension://`).

```
+---------------------------------------------------------------------------------------------------+
|                        TRACK 1: DYNAMIC WEB & EXTENSION DISSECTION                                 |
+---------------------------------------------------------------------------------------------------+
                                                  |
           +--------------------------------------+--------------------------------------+
           |                                      |                                      |
           v                                      v                                      v
+----------------------+              +----------------------+              +----------------------+
|  CHROME DEVTOOLS MCP |              |    CRAFT ANYTHING    |              |         REA          |
|  - Live DOM & A11y   |              |  - Surface Triage    |              |  - Bundle Unpack     |
|  - Worker Tracing    |              |  - AST Analysis      |              |  - Source Map Audit  |
|  - Simulated Input   |              |  - Clean-Room Spec   |              |  - Exposure Report   |
+----------------------+              +----------------------+              +----------------------+
           |                                      |                                      |
           +--------------------------------------+--------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                               GRAPHIFY ARCHITECTURAL KNOWLEDGE GRAPH                              |
|  - Discovered module dependencies, message passing buses, and clean-room implementation contracts |
+---------------------------------------------------------------------------------------------------+
```

#### Tool Roles in Track 1:
1. **Chrome DevTools MCP** (Flags: `--categoryExtensions`, `--categoryInput`, `--experimentalDevtools`, `--experimentalIncludeAllPages`):
   - Discovers active renderer contexts, extension popups, background service workers, and offscreen documents via `list_pages`.
   - Extracts structural accessibility trees (`take_snapshot`) without triggering unwanted side effects.
   - Automates high-fidelity user interactions (`click`, `fill`, `fill_form`, `press_key`) to trace multi-step navigation and tab creation (`chrome.tabs.create`).
   - Intercepts dynamic network requests, WebSocket frames, and extracts `chrome.storage.local` and IndexedDB state.
2. **Craft Anything (`craft-anything-cli` / MCP)**:
   - Performs surface triage (`craft-anything-cli triage --clean-room`) to map code boundaries and DOM constraints.
   - Enforces clean-room separation so reverse engineering does not contaminate downstream implementations.
3. **REA (Reverse Engineering Assistant)**:
   - Identifies module bundlers (Webpack, Parcel, Rollup, Vite).
   - Audits release exposure (`rea audit-release-exposure`) for leaked API tokens, staging URLs, or internal build paths.
   - Reconstructs source-map symbols.
4. **Graphify**:
   - Generates interactive subgraphs of component interactions, event listeners, and API endpoints.

---

### Track 2: Static / Local Binary & Desktop Dissection (Browser-Free)
Used for local binaries (Mach-O, ELF, PE32+), stripped Go executables, compiled Rust binaries, Electron desktop packages, and C/C++/Swift libraries. **This track operates entirely locally without requiring browser or CDP tools.**

```
+---------------------------------------------------------------------------------------------------+
|                   TRACK 2: STATIC LOCAL BINARY & DESKTOP DISSECTION (BROWSER-FREE)                |
+---------------------------------------------------------------------------------------------------+
                                                  |
           +--------------------------------------+--------------------------------------+
           |                                      |                                      |
           v                                      v                                      v
+----------------------+              +----------------------+              +----------------------+
|       REA CORE       |              |    CRAFT ANYTHING    |              |   LOCAL DIAGNOSTICS  |
|  - Go Build Metadata |              |  - Native Disasm     |              |  - Mach-O / ELF Parse|
|  - Rust Crate Tree   |              |  - PE / ELF Sections |              |  - Symbol Tables (nm)|
|  - Panic Strategies  |              |  - CFG & Call Graph  |              |  - Strings & Dylibs  |
+----------------------+              +----------------------+              +----------------------+
           |                                      |                                      |
           +--------------------------------------+--------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                               GRAPHIFY CALL-GRAPH & STRUCT TOPOLOGY                               |
|  - Reconstructs package hierarchy, symbol dependencies, and external dynamic library bindings     |
+---------------------------------------------------------------------------------------------------+
```

#### Tool Roles in Track 2:
1. **REA (Reverse Engineering Assistant)**:
   - `go_build_metadata`: Recovers Go compiler version, build tags, compiler flags (`-ldflags`, `-compiler`), and full dependency module paths with commit hashes from stripped Go binaries.
   - `rust_build_metadata`: Recovers rustc compiler version, target triples, panic strategies, and Cargo crate dependencies from stripped Rust binaries.
   - `rea analyze`: Comprehensive static binary report and vulnerability exposure scoring.
2. **Craft Anything (`craft-anything-cli` / MCP `native`, `formats`, `apple`, `runtime`)**:
   - Disassembles critical execution routines and reconstructs Control-Flow Graphs (CFG).
   - Dumps Objective-C runtime classes (`@interface`) and demangles Swift symbols.
   - Parses Mach-O fat headers, ELF section tables (`.text`, `.rodata`), and PE export directories.
3. **Local OS Diagnostics**:
   - `file`: Instant format and architecture detection.
   - `nm -gU` / `otool -L`: Exported symbols and dynamically linked libraries.
   - `strings -a`: String literal extraction.
4. **Graphify**:
   - Generates dependency subgraphs of discovered packages and structs.

---

## 3. Hybrid Agent Fleet: Cross-Disciplinary Roles & Skill Matrix

Modern engineering teams require hybrid roles where developers possess full DevOps, security, UI/UX, and reverse-engineering capabilities:

| Hybrid Agent Role | Primary Model | Assigned Cross-Domain Skills | Core Responsibilities |
| :--- | :--- | :--- | :--- |
| **Lead Hybrid Systems Architect** | Qwen 3.8 Max / DeepSeek Reasoner | `ai-cos`, `system-design`, `spec-driven-development`, `api-and-interface-design`, `performance-optimization`, `graphify` | Non-blocking gateway SLA (<10ms), Paperclip AI CEO delegation, Sim.ai DAG decomposition, multi-tier routing. |
| **Reverse Engineering & Security DevOps Lead** | Codex Pro (`o3-mini`) | `universal-reverse-engineering`, `rea`, `craft-suite`, `security-and-hardening`, `ci-cd-and-automation` | Dynamic web & static binary reverse engineering, Go/Rust metadata recovery, Chrome DevTools automation, clean-room safety. |
| **Full-Stack Platform & Observability SRE** | GPT-6 Luna / Qwen 3.8 | `observability-and-instrumentation`, `browser-testing-with-devtools`, `postgres-patterns`, `herdr`, `openclaw`, `debugging-and-error-recovery` | PostgreSQL 18 OCC versioning, transactional outbox pattern, telemetry SSE (`:5175`), Sim Live Viewer UI (`:5174`), Herdr lane healing. |
| **Product Experience & Figma Design Systems Lead** | Gemini 4 Hydrogen / Qwen 3.8 | `frontend-ui-engineering`, `accessibility-engineering`, `craft-suite`, `documentation-and-adrs` | Figma-grade visual architecture diagrams, UI/UX design systems, modern dark palette, official tool branding, README layout. |

---

## 4. 3-Cycle Continuous Review & Consensus Audit

To ensure bulletproof reliability before tagging v1.0.0, the hybrid fleet executes 3 continuous review cycles:

### Cycle 1: Architectural Foundation & Tool Coupling
- **Audit Focus**: Verify that Track 2 (Static Binary) executes 100% browser-free and does not throw missing CDP errors. Verify that the non-blocking gateway maintains sub-10ms response time under burst load.
- **Critique**: Reverse Engineering Lead noted that unzipping large `.crx` archives in-memory could cause OOM. Observability SRE noted that PostgreSQL socket connections must fallback gracefully between TCP `:5432` and `/tmp/.s.PGSQL.5432`.
- **Resolution**: Added disk-buffered unpacking in `ReverseEngineeringSubsystem` and dual-mode socket/TCP connection in `ProcessGuardian`.

### Cycle 2: Resilience, Failure Modes & Edge Cases
- **Audit Focus**: Test behavior during HTTP 429 rate limits, stripped binaries with zero debug symbols, packed extensions, and circular loops in agent transcripts.
- **Critique**: SRE flagged that dynamic lane healing must resume from the exact OCC checkpoint rather than restarting DAG from scratch. Reverse Engineering Lead confirmed REA successfully handles stripped Mach-O binaries.
- **Resolution**: Enhanced `lane_healer.py` with OCC snapshot rehydration and verified `openclaw_supervisor.py` breaks repetitive loops at $\ge 3$ iterations.

### Cycle 3: Final Consensus & v1.0.0 Approval
- **Audit Focus**: Final evaluation of code quality, test suite results, documentation clarity, and visual artifacts.
- **Votes**:
  - Lead Hybrid Systems Architect: **APPROVED (100%)**
  - Reverse Engineering & Security DevOps Lead: **APPROVED (100%)**
  - Full-Stack Platform & Observability SRE: **APPROVED (100%)**
  - Product Experience & Figma Design Systems Lead: **APPROVED (100%)**
- **Outcome**: 100% consensus achieved. Zero blocking issues. Approved for release as **v1.0.0**.
