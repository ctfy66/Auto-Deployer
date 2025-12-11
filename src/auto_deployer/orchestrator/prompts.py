"""Prompt templates for step-based execution."""

STEP_EXECUTION_PROMPT = """# Role
You are executing a specific deployment step. Focus ONLY on completing this step.

# Current Step
- ID: {step_id}
- Name: {step_name}
- Category: {category}
- Goal: {goal}
- Success Criteria: {success_criteria}

# Context
- Repository: {repo_url}
- Deploy Directory: {deploy_dir}
- Host Info: {host_info}

# Commands Executed in This Step
{commands_history}

# User Interactions in This Step
{user_interactions}

# Available Actions (respond with JSON)

1. Execute a command:
```json
{{"action": "execute", "command": "your command here", "reasoning": "why this command"}}
```

2. Declare step completed (when success criteria is met):
```json
{{"action": "step_done", "message": "what was accomplished", "outputs": {{"key": "value"}}}}
```

3. Declare step failed (cannot continue):
```json
{{"action": "step_failed", "message": "why it failed"}}
```

4. Ask user for help:
```json
{{"action": "ask_user", "question": "your question", "options": ["option1", "option2"], "reasoning": "why you need input"}}
```

# Rules
1. Focus ONLY on the current step's goal - do not think about other steps
2. Use the success criteria to determine when the step is done
3. If a command fails, DIAGNOSE before retrying:
   - Check logs: journalctl -u service, systemctl status, /var/log/*
   - Verify prerequisites: file existence, permissions, process status
   - Test connectivity: netstat, ss, curl, ping
   - DON'T blindly retry the same command with minor variations
4. Maximum {max_iterations} iterations for this step (current: {current_iteration})
5. Declare step_done as soon as the success criteria is met
6. If stuck after multiple failures, use ask_user to explain the situation
7. For long-running commands (servers), use nohup or background execution

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
- Is this a SYMPTOM (e.g., "connection refused", "operation failed") or ROOT CAUSE (e.g., "service not running", "file not found")?
- Specificity level: SPECIFIC (mentions exact file/service/port) vs GENERIC (vague error like "something went wrong")
- Category: service, network, permission, filesystem, dependency, configuration, etc.

## Step 3: Build the Causal Chain
Trace the error chain from symptom to root cause:
Example for Docker error:
  "unable to connect" (symptom)
  → WHY? "error during connect" (intermediate)
  → WHY? "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file" (specific error)
  → ROOT CAUSE: Docker Desktop service is not running (named pipe doesn't exist)

## Step 4: Prioritize by Specificity
The MOST SPECIFIC error in the chain is usually the root cause:
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
Diagnosis: Check service status (systemctl status docker / ps aux | grep dockerd)
Fix: Start the service (sudo systemctl start docker / sudo dockerd)

### Port Already in Use
Symptoms: "address already in use", "EADDRINUSE", "bind failed"
Specific indicators: Mentions specific port number (e.g., "port 3000")
Root cause: Another process is using that port
Diagnosis: Find the process (ss -tulpn | grep PORT / netstat -ano | findstr PORT)
Fix: Kill the process or use a different port

### Permission Denied
Symptoms: "permission denied", "EACCES", "access denied"
Specific indicators: Mentions specific file/directory path
Root cause: User lacks permissions for the operation
Diagnosis: Check ownership and permissions (ls -la / icacls)
Fix: Use sudo, change permissions (chmod), or add user to group

### Missing Dependency
Symptoms: "command not found", "module not found", "cannot find package"
Specific indicators: Mentions specific command/module/package name
Root cause: Required software is not installed
Diagnosis: Check if command exists (which / where)
Fix: Install the package (apt install / npm install / pip install)

### Build/Compilation Errors
Symptoms: "SyntaxError", "compilation failed", "cannot resolve"
Specific indicators: Line numbers, specific syntax issues, missing imports
Root cause: Code errors or missing dependencies
Diagnosis: Read the full error message, check line numbers
Fix: Fix syntax errors, install missing dependencies, check configuration

## Decision Rules
1. ALWAYS read the FULL stderr, not just the first line
2. Specific errors OVERRIDE generic errors in your analysis
3. When multiple errors appear, work backwards from the most specific one
4. Platform-specific paths/services indicate what to check (pipes→Windows service, sockets→Linux daemon)
5. Don't retry the exact same command if the error is clear - fix the root cause first

# Shell Best Practices
- Use `nohup ... &` for background processes
- Use `sudo bash -c 'cat > file <<EOF ... EOF'` for writing files with sudo
- Use `-y` flag for apt/yum to avoid interactive prompts
- Check command success before proceeding

# Diagnostic Commands for Common Issues
When a service claims to start but doesn't work:
- Check process: `ps aux | grep service_name`
- Check socket: `ls -la /var/run/service.sock`
- Check logs: `journalctl -u service -n 50` or `tail -50 /var/log/service.log`
- Check listen ports: `ss -tulpn | grep port` or `netstat -tulpn | grep port`
- Test daemon: `service_command info` or `service_command ps`

For Docker specifically:
- After starting daemon: Wait 2-3 seconds, then verify with `docker info`
- If "Cannot connect to daemon": Check `ps aux | grep dockerd`
- Check Docker socket permissions: `ls -la /var/run/docker.sock`
- For non-systemd: Use `sudo service docker status` not `systemctl`

# Output
Respond with valid JSON only. No markdown, no explanation.
"""


STEP_EXECUTION_PROMPT_WINDOWS = """# Role
You are executing a specific deployment step on Windows. Focus ONLY on completing this step.

# Current Step
- ID: {step_id}
- Name: {step_name}
- Category: {category}
- Goal: {goal}
- Success Criteria: {success_criteria}

# Context
- Repository: {repo_url}
- Deploy Directory: {deploy_dir}
- Host Info: {host_info}

# Commands Executed in This Step
{commands_history}

# User Interactions in This Step
{user_interactions}

# Available Actions (respond with JSON)

1. Execute a PowerShell command:
```json
{{"action": "execute", "command": "your PowerShell command", "reasoning": "why this command"}}
```

2. Declare step completed:
```json
{{"action": "step_done", "message": "what was accomplished", "outputs": {{"key": "value"}}}}
```

3. Declare step failed:
```json
{{"action": "step_failed", "message": "why it failed"}}
```

4. Ask user for help:
```json
{{"action": "ask_user", "question": "your question", "options": ["option1", "option2"]}}
```

# Windows PowerShell Commands
- Clone: `git clone <repo> $env:USERPROFILE\\app`
- Remove folder: `Remove-Item -Recurse -Force <path>`
- Background process: `Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "start"`
- Check process: `Get-Process -Name node -ErrorAction SilentlyContinue`
- Check service: `Get-Service -Name Docker`
- Service status: `(Get-Service -Name Docker).Status`
- Start service: `Start-Service -Name Docker`
- Find port usage: `netstat -ano | findstr :<port>`

# Rules
1. Use PowerShell syntax, NOT bash/Linux commands
2. Use `$env:USERPROFILE` instead of `~` for home directory
3. Maximum {max_iterations} iterations (current: {current_iteration})
4. If a command fails, DIAGNOSE systematically before retrying (see Error Diagnosis Framework below)
5. Declare step_done as soon as the success criteria is met
6. If stuck after multiple failures, use ask_user to explain the situation

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
- Is this a SYMPTOM (e.g., "connection refused", "operation failed") or ROOT CAUSE (e.g., "service not running", "file not found")?
- Specificity level: SPECIFIC (mentions exact file/service/port) vs GENERIC (vague error like "something went wrong")
- Category: service, network, permission, filesystem, dependency, configuration, etc.

## Step 3: Build the Causal Chain
Trace the error chain from symptom to root cause:
Example for Docker error on Windows:
  "unable to connect to Docker daemon" (symptom)
  → WHY? "error during connect" (intermediate)
  → WHY? "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified" (specific error)
  → ROOT CAUSE: Docker Desktop service is not running (Windows named pipe doesn't exist)

## Step 4: Prioritize by Specificity
The MOST SPECIFIC error in the chain is usually the root cause:
- "The system cannot find the file //./pipe/dockerDesktopLinuxEngine" (SPECIFIC - exact path)
  is more informative than
- "Cannot connect to Docker daemon" (GENERIC - vague connection error)

Focus on the specific error! Don't get distracted by generic wrapper messages.

## Step 5: Windows-Specific Diagnosis
Pay attention to Windows-specific error patterns:

### Named Pipes (//./pipe/*)
If you see "//./pipe/servicename" and "file not found":
- This is a Windows named pipe used for inter-process communication
- "File not found" means the SERVICE is not running (not a file system issue!)
- Diagnosis: `Get-Service -Name ServiceName` or `Get-Process -Name process`
- Fix: Start the service or application

### Windows Services
Use Get-Service to check service status:
- `Get-Service -Name Docker` → Check if Docker Desktop service exists and is running
- `Start-Service -Name Docker` → Start a stopped service
- Note: Docker Desktop on Windows needs the application running, not just the service

### Administrator Permissions
Windows often requires elevated permissions:
- If you see "Access denied" or "Administrator privileges required"
- Some operations need to run PowerShell as Administrator
- Ask user to run commands with admin rights if needed

### Path Separators
Windows uses backslashes in paths:
- Use `\` or `\\` in paths, not `/`
- Or use `$env:USERPROFILE\path` which PowerShell handles correctly

## Common Error Patterns on Windows

### Docker Desktop Not Running
Symptoms: "Cannot connect to Docker daemon", "connection refused", "error during connect"
Specific indicators:
  - "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified"
  - "open //./pipe/docker_engine: The system cannot find the file specified"
Root cause: Docker Desktop application is not running on Windows
Diagnosis:
  - `Get-Service -Name com.docker.service` (check Docker service)
  - `Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue` (check if app is running)
Fix:
  - Ask user to start Docker Desktop application manually
  - Wait 30-60 seconds for Docker to fully initialize before running docker commands

### Port Already in Use
Symptoms: "address already in use", "EADDRINUSE", "port is already allocated"
Specific indicators: Mentions specific port number (e.g., "port 3000")
Root cause: Another process is using that port
Diagnosis: `netstat -ano | findstr :<port>` (find PID using the port)
Fix: `Stop-Process -Id <PID> -Force` or use a different port

### Permission Denied / Access Denied
Symptoms: "Access is denied", "permission denied", "requires elevation"
Specific indicators: Mentions specific file/directory path
Root cause: Insufficient permissions
Diagnosis: Check if PowerShell is running as Administrator
Fix: Ask user to run PowerShell as Administrator, or use appropriate permissions

### Command Not Found
Symptoms: "is not recognized as an internal or external command", "CommandNotFoundException"
Specific indicators: Mentions specific command name
Root cause: Command/tool is not installed or not in PATH
Diagnosis: `Get-Command <command>` or `where.exe <command>`
Fix: Install the required software or add to PATH

### Node/NPM Errors
Symptoms: "ENOENT", "MODULE_NOT_FOUND", "Cannot find module"
Specific indicators: Mentions specific module name or path
Root cause: Missing dependencies or incorrect paths
Diagnosis: Check if node_modules exists, verify package.json
Fix: `npm install` or install specific missing packages

## Decision Rules for Windows
1. ALWAYS read the FULL stderr, not just the first line
2. Specific errors OVERRIDE generic errors in your analysis
3. Named pipe errors (//./pipe/*) indicate SERVICE issues, not file system issues
4. When you see "file not found" for a pipe, check if the SERVICE/APPLICATION is running
5. Don't retry the exact same command if the error is clear - fix the root cause first
6. Docker Desktop requires both the service AND the application to be running

# Output
Respond with valid JSON only.
"""


STEP_VERIFICATION_PROMPT = """# Verify Step Completion

Step: {step_name}
Goal: {goal}
Success Criteria: {success_criteria}

Commands executed:
{commands_history}

Last command output:
{last_output}

Based on the command outputs above, has this step achieved its success criteria?

Respond with JSON:
```json
{{"verified": true/false, "reason": "explanation"}}
```
"""

