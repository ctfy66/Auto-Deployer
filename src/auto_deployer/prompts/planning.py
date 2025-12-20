"""Planning phase prompt templates.

This module contains prompts used during the deployment planning phase,
where the LLM analyzes the repository and generates a structured deployment plan.
"""

from typing import Optional
from .cot_framework import PLANNING_PHASE_GUIDE, get_reasoning_requirements


def build_planning_prompt(
    repo_url: str,
    deploy_dir: str,
    project_type: str,
    framework: str,
    repo_analysis: str,
    target_info: str,
    host_details: str,
) -> str:
    """Build the deployment planning prompt.

    Args:
        repo_url: Repository URL
        deploy_dir: Deployment directory path
        project_type: Detected project type (e.g., "nodejs", "python")
        framework: Detected framework (e.g., "express", "django")
        repo_analysis: Pre-analyzed repository context (formatted)
        target_info: Target environment summary (e.g., "Local machine (Windows)" or "user@host:port")
        host_details: Detailed host information (OS, tools, architecture, etc.)

    Returns:
        Formatted planning prompt ready to send to LLM
    """
    return f"""# Role
You are a DevOps deployment planner with systematic reasoning capabilities.
Analyze the repository deeply and create a structured deployment plan using Chain of Thought reasoning.

# Input
- Repository: {repo_url}
- Deploy Directory: {deploy_dir}
- Project Type: {project_type}
- Framework: {framework}

{host_details}

# Repository Analysis
{repo_analysis}

{PLANNING_PHASE_GUIDE}

# Task
Create a deployment plan using the systematic reasoning process above. Think deeply about:
1. What deployment strategy is best? (Docker if Dockerfile exists, traditional otherwise)
2. What components need to be installed? (Node.js, Python, Nginx, etc.)
3. What are the exact steps to deploy this project?
4. What could go wrong? (missing env files, build errors, etc.)

Output a JSON object with this exact structure:
```json
{{{{
  "strategy": "docker-compose|docker|traditional|static",
  "components": ["list", "of", "required", "components"],
  "steps": [
    {{{{
      "id": 1,
      "name": "Short step name",
      "description": "What this step does and why",
      "category": "prerequisite|setup|build|deploy|verify",
      "estimated_commands": ["command1", "command2"],
      "success_criteria": "How to verify this step succeeded",
      "depends_on": []
    }}}}
  ],
  "risks": ["Potential risk 1", "Potential risk 2"],
  "notes": ["Important note 1"],
  "estimated_time": "5-10 minutes"
}}}}
```

# Rules
1. Choose the SIMPLEST strategy that works:
   - If docker-compose.yml exists → use "docker-compose"
   - If only Dockerfile exists → use "docker"
   - If neither exists → use "traditional" or "static"

2. **Docker-in-Docker Detection (CRITICAL for testing environments)**:
   - If target environment is a container (check for: no systemd at PID 1, /proc/1/cgroup contains 'docker')
   - AND project requires Docker (Dockerfile present)
   - THEN: Skip Docker installation OR use "traditional" strategy instead
   - Add this to risks: "Running in containerized environment - Docker-in-Docker may not work"

3. Include ALL necessary steps (install dependencies, configure, build, deploy, verify)
4. Each step should be atomic and independently verifiable
5. Always include a final "verify" step to confirm deployment works
6. Identify risks from repository analysis (e.g., missing .env, syntax errors in configs)
7. Order steps by dependencies
8. Make success_criteria specific and verifiable:
   - For installation steps: Command availability (e.g., "docker --version succeeds")
   - For service steps: Service status (e.g., "systemctl status shows active OR docker ps works")
   - Provide fallback criteria for non-systemd environments

# 🔒 CRITICAL: Environment Isolation (MANDATORY)
9. For "traditional" strategy, you MUST include environment isolation steps:
   - **Python projects**: MUST create and activate virtual environment BEFORE pip install
     Example step: "Create Python virtual environment (venv)"
   - **Node.js projects**: MUST use local dependencies (npm install, NOT npm install -g)
     Example step: "Install Node.js dependencies locally"
   - **Docker projects**: Already isolated, no additional steps needed
10. The environment isolation step should be in "setup" category and come BEFORE dependency installation
11. Example steps for Python project:
   - Step X (setup): "Create virtual environment" → python -m venv venv
   - Step X+1 (setup): "Activate virtual environment and install dependencies" → source venv/bin/activate && pip install -r requirements.txt
12. Example steps for Node.js project:
   - Step X (setup): "Install local dependencies" → npm install (NEVER use -g)

# Category Definitions
- prerequisite: Install required software (Node.js, Docker, etc.)
- setup: Clone repo, configure environment, copy files
- build: Compile, bundle, or build the application
- deploy: Start services, configure web server
- verify: Test that deployment is working

# Output Format

FIRST, show your reasoning process (简洁版，不要太长):
```
## 项目分析
[类型、技术栈、关键依赖]

## 策略选择
Docker-Compose: [适合/不适合 + 简短理由]
Docker: [适合/不适合 + 简短理由]
Traditional: [适合/不适合 + 简短理由]
选择: [X] 因为 [核心原因]

## 主要风险
[3-5个关键风险点]
```

THEN, output the JSON plan (no markdown code fence):
```json
{{{{
  "strategy": "...",
  "components": [...],
  "steps": [...],
  "risks": [...],
  "notes": [...],
  "estimated_time": "..."
}}}}
```

Output your reasoning first, THEN the JSON plan."""


def build_host_details_local(
    os_name: str,
    os_release: str,
    architecture: str,
    kernel: str,
    is_container: bool,
    has_systemd: bool,
    available_tools: dict,
) -> str:
    """Build host details section for local deployment.

    Args:
        os_name: Operating system name (e.g., "Windows", "Linux")
        os_release: OS version
        architecture: System architecture (e.g., "x86_64", "ARM64")
        kernel: Kernel version
        is_container: Whether running in a container
        has_systemd: Whether systemd is available
        available_tools: Dict of tool availability (e.g., {"docker": True, "git": True})

    Returns:
        Formatted host details string
    """
    target_info = f"Local machine ({os_name} - {os_release})"

    # Build installed tools list
    installed_tools = [k for k, v in available_tools.items() if v]
    tools_info = f"\nInstalled tools: {', '.join(installed_tools) if installed_tools else 'none detected'}"

    return f"""
# Target Environment
- Platform: {target_info}
- Architecture: {architecture}
- Kernel: {kernel}
{tools_info}

**Environment Detection**:
- Running in Container: {'Yes (Docker-in-Docker limitations apply!)' if is_container else 'No'}
- Init System: {'systemd' if has_systemd else 'non-systemd (use service/init.d commands)'}
- Has Docker: {'Yes' if available_tools.get('docker') else 'No'}
- Has Git: {'Yes' if available_tools.get('git') else 'No'}
- Has Node.js: {'Yes' if available_tools.get('node') else 'No'}
- Has Python: {'Yes' if available_tools.get('python3') else 'No'}

**IMPORTANT**: If running in container AND project requires Docker, consider using 'traditional' strategy instead!
"""


def build_host_details_remote(
    ssh_target: str,
    os_release: str,
    kernel: str,
    architecture: str,
    is_container: bool,
    has_systemd: bool,
) -> str:
    """Build host details section for remote SSH deployment.

    Args:
        ssh_target: SSH target string (e.g., "user@host:port")
        os_release: OS version
        kernel: Kernel version
        architecture: System architecture
        is_container: Whether running in a container
        has_systemd: Whether systemd is available

    Returns:
        Formatted host details string
    """
    return f"""
# Target Environment
- Platform: {ssh_target}
- OS: {os_release}
- Kernel: {kernel}
- Architecture: {architecture}

**Environment Detection**:
- Running in Container: {'Yes (Docker-in-Docker limitations apply!)' if is_container else 'No'}
- Init System: {'systemd' if has_systemd else 'non-systemd (use service/init.d commands)'}

**IMPORTANT**: If running in container AND project requires Docker, consider using 'traditional' strategy instead!
"""
