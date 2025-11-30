# Auto-Deployer

Auto-Deployer is a CLI-first automation agent that accepts a GitHub repository URL and SSH credentials, then orchestrates cloning, analysis, and deployment planning with the assistance of an LLM. The current milestone delivers the foundational CLI, configuration system, and workflow skeleton so future iterations can plug in real analyzers and executors.

## Features (current milestone)

- CLI command `auto-deployer deploy` with required repository and server parameters.
- JSON-based configuration file that controls retry strategy, workspace locations, and LLM provider metadata.
- Modular package layout (`github`, `ssh`, `analyzer`, `planner`, `executor` placeholders) prepared for future implementations.
- Lightweight workflow engine that logs each step and demonstrates how the agent will proceed once concrete integrations are in place.
- Local workspace manager plus repository analyzer stubs that prepare per-run directories and derive simple language/deployment hints for the LLM.
- Git-backed checkout flow that clones (or pulls) the requested repository into each workspace and records the commit hash for traceability.
- SSH session manager with remote host probing and command execution hooks, enabling end-to-end dry runs of the deployment workflow.
- OpenAI-compatible LLM provider (optional) that can plan deployments and analyze failures, automatically suggesting a fallback action when a step breaks.

## Requirements

- Python 3.10+

## Installation

From the repository root:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Usage

```bash
auto-deployer deploy \
    --repo https://github.com/example/project.git \
    --host 203.0.113.10 \
    --user deploy \
    --auth-method password \
    --password yourpassword
```

Optional flags:

- `--config PATH`: load a custom JSON configuration file.
- `--workspace PATH`: override the local analysis workspace directory.
- `--max-retries N`: temporarily override the retry budget for this run.

## Configuration

A sample configuration lives at `config/default_config.json`. Duplicate it, update sensitive values (for example, LLM API keys), and pass the new path via `--config`.

```json
{
  "llm": {
    "provider": "dummy",
    "model": "planning-v0",
    "api_key": null,
    "endpoint": null,
    "temperature": 0.0
  },
  "deployment": {
    "workspace_root": ".auto-deployer/workspace",
    "default_max_retries": 3
  }
}
```

### LLM providers

- **Dummy** (default): returns static plans, suitable for offline development.
- **OpenAI**: set `"provider": "openai"`, specify `"model"` (e.g. `gpt-4o-mini`) and leave `"api_key": null` to pull from the `AUTO_DEPLOYER_LLM_API_KEY` environment variable. Optional overrides: `endpoint`, `temperature`.
- **Gemini**: set `"provider": "gemini"`, choose a model such as `gemini-1.5-pro`, and either place the key directly in the config or export `AUTO_DEPLOYER_GEMINI_API_KEY`. If `llm.api_key` is omitted, the loader looks for the provider-specific env var first, then falls back to `AUTO_DEPLOYER_LLM_API_KEY`.

When OpenAI or Gemini is active, the workflow will:

1. Send repository insights + remote host facts to generate a plan.
2. Receive free-form shell commands (`command` field) for each step; every command is executed verbatim over the SSH session, so the model has complete control over the deployment flow.
3. On step failure, send error context back to the model to request a remediation, then retry using the suggested action/command.
4. Fall back to the dummy behaviour if the API cannot be reached or returns invalid JSON.

### SSH target defaults

You can store default SSH credentials in the config under `deployment`:

```json
"deployment": {
  "workspace_root": ".auto-deployer/workspace",
  "default_max_retries": 3,
  "default_host": "203.0.113.10",
  "default_port": 22,
  "default_username": "deploy",
  "default_auth_method": "password",
  "default_password": "hunter2",
  "default_key_path": null
}
```

CLI flags still override these values. If you omit a required field (e.g., `host`) from both config and CLI arguments, the command will exit with a clear error.

## Development

Run the unit tests:

```bash
python -m unittest
```

## Roadmap

1. Connect to servers over SSH, collect telemetry, and stream logs. ✅ (initial probe and command execution are now wired.)
2. Promote the LLM from a stub planner to a fully automated problem solver. 🚧 (OpenAI provider + failure repair loop done; next step is richer action generation.)
3. Add deployment transcripts, retry logic, and eventually a web dashboard.
4. Support Docker, Python, and Node templates with ready-made execution strategies.
