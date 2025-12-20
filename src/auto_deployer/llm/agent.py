"""LLM Agent for deployment planning.

This module contains the DeploymentPlanner class which creates structured
deployment plans that are executed by the Orchestrator.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

import requests

from ..config import LLMConfig

if TYPE_CHECKING:
    from ..analyzer import RepoContext

logger = logging.getLogger(__name__)


@dataclass
class DeploymentStep:
    """单个部署步骤"""
    id: int
    name: str                                    # 如 "Install Node.js"
    description: str                             # 详细描述
    category: str                                # "prerequisite" | "setup" | "build" | "deploy" | "verify"
    estimated_commands: List[str] = field(default_factory=list)  # 预计执行的命令（参考用）
    success_criteria: str = ""                   # 成功标准
    depends_on: List[int] = field(default_factory=list)  # 依赖的步骤ID


@dataclass
class DeploymentPlan:
    """完整的部署方案"""
    strategy: str                                # "docker-compose" | "docker" | "traditional" | "static"
    components: List[str] = field(default_factory=list)  # ["nodejs", "nginx", "pm2"]
    steps: List[DeploymentStep] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)       # 已识别的风险
    notes: List[str] = field(default_factory=list)       # 注意事项
    estimated_time: str = ""                     # 预计时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典用于日志记录"""
        return {
            "strategy": self.strategy,
            "components": self.components,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "estimated_commands": s.estimated_commands,
                    "success_criteria": s.success_criteria,
                    "depends_on": s.depends_on,
                }
                for s in self.steps
            ],
            "risks": self.risks,
            "notes": self.notes,
            "estimated_time": self.estimated_time,
            "created_at": self.created_at,
        }


class DeploymentPlanner:
    """
    LLM-powered deployment planner.
    
    Creates structured deployment plans that are executed by the Orchestrator.
    """

    def __init__(
        self,
        config: LLMConfig,
        planning_timeout: int = 60,
    ) -> None:
        if not config.api_key:
            raise ValueError("Planner requires an API key")
        self.config = config
        self.planning_timeout = planning_timeout
        
        # Initialize LLM provider
        from .base import create_llm_provider
        self.llm_provider = create_llm_provider(config)
        logger.info("Planner using LLM: %s (model: %s)", config.provider, config.model)

        # Keep session for backward compatibility with proxies
        self.session = requests.Session()
        self._setup_proxy()

    def _setup_proxy(self) -> None:
        """Configure proxy if specified."""
        proxy = self.config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def create_plan(
        self,
        repo_url: str,
        deploy_dir: str,
        host_info: dict,
        repo_analysis: Optional[str] = None,
        project_type: Optional[str] = None,
        framework: Optional[str] = None,
        is_local: bool = False,
    ) -> Optional[DeploymentPlan]:
        """
        Create a structured deployment plan.
        
        Args:
            repo_url: Repository URL
            deploy_dir: Target deployment directory
            host_info: Host information dictionary
            repo_analysis: Pre-analyzed repository context
            project_type: Detected project type
            framework: Detected framework
            is_local: Whether deploying locally or via SSH
            
        Returns:
            DeploymentPlan if successful, None otherwise
        """
        logger.info("🧠 Creating deployment plan with LLM...")
        
        
        # Build planning prompt
        from ..prompts.planning import build_planning_prompt

        # Extract host details for the prompt
        target_info = "Local machine" if is_local else f"{host_info.get('user', 'unknown')}@{host_info.get('host', 'unknown')}"

        prompt = build_planning_prompt(
            repo_url=repo_url,
            deploy_dir=deploy_dir,
            project_type=project_type or "unknown",
            framework=framework or "none",
            repo_analysis=repo_analysis or "No analysis available",
            target_info=target_info,
            host_details=f"# Host Details\n{json.dumps(host_info, indent=2, ensure_ascii=False)}"
        )
        
        # Call LLM
        try:
            response = self.llm_provider.generate_response(
                prompt=prompt,
                system_prompt=None,
                response_format="json",
                timeout=self.planning_timeout,
            )
            
            if not response:
                logger.error("Empty response from LLM")
                return None
            
            # Debug: Log the raw response
            logger.debug("Raw LLM response (first 500 chars): %s", response[:500])
            
            # Parse the plan
            plan = self._parse_plan(response)
            if plan:
                logger.info("✅ Plan created: %s strategy with %d steps", plan.strategy, len(plan.steps))
            else:
                logger.error("❌ Failed to parse plan from LLM response")
            
            return plan
            
        except Exception as exc:
            logger.error("Failed to create plan: %s", exc)
            return None

    def _parse_plan(self, llm_response: str) -> Optional[DeploymentPlan]:
        """Parse deployment plan from LLM JSON response."""
        try:
            # Extract JSON from response
            start_idx = llm_response.find("{")
            end_idx = llm_response.rfind("}") + 1
            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON found in LLM response")
                return None
            
            json_str = llm_response[start_idx:end_idx]
            data = json.loads(json_str)
            
            # Handle nested plan structure (some LLMs return {reasoning: {...}, plan: {...}})
            if "plan" in data and isinstance(data["plan"], dict):
                plan_data = data["plan"]
            else:
                plan_data = data
            
            # Validate required fields
            if "strategy" not in plan_data or "steps" not in plan_data:
                logger.error("Missing required fields (strategy, steps) in plan")
                logger.error("Received keys: %s", list(plan_data.keys()))
                logger.error("Response preview: %s", json_str[:500])
                return None
            
            # Parse steps
            steps = []
            for step_data in plan_data["steps"]:
                step = DeploymentStep(
                    id=step_data["id"],
                    name=step_data["name"],
                    description=step_data.get("description", ""),
                    category=step_data.get("category", "setup"),
                    estimated_commands=step_data.get("estimated_commands", []),
                    success_criteria=step_data.get("success_criteria", ""),
                    depends_on=step_data.get("depends_on", []),
                )
                steps.append(step)
            
            plan = DeploymentPlan(
                strategy=plan_data["strategy"],
                components=plan_data.get("components", []),
                steps=steps,
                risks=plan_data.get("risks", []),
                notes=plan_data.get("notes", []),
                estimated_time=plan_data.get("estimated_time", ""),
            )
            
            return plan
            
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s", e)
            return None
        except KeyError as e:
            logger.error("Missing field in plan: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error parsing plan: %s", e)
            return None

    @staticmethod
    def display_plan(plan: DeploymentPlan) -> None:
        """Display the deployment plan in a readable format."""
        print("\n" + "="*80)
        print("📋 DEPLOYMENT PLAN")
        print("="*80)
        print(f"Strategy: {plan.strategy}")
        print(f"Components: {', '.join(plan.components)}")
        print(f"Estimated Time: {plan.estimated_time}")
        print(f"Total Steps: {len(plan.steps)}")
        
        if plan.risks:
            print("\n⚠️  Identified Risks:")
            for risk in plan.risks:
                print(f"  - {risk}")
        
        if plan.notes:
            print("\n📝 Notes:")
            for note in plan.notes:
                print(f"  - {note}")
        
        print("\n📍 Deployment Steps:")
        print("-" * 80)
        
        for step in plan.steps:
            print(f"\n{step.id}. {step.name} [{step.category}]")
            print(f"   {step.description}")
            
            if step.depends_on:
                deps = ", ".join(str(d) for d in step.depends_on)
                print(f"   Depends on: Step(s) {deps}")
            
            if step.success_criteria:
                print(f"   Success: {step.success_criteria}")
            
            if step.estimated_commands:
                print(f"   Estimated commands: {len(step.estimated_commands)}")
        
        print("\n" + "="*80 + "\n")
