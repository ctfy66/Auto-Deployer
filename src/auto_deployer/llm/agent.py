"""LLM Agent that autonomously controls deployment."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

import requests

from ..config import LLMConfig

if TYPE_CHECKING:
    from ..ssh import RemoteHostFacts
    from ..workflow import DeploymentRequest
    from ..ssh import SSHSession
    from ..analyzer import RepoContext

logger = logging.getLogger(__name__)


@dataclass
class AgentAction:
    """An action decided by the LLM agent."""
    action_type: str  # "execute", "done", "failed"
    command: Optional[str] = None
    reasoning: Optional[str] = None
    message: Optional[str] = None


@dataclass 
class CommandResult:
    """Result of executing a command."""
    command: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int


class DeploymentAgent:
    """
    LLM-powered agent that autonomously deploys applications.
    
    The agent operates in a loop:
    1. Observe: See the current state (repo info, command history)
    2. Think: LLM decides what to do next
    3. Act: Execute the command
    4. Repeat until done or max iterations reached
    """

    def __init__(self, config: LLMConfig, max_iterations: int = 20, log_dir: Optional[str] = None) -> None:
        if not config.api_key:
            raise ValueError("Agent requires an API key")
        self.config = config
        self.max_iterations = max_iterations
        self.session = requests.Session()
        
        # 日志目录
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "agent_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前部署的日志文件
        self.current_log_file: Optional[Path] = None
        self.deployment_log: dict = {}
        
        # 设置代理 - 优先使用配置文件，其次使用环境变量
        import os
        proxy = config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            logger.info("Agent using proxy: %s", proxy)
        
        self.base_endpoint = config.endpoint or (
            f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent"
        )
        
        # 执行历史
        self.history: List[dict] = []

    def deploy(
        self,
        request: "DeploymentRequest",
        host_facts: Optional["RemoteHostFacts"],
        ssh_session: "SSHSession",
        repo_context: Optional["RepoContext"] = None,
    ) -> bool:
        """
        Run the autonomous deployment loop.
        
        Args:
            request: Deployment request with repo URL and SSH details
            host_facts: Information about the remote host
            ssh_session: Active SSH session
            repo_context: Pre-analyzed repository context (optional but recommended)
            
        Returns True if deployment succeeded, False otherwise.
        """
        logger.info("Agent starting deployment...")
        
        # 初始化日志记录
        self._init_deployment_log(request)
        
        # 初始化上下文 - 包含预分析的仓库信息
        self.history = []
        context = self._build_initial_context(request, host_facts, repo_context)
        
        # 记录初始上下文
        self.deployment_log["context"] = {
            "repo_url": context.get("repo_url"),
            "ssh_target": context.get("ssh_target"),
            "has_repo_analysis": repo_context is not None,
            "project_type": repo_context.project_type if repo_context else None,
            "framework": repo_context.detected_framework if repo_context else None,
        }
        
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"📍 Iteration {iteration}/{self.max_iterations}")
            
            # 让 LLM 决定下一步
            action = self._think(context)
            
            # 记录 LLM 的决策
            step_log = {
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
                "action": action.action_type,
                "command": action.command,
                "reasoning": action.reasoning,
                "message": action.message,
            }
            
            if action.action_type == "done":
                step_log["result"] = "SUCCESS"
                self.deployment_log["steps"].append(step_log)
                self.deployment_log["status"] = "success"
                self.deployment_log["end_time"] = datetime.now().isoformat()
                self._save_deployment_log()
                logger.info(f"✅ Agent completed: {action.message}")
                logger.info(f"📄 Log saved to: {self.current_log_file}")
                return True
            
            if action.action_type == "failed":
                step_log["result"] = "FAILED"
                self.deployment_log["steps"].append(step_log)
                self.deployment_log["status"] = "failed"
                self.deployment_log["end_time"] = datetime.now().isoformat()
                self._save_deployment_log()
                logger.error(f"❌ Agent gave up: {action.message}")
                logger.info(f"📄 Log saved to: {self.current_log_file}")
                return False
            
            if action.action_type == "execute" and action.command:
                logger.info(f"🔧 Executing: {action.command}")
                if action.reasoning:
                    logger.info(f"   Reason: {action.reasoning}")
                
                # 执行命令
                result = self._execute_command(ssh_session, action.command)
                
                # 记录命令结果
                step_log["result"] = {
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout[:2000] if result.stdout else "",
                    "stderr": result.stderr[:2000] if result.stderr else "",
                }
                self.deployment_log["steps"].append(step_log)
                
                # 记录到历史
                self.history.append({
                    "iteration": iteration,
                    "reasoning": action.reasoning,
                    "command": action.command,
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout[:1000] if result.stdout else "",
                    "stderr": result.stderr[:1000] if result.stderr else "",
                })
                
                # 显示结果
                status = "✓" if result.success else "✗"
                logger.info(f"   {status} Exit code: {result.exit_code}")
                if result.stdout:
                    logger.debug(f"   stdout: {result.stdout[:200]}")
                if result.stderr and not result.success:
                    logger.warning(f"   stderr: {result.stderr[:200]}")
                
                # 每步都保存日志（防止中断丢失）
                self._save_deployment_log()
            else:
                logger.warning(f"Unknown action: {action.action_type}")
        
        self.deployment_log["status"] = "max_iterations"
        self.deployment_log["end_time"] = datetime.now().isoformat()
        self._save_deployment_log()
        logger.error("❌ Agent reached max iterations without completing")
        logger.info(f"📄 Log saved to: {self.current_log_file}")
        return False

    def _init_deployment_log(self, request: "DeploymentRequest") -> None:
        """Initialize a new deployment log file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 从 repo_url 提取项目名
        repo_name = request.repo_url.split("/")[-1].replace(".git", "")
        filename = f"deploy_{repo_name}_{timestamp}.json"
        self.current_log_file = self.log_dir / filename
        
        self.deployment_log = {
            "repo_url": request.repo_url,
            "target": f"{request.username}@{request.host}:{request.port}",
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "context": {},
            "steps": [],
        }
        logger.info(f"📝 Logging to: {self.current_log_file}")

    def _save_deployment_log(self) -> None:
        """Save the deployment log to file."""
        if self.current_log_file:
            with open(self.current_log_file, "w", encoding="utf-8") as f:
                json.dump(self.deployment_log, f, indent=2, ensure_ascii=False)

    def _think(self, context: dict) -> AgentAction:
        """Ask LLM to decide the next action."""
        import time
        
        prompt = self._build_prompt(context)
        
        url = f"{self.base_endpoint}?key={self.config.api_key}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "responseMimeType": "application/json",
            },
        }
        
        # 重试机制处理速率限制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, json=body, timeout=60)
                
                # 处理速率限制
                if response.status_code == 429:
                    wait_time = 30 * (attempt + 1)  # 30s, 60s, 90s
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                # 提取响应文本
                candidates = data.get("candidates") or []
                for candidate in candidates:
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text")
                        if text:
                            return self._parse_action(text)
                
                logger.error("No response from LLM")
                return AgentAction(action_type="failed", message="No LLM response")
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"LLM API call failed: {e}")
                return AgentAction(action_type="failed", message=str(e))
            except Exception as exc:
                logger.error(f"LLM API call failed: {exc}")
                return AgentAction(action_type="failed", message=str(exc))
        
        return AgentAction(action_type="failed", message="Rate limited after max retries")

    def _parse_action(self, text: str) -> AgentAction:
        """Parse LLM response into an action."""
        try:
            data = json.loads(text)
            return AgentAction(
                action_type=data.get("action", "failed"),
                command=data.get("command"),
                reasoning=data.get("reasoning"),
                message=data.get("message"),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return AgentAction(action_type="failed", message=f"Parse error: {text[:100]}")

    def _execute_command(self, session: "SSHSession", command: str) -> CommandResult:
        """Execute a command on the remote server."""
        try:
            result = session.run(command, timeout=120)
            return CommandResult(
                command=command,
                success=result.ok,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_status,
            )
        except Exception as exc:
            return CommandResult(
                command=command,
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=-1,
            )

    def _build_initial_context(
        self,
        request: "DeploymentRequest",
        host_facts: Optional["RemoteHostFacts"],
        repo_context: Optional["RepoContext"] = None,
    ) -> dict:
        """Build the initial context for the agent."""
        ctx = {
            "repo_url": request.repo_url,
            "ssh_target": f"{request.username}@{request.host}:{request.port}",
            "remote_host": host_facts.to_payload() if host_facts else None,
        }
        
        # 添加预分析的仓库信息
        if repo_context:
            ctx["repo_analysis"] = repo_context.to_prompt_context()
            ctx["project_type"] = repo_context.project_type
            ctx["framework"] = repo_context.detected_framework
            ctx["scripts"] = repo_context.detected_scripts
        
        return ctx

    def _build_prompt(self, context: dict) -> str:
        """Build the prompt for the LLM agent."""
        
        # 检查是否有预分析的仓库信息
        has_repo_analysis = "repo_analysis" in context
        
        # 构建系统提示词 - 根据是否有预分析调整
        if has_repo_analysis:
            system_prompt = """# Role
You are an autonomous DevOps deployment agent. You execute shell commands on a remote Linux server via SSH to deploy applications.

# Goal  
Deploy the given repository and ensure the application is running and accessible. Success = application responds to HTTP requests with actual content.

# Environment
- You have SSH access to a remote Linux server
- Commands you output will be executed directly on the remote server
- You will see the stdout, stderr, and exit code of each command
- sudo is available (password handled automatically)
- Common tools: git, npm, node, python3, pip, curl, systemctl, pm2

# ⭐ IMPORTANT: Repository Analysis Provided
You have been given a **pre-analyzed repository context** below. Use this information to make informed decisions:
- Project type and framework are already identified
- Key configuration files (package.json, requirements.txt, Dockerfile, etc.) are provided
- Available scripts and dependencies are listed
- Directory structure is shown

**Do NOT waste iterations re-analyzing the repository!** Use the provided information directly.

# Available Actions
You must respond with JSON in this exact format:
```json
{
  "action": "execute" | "done" | "failed",
  "command": "shell command to run (required if action=execute)",
  "reasoning": "brief explanation of your decision",
  "message": "final status message (required if action=done or failed)"
}
```

# Decision Rules
1. **execute**: Run a shell command and observe the result
2. **done**: Deployment successful - app is verified running AND curl returned actual content
3. **failed**: Deployment impossible after reasonable attempts

# ⚠️ CRITICAL RULES (MUST FOLLOW)
1. **NEVER run server commands directly!** Commands like `npm run dev`, `npm start`, `python app.py` will BLOCK FOREVER.
2. **ALWAYS use nohup for servers**: `nohup <cmd> > app.log 2>&1 &`
3. **Verification MUST show actual content!** Empty curl response = FAILURE, not success!
4. **Check app.log if curl fails** to see error messages.
5. **Use the pre-analyzed info!** Don't cat files that are already provided.

# Deployment Flow (with pre-analysis)
1. Clone: `rm -rf ~/app && git clone <repo> ~/app`
2. Install dependencies (based on pre-analyzed project type)
3. Start server IN BACKGROUND (use correct command from package.json scripts or framework knowledge)
4. Wait: `sleep 5`
5. Verify: `curl -s http://localhost:<port>`
6. If empty, check logs: `cat ~/app/app.log`

# Common Ports
- VitePress/Vite: 5173
- React (CRA): 3000
- Next.js: 3000
- Flask: 5000
- Django: 8000
- Express: 3000

# Error Handling
- "command not found" → install the tool or check PATH
- "port already in use" → kill existing process: `lsof -ti:<port> | xargs kill -9`
- "permission denied" → use sudo
- "module not found" → install dependencies
- Empty curl response → Server failed to start! Check app.log"""
        else:
            # 没有预分析时的 prompt（需要自己探索）
            system_prompt = """# Role
You are an autonomous DevOps deployment agent. You execute shell commands on a remote Linux server via SSH to deploy applications.

# Goal  
Deploy the given repository and ensure the application is running and accessible. Success = application responds to HTTP requests with actual content.

# Environment
- You have SSH access to a remote Linux server
- Commands you output will be executed directly on the remote server
- You will see the stdout, stderr, and exit code of each command
- sudo is available (password handled automatically)
- Common tools: git, npm, node, python3, pip, curl, systemctl, pm2

# Available Actions
You must respond with JSON in this exact format:
```json
{
  "action": "execute" | "done" | "failed",
  "command": "shell command to run (required if action=execute)",
  "reasoning": "brief explanation of your decision",
  "message": "final status message (required if action=done or failed)"
}
```

# ⚠️ CRITICAL RULES (MUST FOLLOW)
1. **ALWAYS analyze the repository FIRST** after cloning! Check package.json OR requirements.txt to determine project type.
2. **NEVER assume project type!** A repo might have package.json but be a Python project.
3. **NEVER run server commands directly!** Commands like `npm run dev`, `npm start`, `python app.py` will BLOCK FOREVER.
4. **ALWAYS use nohup for servers**: `nohup <cmd> > app.log 2>&1 &`
5. **Verification MUST show actual content!** Empty curl response = FAILURE, not success!
6. **Check app.log if curl fails** to see error messages.

# Deployment Flow
1. Clone: `rm -rf ~/app && git clone <repo> ~/app`
2. **ANALYZE FIRST**: `cat ~/app/package.json 2>/dev/null || cat ~/app/requirements.txt 2>/dev/null || ls ~/app`
3. Install dependencies based on project type
4. Start server IN BACKGROUND
5. Wait: `sleep 5`
6. Verify: `curl -s http://localhost:<port>`

# Common Ports
- VitePress/Vite: 5173
- React (CRA): 3000
- Next.js: 3000
- Flask: 5000
- Django: 8000"""

        # 构建当前状态
        state = {
            "repo_url": context.get("repo_url"),
            "server": {
                "target": context.get("ssh_target"),
                "os": context.get("remote_host", {}).get("os_release") if context.get("remote_host") else "Linux",
            },
            "command_history": self.history[-10:],  # 最近10条命令历史
        }
        
        # 组合最终 prompt
        parts = [system_prompt, "\n---\n"]
        
        # 添加预分析的仓库上下文
        if has_repo_analysis:
            parts.append("# Pre-Analyzed Repository Context")
            parts.append(context["repo_analysis"])
            parts.append("\n---\n")
        
        parts.append("# Current Deployment State")
        parts.append(f"```json\n{json.dumps(state, indent=2, ensure_ascii=False)}\n```")
        parts.append("\nBased on the above information, decide your next action. Respond with JSON only.")
        
        return "\n".join(parts)
