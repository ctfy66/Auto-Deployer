"""测试 StepExecutor 的输出提取和日志记录功能"""

import sys
import io

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, 'src')

import logging
from unittest.mock import Mock, MagicMock
from auto_deployer.orchestrator.step_executor import StepExecutor
from auto_deployer.orchestrator.models import StepContext, DeployContext
from auto_deployer.config import LLMConfig


def test_command_output_extraction():
    """测试命令输出提取和日志记录"""
    print("\n=== 测试命令输出提取和显示 ===\n")

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建模拟的配置
    llm_config = LLMConfig(
        provider="gemini",
        model="gemini-2.0-flash-exp",
        api_key="dummy-key",
        temperature=0.0
    )

    # 创建模拟的session
    mock_session = Mock()

    # 创建模拟的interaction handler
    mock_interaction = Mock()

    # 创建 StepExecutor
    executor = StepExecutor(
        llm_config=llm_config,
        session=mock_session,
        interaction_handler=mock_interaction,
        max_iterations_per_step=10,
        is_windows=False
    )

    print("1️⃣ 测试噪音型命令 (npm install)")
    print("-" * 60)

    # 模拟npm install的输出
    npm_output = """
npm WARN deprecated package1@1.0.0
npm WARN deprecated package2@2.0.0
npm WARN deprecated package3@3.0.0
    """ + "\n".join([f"added package-{i}@1.0.0" for i in range(50)])
    npm_output += "\n\nadded 125 packages from 300 contributors and audited 450 packages in 12.5s\nfound 0 vulnerabilities"

    # 配置mock返回
    mock_result = Mock()
    mock_result.stdout = npm_output
    mock_result.stderr = ""
    mock_result.ok = True
    mock_result.exit_status = 0
    mock_session.run.return_value = mock_result

    # 执行命令
    command_record = executor._execute_command("npm install express")

    print(f"\n原始输出长度: {len(npm_output)} 字符")
    print(f"提取后输出长度: {len(command_record.stdout)} 字符")
    print(f"压缩率: {(1 - len(command_record.stdout) / len(npm_output)) * 100:.1f}%")

    print("\n\n2️⃣ 测试信息型命令 (ls -la)")
    print("-" * 60)

    # 模拟ls输出
    ls_output = """total 48
drwxr-xr-x  10 user  staff   320 Jan 10 10:00 .
drwxr-xr-x   5 user  staff   160 Jan 10 09:00 ..
-rw-r--r--   1 user  staff  1234 Jan 10 10:00 package.json
-rw-r--r--   1 user  staff  5678 Jan 10 10:00 README.md
drwxr-xr-x   5 user  staff   160 Jan 10 10:00 src
drwxr-xr-x   3 user  staff    96 Jan 10 10:00 tests
"""

    mock_result.stdout = ls_output
    mock_result.stderr = ""
    mock_result.ok = True
    mock_result.exit_status = 0
    mock_session.run.return_value = mock_result

    command_record = executor._execute_command("ls -la")

    print(f"\n原始输出长度: {len(ls_output)} 字符")
    print(f"提取后输出长度: {len(command_record.stdout)} 字符")
    print(f"保留率: {(len(command_record.stdout) / len(ls_output)) * 100:.1f}%")

    print("\n\n3️⃣ 测试操作型命令 (git clone)")
    print("-" * 60)

    # 模拟git clone输出
    git_output = """Cloning into 'my-repo'...
remote: Enumerating objects: 1000, done.
remote: Counting objects: 100% (1000/1000), done.
remote: Compressing objects: 100% (500/500), done.
remote: Total 1000 (delta 300), reused 900 (delta 250)
Receiving objects: 100% (1000/1000), 5.50 MiB | 2.50 MiB/s, done.
Resolving deltas: 100% (300/300), done.
"""

    mock_result.stdout = git_output
    mock_result.stderr = ""
    mock_result.ok = True
    mock_result.exit_status = 0
    mock_session.run.return_value = mock_result

    command_record = executor._execute_command("git clone https://github.com/user/my-repo")

    print(f"\n原始输出长度: {len(git_output)} 字符")
    print(f"提取后输出长度: {len(command_record.stdout)} 字符")
    print(f"压缩率: {(1 - len(command_record.stdout) / len(git_output)) * 100:.1f}%")

    print("\n\n4️⃣ 测试失败命令")
    print("-" * 60)

    # 模拟错误输出
    error_output = """npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /nonexistent/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/nonexistent/package.json'
npm ERR! A complete log of this run can be found in:
npm ERR!     /Users/user/.npm/_logs/2024-01-10T10_00_00_000Z-debug.log
"""

    mock_result.stdout = ""
    mock_result.stderr = error_output
    mock_result.ok = False
    mock_result.exit_status = 1
    mock_session.run.return_value = mock_result

    command_record = executor._execute_command("npm install")

    print(f"\n原始错误输出长度: {len(error_output)} 字符")
    print(f"提取后输出长度: {len(command_record.stdout)} 字符")

    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)
    print("\n💡 提示: LLM将看到提取后的简洁输出,而不是完整的原始输出")


if __name__ == "__main__":
    try:
        test_command_output_extraction()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
