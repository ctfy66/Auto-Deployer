"""Chain of Thought (CoT) Framework for Deep Reasoning.

This module contains templates and utilities to enable systematic, step-by-step
reasoning in LLM responses, improving decision quality and transparency.
"""

# ============================================================================
# Core Chain of Thought Framework
# ============================================================================

CHAIN_OF_THOUGHT_FRAMEWORK = """
# 🧠 Chain of Thought - Systematic Reasoning Process

Before deciding on any action, you MUST follow this structured thinking process:

## Step 1: 观察 (OBSERVE) - What is the current state?
Carefully examine:
- Current deployment stage and progress
- Recent command outputs (stdout, stderr, exit codes)
- Error messages and warnings
- System state (processes, services, files)
- User feedback or instructions

**Output format:**
```
OBSERVATION:
- Current stage: [e.g., "Installing dependencies", "Starting service"]
- Last command result: [success/failure + key outputs]
- System state: [what's running, what exists]
- Issues detected: [any errors, warnings, or anomalies]
```

## Step 2: 分析 (ANALYZE) - What is the goal and what are the constraints?
Clarify:
- What is the immediate goal or objective?
- What are the success criteria?
- What constraints exist (platform, tools available, user preferences)?
- What information is missing or uncertain?

**Output format:**
```
ANALYSIS:
- Goal: [what needs to be achieved]
- Success criteria: [how to verify success]
- Constraints: [limitations, requirements, preferences]
- Uncertainties: [what's unclear or missing]
```

## Step 3: 推理 (REASON) - What are the possible approaches?
Generate and evaluate options:
- List 2-3 possible approaches
- For each approach, identify:
  * Advantages (pros)
  * Disadvantages (cons)
  * Risks and prerequisites
  * Likelihood of success

**Output format:**
```
REASONING:
Option A: [approach description]
  ✅ Pros: [advantages]
  ❌ Cons: [disadvantages]
  ⚠️ Risks: [potential issues]
  📊 Success probability: [high/medium/low]

Option B: [approach description]
  ✅ Pros: [advantages]
  ❌ Cons: [disadvantages]
  ⚠️ Risks: [potential issues]
  📊 Success probability: [high/medium/low]

[Option C if applicable...]
```

## Step 4: 决策 (DECIDE) - What is the best action?
Make a clear decision:
- Which option to choose and why
- What specific action to take
- How to verify the result
- What to do if it fails (fallback plan)

**Output format:**
```
DECISION:
- Chosen approach: [Option X]
- Rationale: [why this option is best given the analysis]
- Specific action: [exact command or question to ask]
- Verification: [how to check if it worked]
- Fallback: [what to do if it fails]
```

## ⚡ Example: Handling a Port Conflict

```
OBSERVATION:
- Current stage: Starting Node.js application
- Last command result: Failed - "Error: listen EADDRINUSE: address already in use :::3000"
- System state: Application not running
- Issues detected: Port 3000 is occupied

ANALYSIS:
- Goal: Start the application on an available port
- Success criteria: Application responds to HTTP requests
- Constraints: User prefers port 3000 but will accept alternatives
- Uncertainties: What process is using port 3000?

REASONING:
Option A: Find and kill the process using port 3000
  ✅ Pros: Frees the preferred port, maintains configuration
  ❌ Cons: Might kill important services, needs sudo
  ⚠️ Risks: Could disrupt other applications
  📊 Success probability: medium (depends on what's using the port)

Option B: Use a different port (e.g., 3001)
  ✅ Pros: Safe, guaranteed to work, no permissions needed
  ❌ Cons: Different from default, might need config changes
  ⚠️ Risks: Low risk
  📊 Success probability: high

Option C: Ask user which approach to take
  ✅ Pros: User gets control, avoids wrong decisions
  ❌ Cons: Requires user interaction, slower
  ⚠️ Risks: None
  📊 Success probability: high (user decides)

DECISION:
- Chosen approach: Option C (ask user)
- Rationale: Port conflicts can be sensitive - user should decide whether to kill existing process or use different port
- Specific action: ask_user with options ["Kill process on port 3000", "Use port 3001", "Use port 8080"]
- Verification: After user choice, execute their decision and verify app responds
- Fallback: If chosen port also fails, try next option from list
```

## 🎯 When to Use Full CoT vs Abbreviated CoT

**Full CoT (all 4 steps)** - Use when:
- Encountering errors or failures
- Multiple valid approaches exist
- Making architectural decisions
- User feedback requires interpretation
- Uncertainty about the best path forward

**Abbreviated CoT (2-3 steps)** - Use when:
- Action is straightforward and obvious
- Following established patterns
- Executing routine commands
- Clear success from previous step

**Example of Abbreviated CoT:**
```
OBSERVATION: Dependencies installed successfully, package.json has "start" script
ANALYSIS: Need to start the application using npm start
DECISION: Execute "npm start" in background with nohup
```

## 🚫 Anti-Patterns to Avoid

❌ **Skipping observation**: Making decisions without checking current state
❌ **Single option reasoning**: Not considering alternatives
❌ **Ignoring constraints**: Choosing options that violate known limitations
❌ **No verification plan**: Not planning how to check if action succeeded
❌ **Repeating failures**: Doing the same thing after it failed without reasoning why it would work now
"""

# ============================================================================
# Planning Phase CoT Template
# ============================================================================

PLANNING_COT_TEMPLATE = """
# 🧠 Planning Phase - Deep Analysis

Before generating the deployment plan, perform deep analysis:

## 1. 项目理解 (Project Understanding)
Analyze the repository structure:
- What type of project is this? (web app, API, static site, microservices)
- What is the tech stack? (languages, frameworks, databases)
- What are the critical dependencies?
- Are there any complex requirements? (multi-stage builds, services, external APIs)

## 2. 环境分析 (Environment Analysis)
Understand the target environment:
- What OS and architecture?
- What tools are already installed?
- Are there any environmental constraints? (container, systemd availability, etc.)
- What are the resource implications?

## 3. 策略推理 (Strategy Reasoning)
Evaluate deployment strategies:
- Docker vs Traditional vs Static?
- What are the trade-offs of each approach for THIS project?
- Which strategy best matches the project structure AND environment?
- What risks exist with each strategy?

## 4. 步骤设计 (Step Design)
Design the deployment steps:
- What are the logical phases? (prerequisites → setup → build → deploy → verify)
- What dependencies exist between steps?
- What could go wrong at each step?
- How can each step be verified?

## 5. 风险评估 (Risk Assessment)
Identify potential issues:
- What's missing? (env files, configs, documentation)
- What could fail? (build errors, port conflicts, missing dependencies)
- What assumptions are being made?
- How can risks be mitigated?

**Output your reasoning in a structured format, then generate the JSON plan.**
"""

# ============================================================================
# Execution Phase CoT Template
# ============================================================================

EXECUTION_COT_TEMPLATE = """
# 🧠 Execution Phase - Systematic Decision Making

For each action, apply the 4-step reasoning process:

## Before Every Command:
1. **OBSERVE**: What's the current state? What do recent outputs tell me?
2. **ANALYZE**: What am I trying to achieve? What are the constraints?
3. **REASON**: What are 2-3 ways to do this? What are the trade-offs?
4. **DECIDE**: Which approach is best? What's my verification plan?

## After Every Command:
1. **OBSERVE**: Did it succeed? What does the output say?
2. **ANALYZE**: Does this meet the success criteria?
3. **REASON**: If failed, what are the root causes and possible fixes?
4. **DECIDE**: Next action (continue, retry with fix, or ask for help)

## When Encountering Errors:
Use the full CoT process to:
- Extract ALL error indicators (not just the first line)
- Build the causal chain from symptom to root cause
- Generate multiple potential solutions
- Choose the most likely solution based on error specifics
- Plan verification and fallback

**Never repeat the same failed command without reasoning about WHY it would work this time.**
"""

# ============================================================================
# Reasoning Output Format
# ============================================================================

REASONING_OUTPUT_FORMAT = """
# 📋 Reasoning Output Format

Your JSON responses should include a "reasoning" field showing your thought process:

## For "execute" actions:
```json
{
  "action": "execute",
  "command": "npm install",
  "reasoning": {
    "observation": "package.json detected with dependencies, no node_modules folder",
    "analysis": "Need to install Node.js dependencies before running the app",
    "alternatives_considered": [
      "npm install - installs locally (BEST for isolation)",
      "npm install -g - installs globally (BAD - pollutes system)"
    ],
    "decision": "Use 'npm install' for local dependency installation",
    "verification": "Check that node_modules/ exists after execution",
    "fallback": "If fails, check Node.js version compatibility"
  }
}
```

## For "ask_user" actions:
```json
{
  "action": "ask_user",
  "question": "Which port should the application use?",
  "options": ["3000", "8080", "3001"],
  "reasoning": {
    "observation": "Port 3000 is occupied, multiple port options in config",
    "analysis": "Need to select an available port, but user preference matters",
    "why_asking": "Port selection is a user preference, and I don't know if the process on 3000 can be killed",
    "decision": "Ask user rather than unilaterally choosing port or killing processes"
  }
}
```

## For "step_done" actions:
```json
{
  "action": "step_done",
  "message": "Dependencies installed successfully",
  "reasoning": {
    "observation": "npm install completed with exit code 0, node_modules/ created with 456 packages",
    "verification": "Checked node_modules exists and package-lock.json updated",
    "success_criteria_met": "All dependencies from package.json are installed",
    "next_expectations": "Ready to build or start the application"
  }
}
```

## For "step_failed" actions:
```json
{
  "action": "step_failed",
  "message": "Cannot start Docker daemon - requires Docker Desktop on Windows",
  "reasoning": {
    "observation": "Error: 'open //./pipe/dockerDesktopLinuxEngine: file not found'",
    "root_cause_analysis": "Docker Desktop application is not running (Windows named pipe missing)",
    "attempts_made": ["Tried to start via service", "Checked process status"],
    "why_failed": "Docker Desktop is a GUI application that must be started manually by user",
    "recommendation": "Switch to traditional deployment strategy or ask user to start Docker Desktop"
  }
}
```
"""

# ============================================================================
# Error Analysis CoT Template
# ============================================================================

ERROR_ANALYSIS_COT = """
# 🔍 Error Analysis - Chain of Thought

When a command fails, follow this systematic error analysis process:

## Phase 1: Information Gathering
```
WHAT I SEE:
- Exit code: [code]
- Stderr output: [full error text]
- Stdout output: [any relevant output]
- Context: [what command was this, what was it trying to do]
```

## Phase 2: Error Decomposition
```
ERROR CHAIN:
1. Generic wrapper error: [high-level error message]
2. Intermediate errors: [more specific errors]
3. Root cause error: [most specific error message]

SPECIFIC INDICATORS:
- File paths mentioned: [list]
- Services mentioned: [list]
- Ports mentioned: [list]
- Permissions mentioned: [list]
```

## Phase 3: Hypothesis Generation
```
POSSIBLE ROOT CAUSES:
Hypothesis 1: [cause]
  - Evidence supporting: [what in the error suggests this]
  - Evidence against: [what contradicts this]
  - Probability: [high/medium/low]

Hypothesis 2: [cause]
  - Evidence supporting: [...]
  - Evidence against: [...]
  - Probability: [high/medium/low]

MOST LIKELY: Hypothesis X because [reasoning]
```

## Phase 4: Solution Planning
```
DIAGNOSTIC STEPS:
1. [command to verify hypothesis]
2. [command to gather more info]

SOLUTION OPTIONS:
Option A: [solution]
  - Will this fix the root cause? [yes/no + why]
  - Side effects: [any risks]

Option B: [alternative solution]
  - Will this fix the root cause? [yes/no + why]
  - Side effects: [any risks]

CHOSEN SOLUTION: Option X because [reasoning]
```

## Example:
```
WHAT I SEE:
- Exit code: 1
- Stderr: "docker: Cannot connect to Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"
- Stdout: (empty)
- Context: Trying to run "docker ps" to check running containers

ERROR CHAIN:
1. Generic: "Cannot connect to Docker daemon"
2. Specific: "unix:///var/run/docker.sock" - Unix socket file issue
3. Question: "Is the docker daemon running?" - Hints at service state

SPECIFIC INDICATORS:
- File paths: /var/run/docker.sock (Docker daemon socket)
- Services: docker daemon
- Platform: Linux (unix:// socket)

POSSIBLE ROOT CAUSES:
Hypothesis 1: Docker service not started
  - Evidence supporting: Error message explicitly asks if daemon is running
  - Evidence against: None
  - Probability: HIGH

Hypothesis 2: Permission issue with socket file
  - Evidence supporting: Socket files can have permission issues
  - Evidence against: Error would typically say "permission denied", not "cannot connect"
  - Probability: LOW

MOST LIKELY: Hypothesis 1 (daemon not started)

DIAGNOSTIC STEPS:
1. systemctl status docker (check service status)
2. ps aux | grep dockerd (check if process exists)

SOLUTION OPTIONS:
Option A: Start Docker service
  - Command: sudo systemctl start docker
  - Will fix: YES - if daemon wasn't started
  - Side effects: None

Option B: Add user to docker group
  - Will fix: NO - this is not a permission issue
  - Side effects: Unnecessary

CHOSEN SOLUTION: Option A - Start Docker service
```
"""

# ============================================================================
# User Feedback Interpretation CoT
# ============================================================================

USER_FEEDBACK_COT = """
# 💬 User Feedback Interpretation - Chain of Thought

When user provides feedback or answers a question, systematically interpret it:

## Phase 1: Understand the Feedback
```
USER SAID: "[exact user message]"

CONTEXT:
- What did I just ask or do?
- Why did I ask/do that?
- What was I expecting?
```

## Phase 2: Classify the Feedback
```
FEEDBACK TYPE:
[ ] Answer to my question (information I requested)
[ ] Instruction/Command (telling me what to do)
[ ] Correction (pointing out my mistake)
[ ] Frustration signal (indicating I'm not listening)
[ ] Clarification request (they need more info)

PRIORITY LEVEL:
[ ] Must follow immediately (explicit instruction)
[ ] Should incorporate (strong preference)
[ ] Nice to have (suggestion)
```

## Phase 3: Extract Actionable Items
```
WHAT USER WANTS:
1. [action item 1]
2. [action item 2]

WHAT I SHOULD CHANGE:
1. [behavior to change]
2. [approach to modify]

WHAT I SHOULD NOT DO:
1. [thing to avoid]
2. [question not to ask again]
```

## Phase 4: Plan Response
```
MY NEXT ACTION:
- Immediate action: [what to do right now]
- Why this addresses user's feedback: [reasoning]
- How to avoid similar issues: [preventive measure]
```

## Example:
```
USER SAID: "Split the cd and source commands into two separate executions"

CONTEXT:
- I just tried: cd /app && source venv/bin/activate
- It failed with "activate: no such file"
- I asked user for help

FEEDBACK TYPE:
[X] Instruction/Command
[ ] Answer to question
[ ] Frustration signal

PRIORITY LEVEL:
[X] Must follow immediately

WHAT USER WANTS:
1. Execute "cd /app" as one command
2. Execute "source venv/bin/activate" as a separate command
3. Do NOT combine them with &&

WHAT I SHOULD CHANGE:
1. Stop using && to chain cd with other commands
2. Execute directory changes separately

WHAT I SHOULD NOT DO:
1. Ask the same question again
2. Try cd && source again

MY NEXT ACTION:
- Immediate: Execute "cd /app" alone, verify success
- Then: Execute "source venv/bin/activate" alone
- Why this works: Each command runs in the right context, avoiding path issues
```
"""

# ============================================================================
# Helper Functions
# ============================================================================

def get_cot_framework(phase: str = "execution") -> str:
    """Get the appropriate Chain of Thought framework for a given phase.

    Args:
        phase: "planning", "execution", "error_analysis", or "user_feedback"

    Returns:
        Formatted CoT framework string
    """
    frameworks = {
        "planning": PLANNING_COT_TEMPLATE,
        "execution": EXECUTION_COT_TEMPLATE,
        "error_analysis": ERROR_ANALYSIS_COT,
        "user_feedback": USER_FEEDBACK_COT,
    }

    base = CHAIN_OF_THOUGHT_FRAMEWORK
    specific = frameworks.get(phase, EXECUTION_COT_TEMPLATE)

    return f"{base}\n\n{specific}\n\n{REASONING_OUTPUT_FORMAT}"


def get_reasoning_requirements(detailed: bool = True) -> str:
    """Get reasoning output requirements.

    Args:
        detailed: If True, require full 4-step CoT. If False, allow abbreviated CoT.

    Returns:
        Requirements string for reasoning output
    """
    if detailed:
        return """
## Reasoning Requirements (MANDATORY)

Every action must include a "reasoning" field with:
1. **observation**: What you see in the current state
2. **analysis**: What you're trying to achieve and constraints
3. **alternatives_considered**: 2-3 options you evaluated (or explain why only one option)
4. **decision**: Why you chose this specific action
5. **verification**: How you'll check if it worked
6. **fallback**: What to do if it fails

This reasoning will be logged and helps improve the system over time.
"""
    else:
        return """
## Reasoning Requirements

Include a "reasoning" field explaining:
- **observation**: Current state
- **decision**: Why this action
- **verification**: How to check success (for execute actions)
"""
