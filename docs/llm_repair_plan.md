# LLM Integration & Error Repair Plan

## Objectives

1. **Real LLM provider**: add an OpenAI-compatible client that consumes model, API key, and endpoint from configuration/env vars while keeping the Dummy provider as fallback.
2. **Failure analysis loop**: whenever a workflow step fails, capture the error, solicit the LLM for a remediation suggestion, and retry the step using the recommended action.
3. **Deterministic structure**: normalize LLM outputs into `PlanStep` / `FailureAnalysis` models to keep downstream logic predictable, while still allowing fully free-form shell commands via the `PlanStep.command` field.
4. **Observability & safety**: log summaries of LLM decisions, enforce retry limits, and degrade gracefully when the LLM or network is unavailable.

## Architecture Additions

- `auto_deployer.llm.openai.OpenAILLMProvider`
- `auto_deployer.llm.gemini.GeminiLLMProvider`
  - Uses the Chat Completions endpoint via HTTPS (default `https://api.openai.com/v1/chat/completions`).
  - Pulls API key from `config.llm.api_key` or `AUTO_DEPLOYER_LLM_API_KEY` env var.
  - Generates structured JSON plans and failure analyses, falling back to Dummy provider semantics if parsing fails.
- Gemini provider mirrors the OpenAI flow but targets `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` and consumes `AUTO_DEPLOYER_GEMINI_API_KEY` (or the generic env var) when the config omits `api_key`.
- `LLMProvider` interface
  - `plan_deployment(request, insights, host_facts) -> WorkflowPlan`
  - `analyze_failure(step, error_message, context) -> FailureAnalysis | None`
- `FailureAnalysis` dataclass (summary + optional replacement `PlanStep`).
- Workflow hooks
  - `_run_step` now receives repo/host context and, on exceptions, calls `llm.analyze_failure`.
  - When a suggested `PlanStep` is returned, the workflow retries the step immediately with the new action; otherwise the retry loop proceeds as before.

### Plan Payload Schema

```json
{
  "steps": [
    {
      "title": "Describe the operation",
      "command": "shell command executed remotely",
      "action": "optional hint such as remote:run or noop",
      "details": "optional justification"
    }
  ]
}
```

During failure repair the provider may return:

```json
{
  "summary": "human explanation of the issue",
  "suggested_step": {
    "title": "New step name",
    "command": "replacement command",
    "action": "optional hint",
    "details": "context"
  }
}
```

## Error Context (sent to LLM)

- Deployment request basics (repo, host, attempt number).
- Current `PlanStep` (title/action/details).
- `RepositoryInsights` payload (languages, hints, detected files).
- `RemoteHostFacts` (if any) to signal OS differences.
- Raw exception string from the failed execution.

## Testing Strategy

- Keep network calls out of unit tests by injecting a stub `LLMProvider` into `DeploymentWorkflow`.
- Ensure `_run_step` honors `FailureAnalysis` suggestions (e.g., first attempt fails, LLM replaces action with `noop`, second attempt succeeds).
- Validate configuration loading (env var API key) and pyproject dependencies via unit tests where practical.

## Documentation Updates

- README: describe OpenAI provider, env var usage, and the automatic error-repair loop.
- Mention new doc in Roadmap/changelog section for clarity.
