"""测试自由输入功能的示例脚本"""

from auto_deployer.interaction import (
    InteractionRequest,
    InputType,
    QuestionCategory,
    CLIInteractionHandler,
)


def test_custom_input_features():
    """演示各种自由输入场景"""
    handler = CLIInteractionHandler(use_rich=False)

    print("=" * 60)
    print("自由输入功能测试")
    print("=" * 60)

    # 场景 1: 计划确认场景 (允许自定义)
    print("\n【场景 1】部署计划确认 (允许自定义输入)")
    request1 = InteractionRequest(
        question="是否继续执行此部署计划?",
        input_type=InputType.CHOICE,
        options=["是的,继续执行", "不,取消部署"],
        category=QuestionCategory.CONFIRMATION,
        context="策略: Docker容器化部署\n步骤: 5个\n预计时间: 10分钟",
        default="是的,继续执行",
        allow_custom=True,
    )

    print("\n说明: 您可以:")
    print("  - 输入 1 或 2 选择预设选项")
    print("  - 输入 0 进入自定义输入模式")
    print("  - 直接输入文本 (如 '先让我检查配置') 作为自定义响应\n")

    response1 = handler.ask(request1)
    print(f"\n✅ 收到响应: {response1.value}")
    print(f"   是否自定义: {response1.is_custom}")
    print(f"   选择的选项: {response1.selected_option}")

    # 场景 2: 错误恢复场景 (允许自定义)
    print("\n" + "=" * 60)
    print("【场景 2】步骤失败后的错误恢复 (允许自定义输入)")
    request2 = InteractionRequest(
        question="步骤 '安装依赖' 失败: npm install 返回错误码 1\n您想怎么做?",
        input_type=InputType.CHOICE,
        options=["重试此步骤", "跳过并继续", "终止部署"],
        category=QuestionCategory.ERROR_RECOVERY,
        allow_custom=True,
    )

    print("\n说明: 您可以:")
    print("  - 输入 1-3 选择预设操作")
    print("  - 输入 0 自定义恢复策略")
    print("  - 直接输入命令 (如 'npm install --force') 尝试修复\n")

    response2 = handler.ask(request2)
    print(f"\n✅ 收到响应: {response2.value}")
    print(f"   是否自定义: {response2.is_custom}")

    # 场景 3: 配置决策 (允许自定义)
    print("\n" + "=" * 60)
    print("【场景 3】端口配置决策 (允许自定义输入)")
    request3 = InteractionRequest(
        question="检测到端口 3000 已被占用,请选择新端口:",
        input_type=InputType.CHOICE,
        options=["3001", "5173", "8080"],
        category=QuestionCategory.DECISION,
        context="当前应用: React开发服务器",
        default="3001",
        allow_custom=True,
    )

    print("\n说明: 您可以:")
    print("  - 输入 1-3 选择建议的端口")
    print("  - 输入 0 指定自己的端口号")
    print("  - 直接输入端口号 (如 '4000')\n")

    response3 = handler.ask(request3)
    print(f"\n✅ 收到响应: {response3.value}")
    print(f"   是否自定义: {response3.is_custom}")

    # 场景 4: 纯文本输入
    print("\n" + "=" * 60)
    print("【场景 4】环境变量输入 (纯文本模式)")
    request4 = InteractionRequest(
        question="请输入 DATABASE_URL 环境变量:",
        input_type=InputType.TEXT,
        category=QuestionCategory.INFORMATION,
        context="示例: postgresql://user:pass@localhost:5432/dbname",
        default="postgresql://localhost:5432/myapp",
    )

    response4 = handler.ask(request4)
    print(f"\n✅ 收到响应: {response4.value}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_custom_input_features()
    except KeyboardInterrupt:
        print("\n\n测试已取消")
