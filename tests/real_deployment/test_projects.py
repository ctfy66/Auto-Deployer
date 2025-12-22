"""测试项目配置 - 定义用于真实部署测试的项目列表"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class VerificationConfig:
    """部署验证配置"""
    urls: List[str]  # 需要验证的URL列表
    expected_status: int = 200  # 期望的HTTP状态码
    expected_content: Optional[str] = None  # 期望的响应内容（可选）
    timeout: int = 10  # 验证超时时间（秒）


@dataclass
class TestProject:
    """测试项目配置"""
    name: str  # 项目名称（唯一标识）
    repo_url: str  # Git仓库URL
    description: str  # 项目描述
    expected_strategy: str  # 期望的部署策略: "docker", "docker-compose", "traditional", "static"
    difficulty: str  # 难度: "easy", "medium", "hard"
    expected_time_minutes: int  # 预期部署时间（分钟）
    verification: VerificationConfig  # 验证配置
    skip: bool = False  # 是否跳过此测试
    tags: List[str] = field(default_factory=list)  # 标签（用于筛选）


# 测试项目列表
# 使用真实的公开GitHub仓库进行测试
TEST_PROJECTS: List[TestProject] = [
    # ========== Easy 难度项目 ==========
    TestProject(
        name="HuiBlog",
        repo_url="git@github.com:ctfy66/HuiBlog.git",
        description="next.js个人博客",
        expected_strategy="traditional",
        difficulty="easy",
        expected_time_minutes=5,
        verification=VerificationConfig(
            urls=["http://localhost:3000"],
            expected_status=200,
            timeout=10
        ),
        tags=["next.js", "static", "simple"],
        skip=True
    ),
    TestProject(
        name="docker-welcome",
        repo_url="https://github.com/docker/welcome-to-docker.git",
        description="Docker官方欢迎页面项目，包含Dockerfile，适合测试Docker部署策略",
        expected_strategy="docker",
        difficulty="easy",
        expected_time_minutes=5,
        verification=VerificationConfig(
            urls=["http://localhost:8080"],
            expected_status=200,
            timeout=10
        ),
        tags=["docker", "static", "simple"],
        skip=True
    ),
    TestProject(
        name="nodejs-express-hello",
        repo_url="https://github.com/expressjs/express.git",
        description="Express.js官方仓库，包含示例代码，测试传统Node.js部署",
        expected_strategy="traditional",
        difficulty="easy",
        expected_time_minutes=5,
        verification=VerificationConfig(
            urls=["http://localhost:3000"],
            expected_status=200,
            timeout=10
        ),
        tags=["nodejs", "express", "simple"],
        skip=False  
    ),
    TestProject(
        name="python-flask-hello",
        repo_url="https://github.com/pallets/flask.git",
        description="Flask官方仓库，包含示例代码，测试传统Python部署",
        expected_strategy="traditional",
        difficulty="easy",
        expected_time_minutes=5,
        verification=VerificationConfig(
            urls=["http://localhost:5000"],
            expected_status=200,
            timeout=10
        ),
        tags=["python", "flask", "simple"],
        skip= False
    ),
    TestProject(
        name="nodejs-simple-server",
        repo_url="https://github.com/vercel/next.js.git",
        description="Next.js官方仓库，测试静态站点或Node.js部署",
        expected_strategy="traditional",
        difficulty="easy",
        expected_time_minutes=6,
        verification=VerificationConfig(
            urls=["http://localhost:3000"],
            expected_status=200,
            timeout=10
        ),
        tags=["nodejs", "nextjs", "simple"],
        skip=False  
    ),
    
    # ========== Medium 难度项目 ==========
    
    TestProject(
        name="static-hugo-site",
        repo_url="https://github.com/gohugoio/hugo.git",
        description="Hugo静态站点生成器，测试静态站点构建和部署",
        expected_strategy="static",
        difficulty="medium",
        expected_time_minutes=8,
        verification=VerificationConfig(
            urls=["http://localhost:1313"],
            expected_status=200,
            timeout=10
        ),
        tags=["static", "hugo", "golang"],
        skip=False  
    ),
    TestProject(
        name="nodejs-fullstack",
        repo_url="https://github.com/vercel/next.js.git",
        description="Next.js全栈应用示例，测试Node.js全栈部署",
        expected_strategy="traditional",
        difficulty="medium",
        expected_time_minutes=10,
        verification=VerificationConfig(
            urls=["http://localhost:3000"],
            expected_status=200,
            timeout=10
        ),
        tags=["nodejs", "nextjs", "fullstack"],
        skip=False  
    ),
    TestProject(
        name="BuildingAI",
        repo_url="https://github.com/BidingCC/BuildingAI",
        description="docker多组件项目",
        expected_strategy="traditional",
        difficulty="medium",
        expected_time_minutes=20,
        verification=VerificationConfig(
            urls=["http://localhost:4090"],
            expected_status=200,
            timeout=10
        ),
        tags=["nodejs", "nextjs", "fullstack"],
        skip=False  
    ),

    
    # ========== Hard 难度项目 ==========
    TestProject(
        name="python-django-example",
        repo_url="https://github.com/django/django.git",
        description="Django官方仓库，测试复杂Python Web应用部署",
        expected_strategy="traditional",
        difficulty="hard",
        expected_time_minutes=15,
        verification=VerificationConfig(
            urls=["http://localhost:8000"],
            expected_status=200,
            timeout=10
        ),
        tags=["python", "django", "complex"],
        skip=False  
    ),
    TestProject(
        name="microservices-docker-compose",
        repo_url="https://github.com/dockersamples/example-voting-app.git",
        description="微服务架构示例，使用docker-compose编排多个服务，测试复杂部署场景",
        expected_strategy="docker-compose",
        difficulty="hard",
        expected_time_minutes=15,
        verification=VerificationConfig(
            urls=[
                "http://localhost:5000",
                "http://localhost:5001",
                "http://localhost:8080"  # 工作节点
            ],
            expected_status=200,
            timeout=20
        ),
        tags=["docker-compose", "microservices", "complex"],
        skip = True
    ),
]
    
    
    


def get_projects_by_difficulty(difficulty: str) -> List[TestProject]:
    """按难度筛选项目"""
    return [p for p in TEST_PROJECTS if p.difficulty == difficulty and not p.skip]


def get_projects_by_tag(tag: str) -> List[TestProject]:
    """按标签筛选项目"""
    return [p for p in TEST_PROJECTS if tag in p.tags and not p.skip]


def get_all_projects() -> List[TestProject]:
    """获取所有未跳过的项目"""
    return [p for p in TEST_PROJECTS if not p.skip]


def get_project_by_name(name: str) -> Optional[TestProject]:
    """根据名称获取项目"""
    for project in TEST_PROJECTS:
        if project.name == name:
            return project
    return None

