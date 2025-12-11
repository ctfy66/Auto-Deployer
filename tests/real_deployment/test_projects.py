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
        tags=["docker", "static", "simple"]
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
        skip=True  # Express主仓库较复杂，暂时跳过
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
        skip=True  # Flask主仓库较复杂，暂时跳过
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
        skip=True  # Next.js主仓库较复杂，暂时跳过
    ),
    
    # ========== Medium 难度项目 ==========
    TestProject(
        name="docker-compose-voting-app",
        repo_url="https://github.com/dockersamples/example-voting-app.git",
        description="Docker官方示例投票应用，使用docker-compose，包含多个服务",
        expected_strategy="docker-compose",
        difficulty="medium",
        expected_time_minutes=12,
        verification=VerificationConfig(
            urls=[
                "http://localhost:5000",  # 前端
                "http://localhost:5001"   # 结果页面
            ],
            expected_status=200,
            timeout=15
        ),
        tags=["docker-compose", "fullstack", "multi-service"]
    ),
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
        skip=True  # Hugo主仓库较复杂，暂时跳过
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
        skip=True  # Next.js主仓库较复杂，暂时跳过
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
        skip=True  # Django主仓库较复杂，暂时跳过
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
        tags=["docker-compose", "microservices", "complex"]
    ),
    
    # ========== 真实使用过的项目 ==========
    TestProject(
        name="myblog-vitepress",
        repo_url="https://github.com/ctfy66/myblog.git",
        description="VitePress博客项目，需要构建后部署到Nginx，已在真实环境中测试过",
        expected_strategy="static",
        difficulty="medium",
        expected_time_minutes=8,
        verification=VerificationConfig(
            urls=["http://localhost:80"],
            expected_status=200,
            timeout=10
        ),
        tags=["static", "vitepress", "nginx", "real-world"]
    ),
    
    # ========== 简单示例项目（适合快速测试）==========
    TestProject(
        name="nodejs-hello-world",
        repo_url="https://github.com/nodejs/node.git",
        description="Node.js官方仓库，包含简单示例，测试传统Node.js部署",
        expected_strategy="traditional",
        difficulty="easy",
        expected_time_minutes=5,
        verification=VerificationConfig(
            urls=["http://localhost:3000"],
            expected_status=200,
            timeout=10
        ),
        tags=["nodejs", "simple"],
        skip=True  # Node.js主仓库较复杂
    ),
    TestProject(
        name="python-hello-world",
        repo_url="https://github.com/python/cpython.git",
        description="Python官方仓库，测试Python环境部署",
        expected_strategy="traditional",
        difficulty="easy",
        expected_time_minutes=5,
        verification=VerificationConfig(
            urls=["http://localhost:5000"],
            expected_status=200,
            timeout=10
        ),
        tags=["python", "simple"],
        skip=True  # Python主仓库较复杂
    ),
    
    # ========== 静态站点项目 ==========
    TestProject(
        name="static-html-sample",
        repo_url="https://github.com/octocat/Hello-World.git",
        description="GitHub官方Hello World示例，简单的HTML静态站点",
        expected_strategy="static",
        difficulty="easy",
        expected_time_minutes=3,
        verification=VerificationConfig(
            urls=["http://localhost:80"],
            expected_status=200,
            timeout=10
        ),
        tags=["static", "html", "simple"]
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

