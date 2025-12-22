# AI Coding Agent Specification (specs.md)

This document defines the technical specifications for the AI Coding Agent, a multi-agent command-line tool designed for high-quality software development.

## 1. Technology Stack

- **Language**: Python 3.9+
- **LLM Integration**: DashScope (Qwen, OpenAI-compatible API)
- **Search API**: Tavily API
- **CLI Framework**: `rich`
- **Orchestration**: AutoGen (Multi-Agent framework)
- **Environment Management**: `python-dotenv` (Per-agent model configurations)
- **Data Validation**: `pydantic`

## 2. Multi-Agent Architecture

The system utilizes a specialized multi-agent design based on AutoGen.

### Roles and Responsibilities

- **Product Manager (PM) / Architect**
    - **Responsibility**: Analyzes requirements, designs file structures, and API definitions.
    - **Output**: `specs.md`, `todo_list`.
- **Coder (Developer)**
    - **Responsibility**: Implements specific code based on architectural design.
    - **Key Tools**: `read_file`, `write_file`, `insert_code`, `search_code`.
- **Reviewer (Code Critic)**
    - **Responsibility**: Audits code for bugs, standards, and logic issues.
    - **Output**: Approval or corrective feedback.
- **Tester (QA)**
    - **Responsibility**: Writes/runs tests and observes runtime behavior.
    - **Key Tools**: `execute_shell`.

### Orchestration Flow (via AutoGen GroupChat)

1. **User Input** -> PM/Architect defines the plan.
2. **Implementation Round** -> Coder implements tasks.
3. **Verification Loop**:
   - Reviewer audits code -> If fail, loop to Coder.
   - Tester runs code -> If fail, loop to Coder.
4. **Final Closure** -> Feedback summarized to User.

## 3. Advanced Design Dimensions

### A. Context Loading Strategy
To optimize token usage and accuracy:
- **Level 1 (Mandatory)**: Current file tree, active task List from `.ca/`, latest error logs.
- **Level 2 (On-Demand)**: Full file content retrieved via `read_file` by Coder.
- **Level 3 (Semantic Search)**: Keyword search or `grep` wrappers for cross-file discovery.

### B. State Management & Interrupt Protection
- **Iteration Limit**: Maximum 5 iterations between Coder and Reviewer/Tester per task before requiring user intervention.
- **Persistence**: session state saved in `.ca/state.json`. Agents can resume from the last completed task in the `todo_list`.

### C. Security & Safety (Safety Policy)
| Action                     | Policy                                      |
| :------------------------- | :------------------------------------------ |
| Read/Search File           | Auto-approve                                |
| Run Test (Non-destructive) | Auto-approve                                |
| Write/Overwrite File       | **User Confirmation [Y/n]**                 |
| Execute Shell              | **Explicit Warning & User Confirmation**    |
| **High-Risk Cmds**         | **Hard Block** (e.g., `rm -rf /`, `curl     | sh`) |
| **System Dir**             | **Hard Block** (e.g., `.git/` modification) |

### D. Refined Tool API Design
- `insert_code(path, line_number, content)`: Precise insertion to avoid full file rewrites.
- `search_code(query, path)`: Grep-like functionality for code discovery.
- `execute_shell(command)`: Restricted execution environment.

## 4. Storage & Workspace Management
- **Local Cache**: `.ca/` for metadata, indices, and snapshots.
- **Sandbox**: `playground/` for isolated development and testing.
- **Undo Capability**: Simple file backup in `.ca/` before any write operation.

## 5. Roadmap

### Phase 1: Multi-Agent Hub
- [ ] AutoGen integration and model mapping logic.
- [ ] Base role definitions and system prompts.

### Phase 2: Power Tools
- [ ] Implement `insert_code` and `search_code`.
- [ ] Implement security middleware for shell/write operations.

### Phase 3: Robustness & Observability
- [ ] Token/Cost tracking in CLI.
- [ ] Task snapshot and `undo` functionality.
- [ ] Dialogue history compression for long sessions.
