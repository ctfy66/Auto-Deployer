"""测试并行运行器功能"""
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auto_deployer.config import load_config
from tests.real_deployment.test_projects import get_projects_by_difficulty
from tests.real_deployment.parallel_runner import ParallelTestRunner

def test_parallel_runner():
    """测试并行运行器基本功能"""
    print("🧪 测试并行运行器...")
    
    # 加载配置
    try:
        config = load_config()
        print(f"✅ 配置加载成功: {config.llm.model}")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False
    
    # 获取简单测试项目
    projects = get_projects_by_difficulty("easy")
    if not projects:
        print("❌ 没有找到测试项目")
        return False
    
    # 只测试第一个项目
    projects = projects[:1]
    print(f"✅ 找到 {len(projects)} 个测试项目: {[p.name for p in projects]}")
    
    # 创建并行运行器
    runner = ParallelTestRunner(
        config=config,
        max_workers=1,  # 只用1个worker测试
        retry_on_failure=False  # 禁用重试以加快测试
    )
    print("✅ 并行运行器创建成功")
    
    # 测试环境配置
    env_config = {"mode": "local"}
    
    print("\n开始测试（这可能需要几分钟）...")
    print("注意：这将执行真实的部署操作\n")
    
    try:
        results = runner.run_tests(
            projects=projects,
            env_config=env_config,
            local_mode=True
        )
        
        print(f"\n✅ 测试完成，获得 {len(results)} 个结果")
        
        if results:
            result = results[0]
            print(f"\n项目: {result.project_name}")
            print(f"成功: {result.success}")
            print(f"耗时: {result.deployment_time_seconds:.1f}秒")
            print(f"迭代: {result.total_iterations}")
            if result.retry_info:
                print(f"重试: {result.retry_info.total_attempts}次")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("="*60)
    print("并行测试运行器验证")
    print("="*60)
    print()
    
    success = test_parallel_runner()
    
    print()
    print("="*60)
    if success:
        print("✅ 所有测试通过")
        sys.exit(0)
    else:
        print("❌ 测试失败")
        sys.exit(1)
