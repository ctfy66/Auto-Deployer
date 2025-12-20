# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Auto-Deployer is an LLM-driven autonomous deployment tool that analyzes Git repositories and deploys them automatically. It uses a two-phase deployment model (planning + execution) and supports both SSH remote deployment and local deployment modes.

**Core Concept**: The LLM acts as an autonomous agent that observes, thinks, and acts in a loop—analyzing project structure, making deployment decisions, executing commands, and self-correcting when errors occur.

## Development Commands

### Setup
```bash
# Install in editable mode
pip install -e .

# Install with optional memory/knowledge features
pip install -e ".[memory]"
```

### Running Deployments
```bash
# SSH remote deployment
auto-deployer deploy --repo <git-url> --host <ip> --user <username> --auth-method password --password <pass>

# Local deployment (Windows PowerShell or Linux/Mac Bash)
auto-deployer deploy --repo <git-url> --local

# Using the PowerShell wrapper (Windows)
./run_deploy.ps1 --repo <git-url> --local
```

### Testing
```bash
# Run all tests
py -3.12 -m tests.run_tests

# Or using the PowerShell wrapper
./run_tests.ps1

# Run specific test file
python -m pytest tests/test_analyzer.py
python -m pytest tests/test_config.py

# Run real deployment integration tests (requires test environment)
python -m tests.real_deployment.test_suite
```

### Viewing Logs
```bash
# List all deployment logs
auto-deployer logs --list

# View latest deployment
auto-deployer logs --latest

# View specific log file
auto-deployer logs --file agent_logs/deploy_<project>_<timestamp>.json
```

## Architecture

### Deployment Model

The system uses a **two-phase deployment model** (planning + execution):

1. **Planning Phase** (`DeploymentPlanner` in [llm/agent.py](src/auto_deployer/llm/agent.py))
   - LLM analyzes the project and generates a structured `DeploymentPlan`
   - Plan contains: strategy, components, ordered steps, risks, estimated time
   - User can review and approve the plan before execution
   - Controlled by `require_plan_approval` config flag

2. **Execution Phase** (`DeploymentOrchestrator` in [orchestrator/orchestrator.py](src/auto_deployer/orchestrator/orchestrator.py))
   - Executes the plan step-by-step using `StepExecutor`
   - Each step runs in its own isolated LLM loop with max iterations
   - Step failures trigger user interaction: retry/skip/abort

### Core Components

**Workflow Layer** ([workflow.py](src/auto_deployer/workflow.py))
- `DeploymentWorkflow`: Main orchestrator coordinating all phases
- Uses Orchestrator mode (plan-execute architecture)
- Handles both remote SSH and local deployment requests

**Analysis Layer** ([analyzer/repo_analyzer.py](src/auto_deployer/analyzer/repo_analyzer.py))
- `RepoAnalyzer`: Clones repo locally, reads key files (README, package.json, Dockerfile, etc.)
- `RepoContext`: Captures project type, framework, dependencies, build scripts
- Pre-analysis is fed to the LLM to provide context before deployment starts

**Intelligence Layer** ([llm/agent.py](src/auto_deployer/llm/agent.py))
- `DeploymentPlanner`: Creates structured deployment plans via LLM
- Supports multiple LLM providers via provider abstraction

**Orchestration Layer** ([orchestrator/](src/auto_deployer/orchestrator/))
- `DeploymentOrchestrator`: Step-by-step plan execution
- `StepExecutor`: Isolated LLM loop for each step (max iterations per step)
- `DeployContext`: Shared deployment state across steps
- `StepResult`: Tracks success/failure/skipped status per step

**Execution Layer**
- `SSHSession` ([ssh/session.py](src/auto_deployer/ssh/session.py)): Remote command execution via paramiko
  - Auto-handles sudo password prompts
  - Real-time output streaming
- `LocalSession` ([local/session.py](src/auto_deployer/local/session.py)): Local command execution
  - Platform-aware (Windows PowerShell vs Linux/Mac Bash)
  - Real-time output streaming
- Both implement the same `run(command)` interface

**Interaction Layer** ([interaction/handler.py](src/auto_deployer/interaction/handler.py))
- `UserInteractionHandler`: Abstract interface for asking user questions
- `CLIInteractionHandler`: CLI implementation with rich prompts
- Used for plan approval, step failure recovery, configuration decisions

**Knowledge System** ([knowledge/](src/auto_deployer/knowledge/)) - Optional
- `ExperienceStore`: ChromaDB-based vector store for past deployment experiences
- `ExperienceExtractor`: Extracts reusable patterns from deployment logs
- `ExperienceRetriever`: Finds relevant experiences via semantic search
- Only loaded if `chromadb` and `sentence-transformers` are installed

### Key Data Flow

```
CLI Input → DeploymentWorkflow
  ↓
1. RepoAnalyzer.analyze(repo_url) → RepoContext
2. SSH/LocalSession.connect() → Session
3. Probe.collect() → HostFacts
  ↓
[Planning Phase]
4. DeploymentPlanner.create_plan() → DeploymentPlan
5. User approval (if required)
  ↓
[Execution Phase]
6. DeploymentOrchestrator.run(plan, context)
   - For each step:
     - StepExecutor.execute(step_context)
       - LLM loop: observe → think (LLM API) → act (session.run)
     - Handle failures: ask user (retry/skip/abort)
7. Save deployment log (JSON with full conversation history)
8. Auto-extract experiences for knowledge base
```

## Configuration

Configuration lives in [config/default_config.json](config/default_config.json) and can be overridden by environment variables:

**LLM Settings**
- Provider: Supports multiple LLM providers (see [LLM Providers](#llm-providers) section)
- API Keys: Set via environment variables (e.g., `AUTO_DEPLOYER_GEMINI_API_KEY`)
- Temperature: Default 0.0 for deterministic behavior
- Proxy: Optional HTTP/HTTPS proxy for API requests

**Agent Settings**
- `max_iterations`: Total iteration budget (default: 180) - used for step allocation
- `max_iterations_per_step`: Per-step iterations in orchestrator mode (default: 30)
- `require_plan_approval`: Ask user to approve plan (default: false)
- `planning_timeout`: LLM timeout for plan generation (default: 60s)

**Deployment Settings**
- `workspace_root`: Local clone directory (default: `.auto-deployer/workspace`)
- SSH credentials: Can be set via env vars or command-line args

## Important Implementation Details

### Step Execution Model

The system uses a **plan-execute architecture**:
- Each step is executed independently with dedicated iteration budget
- Step-level retries provide fine-grained control
- Steps can access previous step results via `deploy_context.step_results`
- Better failure recovery and controllability compared to monolithic loops

### Step Execution Isolation
Each step in [orchestrator/step_executor.py](src/auto_deployer/orchestrator/step_executor.py):
- Gets its own fresh LLM conversation context
- Has a dedicated iteration budget (`max_iterations_per_step`)
- Can access previous step results via `deploy_context.step_results`
- Maintains its own command history

### Platform-Specific Shell Handling
[local/session.py](src/auto_deployer/local/session.py) automatically detects:
- Windows → Uses PowerShell (via `subprocess` with `powershell -Command`)
- Linux/Mac → Uses Bash
- The LLM is informed of the platform in the system prompt

### SSH Session Auto-Sudo
[ssh/session.py](src/auto_deployer/ssh/session.py) automatically handles sudo:
- Detects password prompts in stderr
- Injects password when needed
- Provides clean stdout/stderr to the agent

### Logging Format
All deployments save to `agent_logs/deploy_<project>_<timestamp>.json`:
- Full conversation history (system prompts, user messages, assistant responses)
- Deployment plan
- Step results
- Command history with outputs
- Final status and metadata

### Experience Extraction
After successful deployment ([workflow.py:510](src/auto_deployer/workflow.py#L510)):
- `ExperienceExtractor` parses the log file
- Extracts patterns: commands run, errors encountered, solutions
- Stores as "raw experiences" (code-based extraction, no LLM refinement)
- Future deployments can retrieve similar experiences via semantic search

## LLM Providers

Auto-Deployer supports multiple LLM providers out of the box. Configure in [config/default_config.json](config/default_config.json) or via environment variables.

### Supported Providers

**Gemini (Google)** - Default, recommended for cost/performance
```json
{
  "provider": "gemini",
  "model": "gemini-2.0-flash-exp"
}
```
Set `AUTO_DEPLOYER_GEMINI_API_KEY` environment variable.

**OpenAI**
```json
{
  "provider": "openai",
  "model": "gpt-4o"
}
```
Set `AUTO_DEPLOYER_OPENAI_API_KEY` environment variable.
Models: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`

**Anthropic Claude**
```json
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022"
}
```
Set `AUTO_DEPLOYER_ANTHROPIC_API_KEY` environment variable.
Models: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`, `claude-3-haiku-20240307`

**DeepSeek**
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat"
}
```
Set `AUTO_DEPLOYER_DEEPSEEK_API_KEY` environment variable.
Models: `deepseek-chat`, `deepseek-coder`

**OpenRouter** (Access multiple models through one API)
```json
{
  "provider": "openrouter",
  "model": "anthropic/claude-3.5-sonnet"
}
```
Set `AUTO_DEPLOYER_OPENROUTER_API_KEY` environment variable.
Models: `anthropic/claude-3.5-sonnet`, `openai/gpt-4o`, `google/gemini-2.0-flash-exp`, etc.

**OpenAI-Compatible** (Ollama, LM Studio, vLLM, Groq, Together AI, etc.)
```json
{
  "provider": "openai-compatible",
  "model": "your-model-name",
  "endpoint": "http://localhost:11434/v1"
}
```
Works with any OpenAI-compatible API endpoint:
- Ollama: `http://localhost:11434/v1`
- LM Studio: `http://localhost:1234/v1`
- vLLM: `http://your-server:8000/v1`
- Together AI: `https://api.together.xyz/v1`
- Groq: `https://api.groq.com/openai/v1`

### Provider Architecture

All providers implement a common interface defined in [llm/base.py](src/auto_deployer/llm/base.py):
- [llm/gemini.py](src/auto_deployer/llm/gemini.py) - Google Gemini
- [llm/openai.py](src/auto_deployer/llm/openai.py) - OpenAI GPT models
- [llm/anthropic.py](src/auto_deployer/llm/anthropic.py) - Anthropic Claude
- [llm/deepseek.py](src/auto_deployer/llm/deepseek.py) - DeepSeek
- [llm/openrouter.py](src/auto_deployer/llm/openrouter.py) - OpenRouter
- [llm/openai_compatible.py](src/auto_deployer/llm/openai_compatible.py) - Generic OpenAI-compatible

## Working with the Codebase

### Adding a New LLM Provider
1. Create a new file in [llm/](src/auto_deployer/llm/) (e.g., `newprovider.py`)
2. Implement the `generate_response()` method matching the interface in [llm/base.py](src/auto_deployer/llm/base.py)
3. Add the provider to `create_llm_provider()` factory in [llm/base.py](src/auto_deployer/llm/base.py)
4. Update [llm/__init__.py](src/auto_deployer/llm/__init__.py) to export it

### Adding a New Interaction Type
1. Extend `InputType` and `QuestionCategory` enums in [interaction/handler.py](src/auto_deployer/interaction/handler.py)
2. Update `CLIInteractionHandler` to handle the new type
3. The agent can now use it via `InteractionRequest`

### Modifying Deployment Steps
- Planning prompts are in [llm/agent.py](src/auto_deployer/llm/agent.py) (`_build_planning_system_prompt`)
- Execution prompts are in [orchestrator/prompts.py](src/auto_deployer/orchestrator/prompts.py)
- Step categories: `prerequisite`, `setup`, `build`, `deploy`, `verify`

### Testing Deployment Changes
- Use the test projects in [tests/real_deployment/test_projects.py](tests/real_deployment/test_projects.py)
- Real integration tests deploy to actual environments (SSH or local)
- Metrics collector tracks success rate, step counts, iteration usage

## Common Patterns

### Checking Prerequisites Before Commands
The agent is trained to check tool availability:
```bash
which node || (echo "Node.js not installed" && exit 1)
```

### Handling Existing Deployments
The agent typically checks if the deploy directory exists:
```bash
if [ -d ~/myproject ]; then cd ~/myproject && git pull; else git clone <repo> ~/myproject; fi
```

### Port Conflict Detection
The agent asks the user for port selection when conflicts are detected:
```python
InteractionRequest(
    question="Port 3000 is in use. Which port should the app use?",
    input_type=InputType.TEXT,
    category=QuestionCategory.CONFIGURATION,
    default="3001"
)
```

## Project-Specific Notes

- The system is designed for **unattended deployments** but can ask for user input at critical decision points
- The LLM decides what commands to run—there are no hardcoded deployment scripts
- Error recovery is LLM-driven: the agent reads error logs and attempts fixes autonomously
- The knowledge system is optional but improves deployment success rates over time
- Windows support is first-class: PowerShell commands work alongside Linux bash commands
- 如果没有明确要求, 输出默认用中文.代码块除外.
