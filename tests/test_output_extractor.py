"""测试智能输出提取器的命令分类功能"""

import sys
import io

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, 'src')

from auto_deployer.llm.output_extractor import CommandOutputExtractor, CommandType


def test_command_classification():
    """测试命令分类功能"""
    extractor = CommandOutputExtractor()

    # 测试噪音型命令
    noise_commands = [
        "npm install",
        "npm install express",
        "pip install requests",
        "apt-get install nginx",
        "npm run build",
    ]

    print("=== 噪音型命令分类测试 ===")
    for cmd in noise_commands:
        cmd_type = extractor._classify_command(cmd)
        print(f"  {cmd:30s} -> {cmd_type.value}")
        assert cmd_type == CommandType.NOISE, f"Expected NOISE, got {cmd_type}"

    # 测试信息型命令
    info_commands = [
        "ls -la",
        "cat package.json",
        "pwd",
        "which node",
        "node -v",
        "systemctl status nginx",
        "ps aux",
    ]

    print("\n=== 信息型命令分类测试 ===")
    for cmd in info_commands:
        cmd_type = extractor._classify_command(cmd)
        print(f"  {cmd:30s} -> {cmd_type.value}")
        assert cmd_type == CommandType.INFO, f"Expected INFO, got {cmd_type}"

    # 测试操作型命令
    operation_commands = [
        "git clone https://github.com/user/repo",
        "docker run -p 3000:3000 app",
        "systemctl start nginx",
        "pm2 start app.js",
        "cd /home/user",
    ]

    print("\n=== 操作型命令分类测试 ===")
    for cmd in operation_commands:
        cmd_type = extractor._classify_command(cmd)
        print(f"  {cmd:30s} -> {cmd_type.value}")
        assert cmd_type == CommandType.OPERATION, f"Expected OPERATION, got {cmd_type}"

    print("\n✅ 所有分类测试通过!")


def test_output_extraction():
    """测试不同类型命令的输出提取"""
    extractor = CommandOutputExtractor()

    # 1. 测试噪音型命令 - npm install
    print("\n=== 噪音型命令输出提取测试 ===")
    npm_output = """
npm WARN deprecated package1@1.0.0
npm WARN deprecated package2@2.0.0
added 125 packages from 300 contributors and audited 450 packages in 12.5s
found 0 vulnerabilities
    """ + "\n".join([f"package-{i}@1.0.0" for i in range(100)])  # 模拟大量包列表

    result = extractor.extract(
        stdout=npm_output,
        stderr="",
        success=True,
        exit_code=0,
        command="npm install express"
    )

    print(f"原始输出长度: {result.full_length} 字符")
    print(f"提取后长度: {result.extracted_length} 字符")
    print(f"压缩率: {(1 - result.extracted_length / result.full_length) * 100:.1f}%")
    print(f"摘要: {result.summary}")
    print(f"关键信息行数: {len(result.key_info)}")
    assert result.extracted_length < result.full_length * 0.2, "噪音型命令应该大幅压缩"

    # 2. 测试信息型命令 - ls
    print("\n=== 信息型命令输出提取测试 ===")
    ls_output = """
drwxr-xr-x  5 user  staff   160 Jan 10 10:00 src
drwxr-xr-x  3 user  staff    96 Jan 10 10:00 tests
-rw-r--r--  1 user  staff  1234 Jan 10 10:00 package.json
-rw-r--r--  1 user  staff  5678 Jan 10 10:00 README.md
    """

    result = extractor.extract(
        stdout=ls_output,
        stderr="",
        success=True,
        exit_code=0,
        command="ls -la"
    )

    print(f"原始输出长度: {result.full_length} 字符")
    print(f"提取后长度: {result.extracted_length} 字符")
    print(f"摘要: {result.summary}")
    print(f"关键信息行数: {len(result.key_info)}")
    # 信息型命令应该基本不压缩
    assert result.extracted_length >= result.full_length * 0.8, "信息型命令应该保留大部分输出"

    # 3. 测试操作型命令 - git clone
    print("\n=== 操作型命令输出提取测试 ===")
    git_output = """
Cloning into 'repo'...
remote: Enumerating objects: 1000, done.
remote: Counting objects: 100% (1000/1000), done.
remote: Compressing objects: 100% (500/500), done.
remote: Total 1000 (delta 300), reused 900 (delta 250)
Receiving objects: 100% (1000/1000), 5.50 MiB | 2.50 MiB/s, done.
Resolving deltas: 100% (300/300), done.
Successfully cloned repository
    """

    result = extractor.extract(
        stdout=git_output,
        stderr="",
        success=True,
        exit_code=0,
        command="git clone https://github.com/user/repo"
    )

    print(f"原始输出长度: {result.full_length} 字符")
    print(f"提取后长度: {result.extracted_length} 字符")
    print(f"压缩率: {(1 - result.extracted_length / result.full_length) * 100:.1f}%")
    print(f"摘要: {result.summary}")
    print(f"关键信息行数: {len(result.key_info)}")
    print(f"关键信息: {result.key_info[:3]}")

    # 4. 测试失败命令(不应受分类影响)
    print("\n=== 失败命令输出提取测试 ===")
    error_output = """
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /path/to/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory, open '/path/to/package.json'
    """

    result = extractor.extract(
        stdout="",
        stderr=error_output,
        success=False,
        exit_code=1,
        command="npm install"
    )

    print(f"摘要: {result.summary}")
    print(f"错误类型: {result.key_info}")
    print(f"错误上下文: {result.error_context[:100]}...")
    assert result.error_context, "失败命令应该有错误上下文"

    print("\n✅ 所有输出提取测试通过!")


def test_format_for_llm():
    """测试LLM格式化输出"""
    extractor = CommandOutputExtractor()

    print("\n=== LLM格式化输出测试 ===")

    # 测试噪音型命令
    npm_output = "added 125 packages\n" * 50
    extracted = extractor.extract(
        stdout=npm_output,
        stderr="",
        success=True,
        exit_code=0,
        command="npm install express"
    )

    formatted = extractor.format_for_llm(extracted)
    print(f"格式化后输出长度: {len(formatted)} 字符")
    print("格式化后输出预览:")
    print(formatted[:300])

    assert len(formatted) < len(npm_output), "格式化后应该更短"
    assert "[Compressed:" in formatted, "应该包含压缩信息"

    print("\n✅ LLM格式化测试通过!")


if __name__ == "__main__":
    print("开始测试智能输出提取器...\n")

    try:
        test_command_classification()
        test_output_extraction()
        test_format_for_llm()

        print("\n" + "=" * 50)
        print("🎉 所有测试通过!")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
