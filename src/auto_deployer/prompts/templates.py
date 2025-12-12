"""Reusable prompt templates and fragments.

This module contains common prompt fragments that are used across multiple
prompts to ensure consistency and reduce duplication.

For Chain of Thought reasoning templates, see cot_framework.py
"""

# ============================================================================
# User Interaction Guide
# ============================================================================

USER_INTERACTION_GUIDE = """
# 🗣️ User Interaction

You can ask the user for input when needed:

**When to ask:**
- Multiple deployment options available (dev/prod mode, ports, etc.)
- Missing information (environment variables, configuration values)
- Confirmation needed before risky operations (deleting data, overwriting)
- Error recovery: when stuck, ask user for guidance

**How to ask:**
```json
{{
  "action": "ask_user",
  "question": "Clear question for the user",
  "options": ["Option 1", "Option 2", "Option 3"],
  "input_type": "choice",
  "category": "decision",
  "context": "Additional context to help user decide",
  "default": "Option 1",
  "reasoning": "Why you need user input"
}}
```

**input_type options:**
- "choice": User selects from options (can also input custom value)
- "text": Free text input
- "confirm": Yes/No confirmation
- "secret": Sensitive input (password, API key)

**category options:**
- "decision": Deployment choices (port, mode, entry point)
- "confirmation": Confirm risky operations
- "information": Need additional info (env vars)
- "error_recovery": Stuck and need user help

**Examples:**
1. Multiple npm scripts available → Ask which to use
2. Unclear which port the app uses → Ask user
3. Need environment variables → Ask for values
4. Before `rm -rf` on existing deployment → Confirm
5. Deployment keeps failing → Ask user for guidance
"""

# ============================================================================
# Environment Isolation Rules (Critical for Python/Node.js)
# ============================================================================

ENVIRONMENT_ISOLATION_PYTHON = """
## Python Projects (MANDATORY Virtual Environment)

1. **Create virtual environment** before installing packages:
   ```bash
   python3 -m venv venv
   # or if python3 not available:
   python -m venv venv
   ```

2. **Activate virtual environment**:
   ```bash
   source venv/bin/activate
   ```

3. **Verify activation** (should see venv in path):
   ```bash
   which python  # Should show path containing /venv/
   ```

4. **Install dependencies** in isolated environment:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run application** using venv Python:
   ```bash
   python app.py
   # or explicitly:
   ./venv/bin/python app.py
   ```

6. **For background processes**:
   ```bash
   nohup ./venv/bin/python app.py > app.log 2>&1 &
   ```

**Why this matters:**
- ❌ WITHOUT venv: `pip install flask` → installs to system Python → conflicts
- ✅ WITH venv: `pip install flask` → installs to venv → isolated
"""

ENVIRONMENT_ISOLATION_NODEJS = """
## Node.js Projects (MANDATORY Local Dependencies)

1. **NEVER use `npm install -g`** (global install pollutes system)

2. **Install dependencies locally**:
   ```bash
   npm install
   ```

3. **Use npx to run tools** (uses local node_modules):
   ```bash
   npx pm2 start app.js
   npx nodemon server.js
   ```

4. **Or use package.json scripts**:
   ```bash
   npm start
   npm run dev
   ```

**Why this matters:**
- ❌ WITHOUT local: `npm install -g pm2` → global install → version conflicts
- ✅ WITH local: `npx pm2` → uses local version → no conflicts
"""

ENVIRONMENT_ISOLATION_DOCKER = """
## Docker Projects (Best Isolation)

Docker already provides complete isolation - use it when Dockerfile is present:
```bash
docker-compose up -d --build
# or
docker build -t myapp .
docker run -d -p 3000:3000 myapp
```

No additional isolation steps needed with Docker.
"""

ENVIRONMENT_ISOLATION_PYTHON_WINDOWS = """
## Python Projects on Windows (MANDATORY Virtual Environment)

1. **Create virtual environment**:
   ```powershell
   python -m venv venv
   ```

2. **Activate virtual environment**:
   ```powershell
   .\venv\Scripts\Activate.ps1
   # If execution policy blocks it:
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   .\venv\Scripts\Activate.ps1
   ```

3. **Verify activation**:
   ```powershell
   Get-Command python | Select-Object Source
   # Should show path containing \venv\Scripts\
   ```

4. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

5. **Run application**:
   ```powershell
   python app.py
   # or explicitly:
   .\venv\Scripts\python.exe app.py
   ```

6. **For background processes**:
   ```powershell
   Start-Process -NoNewWindow -FilePath ".\venv\Scripts\python.exe" -ArgumentList "app.py" -RedirectStandardOutput "app.log"
   ```

**Why this matters:**
- ❌ WITHOUT venv: `pip install flask` → system Python → conflicts
- ✅ WITH venv: `pip install flask` → isolated venv → safe
"""

ENVIRONMENT_ISOLATION_NODEJS_WINDOWS = """
## Node.js Projects on Windows (MANDATORY Local Dependencies)

1. **NEVER use `npm install -g`** (global install pollutes system)

2. **Install dependencies locally**:
   ```powershell
   npm install
   ```

3. **Use npx to run tools**:
   ```powershell
   npx pm2 start app.js
   npx nodemon server.js
   ```

4. **Or use package.json scripts**:
   ```powershell
   npm start
   npm run dev
   ```

**Why this matters:**
- ❌ WITHOUT local: `npm install -g pm2` → global → version conflicts
- ✅ WITH local: `npx pm2` → local → no conflicts
"""

# ============================================================================
# Deployment Strategies
# ============================================================================

DEPLOYMENT_STRATEGY_DOCKER_COMPOSE = """
### Strategy 1: Docker Compose (BEST for complex projects)

If you see `docker-compose.yml` or `docker-compose.yaml`:
```bash
cd ~/app && docker-compose up -d --build
```

- Handles ALL dependencies automatically
- Multi-service projects work out of the box
- Just verify with `docker-compose ps` and `curl`
"""

DEPLOYMENT_STRATEGY_DOCKER = """
### Strategy 2: Docker (if only Dockerfile)

If you see `Dockerfile` but no compose file:
```bash
cd ~/app && docker build -t myapp . && docker run -d -p <port>:<port> myapp
```
"""

DEPLOYMENT_STRATEGY_TRADITIONAL_PYTHON = """
### Strategy 3a: Traditional Python Deployment

**MANDATORY: Use Virtual Environment**

```bash
cd ~/app

# STEP 1: Create virtual environment (MANDATORY)
python3 -m venv venv

# STEP 2: Activate virtual environment (MANDATORY)
source venv/bin/activate

# STEP 3: Verify activation
which python  # Should show ~/app/venv/bin/python

# STEP 4: Install dependencies in isolated environment
pip install -r requirements.txt

# STEP 5: Run with venv Python
python app.py
# or for background:
nohup ./venv/bin/python app.py > app.log 2>&1 &
```

**Why environment isolation is mandatory:**
- ❌ `pip install flask` → System Python → conflicts with other projects
- ✅ `source venv/bin/activate && pip install flask` → Isolated → safe
"""

DEPLOYMENT_STRATEGY_TRADITIONAL_NODEJS = """
### Strategy 3b: Traditional Node.js Deployment

**MANDATORY: Use Local Dependencies**

```bash
cd ~/app

# STEP 1: Install dependencies locally (NEVER use -g)
npm install

# STEP 2: Build if needed
npm run build

# STEP 3: Start application
# Option A: Use npm scripts
npm start
# Option B: Use local PM2
npm install pm2  # Local, NOT global
npx pm2 start server.js --name myapp
# Option C: Background with nohup
nohup node server.js > app.log 2>&1 &
```

**Why environment isolation is mandatory:**
- ❌ `npm install -g pm2` → Global → version conflicts
- ✅ `npm install pm2 && npx pm2` → Local → per-project isolation
"""

DEPLOYMENT_STRATEGY_STATIC = """
### Strategy 4: Static Site

If it's just HTML/CSS/JS:
```bash
# Build if needed
npm run build

# Serve with Python (in venv if possible)
cd dist && python3 -m http.server 8080

# Or use npx serve (local)
npx serve -s dist -l 3000
```
"""

# ============================================================================
# Action Definitions
# ============================================================================

AVAILABLE_ACTIONS_JSON = """
# Available Actions (respond with JSON only)

**Execute command:**
```json
{{"action": "execute", "command": "your command", "reasoning": "why"}}
```

**Ask user:**
```json
{{"action": "ask_user", "question": "...", "options": [...], "input_type": "choice", "category": "decision"}}
```

**Done:**
```json
{{"action": "done", "message": "success message"}}
```

**Failed:**
```json
{{"action": "failed", "message": "error message"}}
```
"""

# ============================================================================
# Error Diagnosis Framework
# ============================================================================

ERROR_DIAGNOSIS_FRAMEWORK = """
# Error Diagnosis Framework (CRITICAL)

When a command fails, follow this systematic reasoning process:

## Step 1: Extract All Error Indicators
Look at the FULL stderr output and identify ALL error messages:
- Lines with "error", "failed", "cannot", "unable", "denied", "not found"
- Exception traces and stack traces
- Exit codes and their meanings
- Quote the EXACT error messages

## Step 2: Classify Each Error
For each error message, determine:
- Is this a SYMPTOM (e.g., "connection refused") or ROOT CAUSE (e.g., "service not running")?
- Specificity level: SPECIFIC (mentions exact file/service/port) vs GENERIC (vague error)
- Category: service, network, permission, filesystem, dependency, configuration, etc.

## Step 3: Build the Causal Chain
Trace the error chain from symptom to root cause:
Example for Docker error:
  "unable to connect" (symptom)
  → WHY? "error during connect" (intermediate)
  → WHY? "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file" (specific)
  → ROOT CAUSE: Docker Desktop service is not running

## Step 4: Prioritize by Specificity
The MOST SPECIFIC error is usually the root cause:
- "The system cannot find the file //./pipe/dockerDesktopLinuxEngine" (SPECIFIC)
  is more informative than
- "Cannot connect to Docker daemon" (GENERIC)

Focus on the specific error! Don't get distracted by generic wrapper messages.

## Step 5: Context-Aware Diagnosis
Consider the platform and environment:
- Linux: /var/run/docker.sock, systemctl, journalctl
- Windows: Named pipes (//./pipe/*), Get-Service, Event Viewer
- Check: Is the required service actually running? Use appropriate commands.

## Common Error Patterns

### Docker Daemon Not Running
Symptoms: "Cannot connect", "connection refused", "no such file"
Specific indicators:
  - Linux: "/var/run/docker.sock" not found or no permission
  - Windows: "//./pipe/dockerDesktopLinuxEngine" not found
Root cause: Docker service/daemon is not started
Diagnosis: Check service status (systemctl status docker / Get-Service -Name Docker)
Fix: Start the service (sudo systemctl start docker / Start-Service -Name Docker)

### Port Already in Use
Symptoms: "address already in use", "EADDRINUSE", "bind failed"
Specific indicators: Mentions specific port number
Root cause: Another process is using that port
Diagnosis: Find the process (ss -tulpn | grep PORT / netstat -ano | findstr PORT)
Fix: Kill the process or use a different port

### Permission Denied
Symptoms: "permission denied", "EACCES", "access denied"
Specific indicators: Mentions specific file/directory path
Root cause: User lacks permissions
Diagnosis: Check ownership and permissions (ls -la / icacls)
Fix: Use sudo, change permissions (chmod), or add user to group

### Missing Dependency
Symptoms: "command not found", "module not found", "cannot find package"
Specific indicators: Mentions specific command/module/package name
Root cause: Required software is not installed
Diagnosis: Check if command exists (which / where)
Fix: Install the package (apt install / npm install / pip install)

## Decision Rules
1. ALWAYS read the FULL stderr, not just the first line
2. Specific errors OVERRIDE generic errors in your analysis
3. When multiple errors appear, work backwards from the most specific one
4. Platform-specific paths/services indicate what to check
5. Don't retry the exact same command if the error is clear - fix the root cause first
"""

# ============================================================================
# Helper Functions
# ============================================================================

def get_environment_isolation_rules(os_type: str = "linux") -> str:
    """Get environment isolation rules for the target OS.

    Args:
        os_type: "linux", "windows", or "macos"

    Returns:
        Combined environment isolation rules for Python + Node.js + Docker
    """
    if os_type.lower() == "windows":
        return f"""
# 🔒 Environment Isolation (CRITICAL - MANDATORY)

When deploying applications, you MUST create isolated environments to prevent dependency conflicts and system pollution.

{ENVIRONMENT_ISOLATION_PYTHON_WINDOWS}

{ENVIRONMENT_ISOLATION_NODEJS_WINDOWS}

{ENVIRONMENT_ISOLATION_DOCKER}
"""
    else:  # linux or macos
        return f"""
# 🔒 Environment Isolation (CRITICAL - MANDATORY)

When deploying applications, you MUST create isolated environments to prevent dependency conflicts and system pollution.

{ENVIRONMENT_ISOLATION_PYTHON}

{ENVIRONMENT_ISOLATION_NODEJS}

{ENVIRONMENT_ISOLATION_DOCKER}
"""


def get_deployment_strategies(os_type: str = "linux") -> str:
    """Get deployment strategies for the target OS.

    Args:
        os_type: "linux", "windows", or "macos"

    Returns:
        Combined deployment strategies
    """
    return f"""
# Deployment Strategies

{DEPLOYMENT_STRATEGY_DOCKER_COMPOSE}

{DEPLOYMENT_STRATEGY_DOCKER}

{DEPLOYMENT_STRATEGY_TRADITIONAL_PYTHON}

{DEPLOYMENT_STRATEGY_TRADITIONAL_NODEJS}

{DEPLOYMENT_STRATEGY_STATIC}
"""


# ============================================================================
# Re-export Chain of Thought framework for convenience
# ============================================================================

try:
    from .cot_framework import (
        CHAIN_OF_THOUGHT_FRAMEWORK,
        PLANNING_COT_TEMPLATE,
        EXECUTION_COT_TEMPLATE,
        ERROR_ANALYSIS_COT,
        USER_FEEDBACK_COT,
        REASONING_OUTPUT_FORMAT,
        get_cot_framework,
        get_reasoning_requirements,
    )
    __all__ = [
        "USER_INTERACTION_GUIDE",
        "ERROR_DIAGNOSIS_FRAMEWORK",
        "get_environment_isolation_rules",
        "get_deployment_strategies",
        # Chain of Thought exports
        "CHAIN_OF_THOUGHT_FRAMEWORK",
        "PLANNING_COT_TEMPLATE",
        "EXECUTION_COT_TEMPLATE",
        "ERROR_ANALYSIS_COT",
        "USER_FEEDBACK_COT",
        "REASONING_OUTPUT_FORMAT",
        "get_cot_framework",
        "get_reasoning_requirements",
    ]
except ImportError:
    # cot_framework.py not yet available (during initial setup)
    pass
