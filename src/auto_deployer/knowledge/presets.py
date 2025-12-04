"""Preset experiences for common deployment issues."""

from __future__ import annotations

import logging
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .store import ExperienceStore

logger = logging.getLogger(__name__)


# 预置经验列表
PRESET_EXPERIENCES: List[Dict[str, Any]] = [
    {
        "id": "preset_docker_mirror_config",
        "content": """Docker Hub timeout fix: Configure registry mirrors

When Docker build/pull fails with 'dial tcp ... i/o timeout' or 'failed to resolve source metadata for docker.io/...', 
it usually means Docker Hub is unreachable (common in China or restricted networks).

Error patterns:
- dial tcp X.X.X.X:443: i/o timeout
- failed to resolve source metadata for docker.io/library/XXX
- TLS handshake timeout
- context deadline exceeded

Solution:
1. Check existing config: cat /etc/docker/daemon.json 2>/dev/null || echo "No config"
2. Configure Chinese mirrors:
   sudo mkdir -p /etc/docker
   sudo bash -c 'cat > /etc/docker/daemon.json <<EOF
   {
     "registry-mirrors": [
       "https://docker.1ms.run",
       "https://docker.xuanyuan.me"
     ]
   }
   EOF'
3. Restart Docker: sudo systemctl daemon-reload && sudo systemctl restart docker
4. Retry the build/pull command

This is a universal fix that works for any Docker-based deployment when Docker Hub is slow or unreachable.""",
        "metadata": {
            "scope": "universal",
            "title": "Docker Hub Timeout - Configure Registry Mirrors",
            "problem_summary": "Docker build/pull fails with i/o timeout when accessing docker.io registry",
            "solution_summary": "Configure Chinese Docker registry mirrors in /etc/docker/daemon.json, then restart Docker and retry",
            "lesson": "Always check and configure Docker mirrors when deployment target may have restricted network access to Docker Hub",
            "tags": "docker,timeout,mirror,registry,network,china",
            "confidence": "0.95",
            "keywords": "docker timeout mirror registry i/o timeout dial tcp failed to resolve TLS handshake"
        }
    },
    {
        "id": "preset_npm_registry_config",
        "content": """npm registry timeout fix: Configure Chinese mirror

When npm install fails with ETIMEDOUT, ECONNREFUSED, or takes forever, configure Chinese npm registry.

Error patterns:
- npm ERR! code ETIMEDOUT
- npm ERR! code ECONNREFUSED
- npm ERR! network request failed
- Stuck at "idealTree" for long time

Solution:
1. Set npm registry: npm config set registry https://registry.npmmirror.com
2. Or use with single command: npm install --registry=https://registry.npmmirror.com
3. For yarn: yarn config set registry https://registry.npmmirror.com

This helps when npm official registry is slow or blocked.""",
        "metadata": {
            "scope": "universal",
            "title": "npm Registry Timeout - Configure Chinese Mirror",
            "problem_summary": "npm install fails with timeout or connection refused",
            "solution_summary": "Configure npmmirror.com as npm registry",
            "lesson": "Configure npm mirror for faster package installation in China",
            "tags": "npm,nodejs,timeout,mirror,registry,network",
            "confidence": "0.90",
            "keywords": "npm ETIMEDOUT ECONNREFUSED registry timeout idealTree"
        }
    },
    {
        "id": "preset_pip_mirror_config",
        "content": """pip/PyPI timeout fix: Configure Chinese mirror

When pip install fails with timeout or connection errors, configure Chinese PyPI mirror.

Error patterns:
- pip._vendor.urllib3.exceptions.ReadTimeoutError
- Connection timed out
- Could not fetch URL

Solution:
1. Use mirror for single command: pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <package>
2. Or configure permanently:
   pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
3. Alternative mirrors:
   - https://pypi.tuna.tsinghua.edu.cn/simple (Tsinghua)
   - https://mirrors.aliyun.com/pypi/simple (Aliyun)

This helps when PyPI is slow or blocked.""",
        "metadata": {
            "scope": "universal",
            "title": "pip/PyPI Timeout - Configure Chinese Mirror",
            "problem_summary": "pip install fails with timeout when accessing pypi.org",
            "solution_summary": "Configure Chinese PyPI mirror (Tsinghua or Aliyun)",
            "lesson": "Configure pip mirror for faster package installation in China",
            "tags": "pip,python,timeout,mirror,pypi,network",
            "confidence": "0.90",
            "keywords": "pip timeout ReadTimeoutError pypi connection timed out"
        }
    },
]


def init_preset_experiences(store: "ExperienceStore") -> int:
    """
    初始化预置经验到知识库。
    
    只添加不存在的经验，已存在的会跳过。
    
    Args:
        store: ExperienceStore 实例
        
    Returns:
        新添加的经验数量
    """
    added = 0
    for exp in PRESET_EXPERIENCES:
        exp_id = exp["id"]
        if not store.refined_exists(exp_id):
            success = store.add_refined_experience(
                id=exp_id,
                content=exp["content"],
                metadata=exp["metadata"]
            )
            if success:
                logger.info(f"Added preset experience: {exp_id}")
                added += 1
            else:
                logger.warning(f"Failed to add preset experience: {exp_id}")
        else:
            logger.debug(f"Preset experience already exists: {exp_id}")
    
    return added


def get_preset_count() -> int:
    """获取预置经验数量"""
    return len(PRESET_EXPERIENCES)

