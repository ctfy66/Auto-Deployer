# 多LLM提供商支持 - 实现说明

## 概述

Auto-Deployer现已支持多个主流LLM提供商，包括：
- ✅ Google Gemini（原有，已重构）
- ✅ OpenAI (GPT-4o, GPT-4-turbo, etc.)
- ✅ Anthropic Claude (Claude 3.5 Sonnet, Opus, Haiku)
- ✅ DeepSeek (deepseek-chat, deepseek-coder)
- ✅ OpenRouter (访问100+模型)
- ✅ OpenAI-Compatible (Ollama, LM Studio, Groq, Together AI, vLLM等)

## 架构设计

### 提供商抽象层

所有LLM提供商实现统一接口 `BaseLLMProvider`：

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "json",
        timeout: int = 60,
        max_retries: int = 3,
    ) -> Optional[str]:
        pass
```

### 文件结构

```
src/auto_deployer/llm/
├── base.py                   # 基类和工厂函数
├── gemini.py                 # Google Gemini提供商
├── openai.py                 # OpenAI提供商
├── anthropic.py              # Anthropic Claude提供商
├── deepseek.py               # DeepSeek提供商
├── openrouter.py             # OpenRouter提供商
├── openai_compatible.py      # 通用OpenAI兼容提供商
└── agent.py                  # 已重构使用provider抽象
```

## 主要改动

### 1. 新增提供商实现

#### [src/auto_deployer/llm/gemini.py](../src/auto_deployer/llm/gemini.py)
- 将原agent.py中的Gemini调用封装为GeminiProvider类
- 实现统一的generate_response接口

#### [src/auto_deployer/llm/openai.py](../src/auto_deployer/llm/openai.py)
- OpenAI官方API实现
- 支持GPT-4o, GPT-4-turbo, GPT-3.5-turbo等模型
- 支持JSON响应格式

#### [src/auto_deployer/llm/anthropic.py](../src/auto_deployer/llm/anthropic.py)
- Anthropic Claude API实现
- 支持Claude 3.5 Sonnet, Opus, Haiku
- 注意：Claude没有原生JSON模式，通过prompt指导

#### [src/auto_deployer/llm/deepseek.py](../src/auto_deployer/llm/deepseek.py)
- DeepSeek API实现（OpenAI兼容）
- 支持deepseek-chat和deepseek-coder模型

#### [src/auto_deployer/llm/openrouter.py](../src/auto_deployer/llm/openrouter.py)
- OpenRouter聚合服务实现
- 一个API访问100+模型

#### [src/auto_deployer/llm/openai_compatible.py](../src/auto_deployer/llm/openai_compatible.py)
- 通用OpenAI兼容端点实现
- 支持Ollama, LM Studio, vLLM, Groq, Together AI等

### 2. 重构Agent类

#### [src/auto_deployer/llm/agent.py](../src/auto_deployer/llm/agent.py)

**DeploymentAgent类**:
- `__init__`: 添加provider初始化
- `_think`: 简化为使用provider.generate_response()
- `_think_local`: 简化为使用provider.generate_response()
- `_create_deployment_plan`: 简化为使用provider.generate_response()

**DeploymentPlanner类**:
- `__init__`: 添加provider初始化
- `create_plan`: 简化为使用provider.generate_response()

**改动前** (直接调用Gemini API):
```python
url = f"{self.base_endpoint}?key={self.config.api_key}"
body = {
    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    "generationConfig": {
        "temperature": self.config.temperature,
        "responseMimeType": "application/json",
    },
}
response = self.session.post(url, json=body, timeout=60)
# ... 解析响应 ...
```

**改动后** (使用provider抽象):
```python
text = self.llm_provider.generate_response(
    prompt=prompt,
    response_format="json",
    timeout=60,
    max_retries=3
)
```

### 3. 更新配置

#### [config/default_config.json](../config/default_config.json)
- 添加proxy配置项
- 添加`_llm_providers`注释部分，列出所有支持的提供商和配置示例

### 4. 文档更新

#### [CLAUDE.md](../CLAUDE.md)
- 更新Configuration部分，说明支持多提供商
- 添加完整的"LLM Providers"章节
- 更新"Adding a New LLM Provider"部分

#### [docs/LLM_PROVIDERS.md](../docs/LLM_PROVIDERS.md) (新建)
- 用户友好的完整LLM提供商使用指南
- 包含配置示例、成本对比、性能对比
- 包含故障排查和测试方法

## 使用方法

### 切换到DeepSeek

**方法1: 修改配置文件**
```json
{
  "llm": {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "temperature": 0.0
  }
}
```

**方法2: 环境变量**
```bash
export AUTO_DEPLOYER_DEEPSEEK_API_KEY="your-api-key"
```

### 使用OpenAI

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.0
  }
}
```

```bash
export AUTO_DEPLOYER_OPENAI_API_KEY="your-api-key"
```

### 使用本地Ollama

```json
{
  "llm": {
    "provider": "openai-compatible",
    "model": "llama3.1",
    "endpoint": "http://localhost:11434/v1",
    "temperature": 0.0
  }
}
```

无需API密钥！

## 测试

### 测试单个提供商

```python
from src.auto_deployer.config import LLMConfig
from src.auto_deployer.llm import create_llm_provider

# 测试DeepSeek
config = LLMConfig(
    provider="deepseek",
    model="deepseek-chat",
    api_key="your-api-key"
)
provider = create_llm_provider(config)
response = provider.generate_response(
    prompt="Say 'Hello World' in JSON format",
    response_format="json"
)
print(response)
```

### 运行现有测试

所有现有测试应该继续工作，因为默认使用Gemini提供商（向后兼容）。

```bash
python -m pytest tests/
```

## 向后兼容性

✅ **完全向后兼容**
- 默认使用Gemini提供商
- 现有配置文件无需修改
- 环境变量保持不变
- 所有现有功能正常工作

## 性能影响

- ✅ 无性能损失：provider调用是轻量级的
- ✅ 相同的重试机制和错误处理
- ✅ 相同的超时配置

## 扩展性

添加新提供商非常简单：

1. 创建新文件 `src/auto_deployer/llm/newprovider.py`
2. 继承`BaseLLMProvider`或实现相同接口
3. 在`base.py`的`create_llm_provider()`中添加分支
4. 更新`__init__.py`导出

示例：
```python
# src/auto_deployer/llm/newprovider.py
class NewProvider:
    def __init__(self, config: LLMConfig):
        self.config = config
        # ... 初始化 ...

    def generate_response(self, prompt, **kwargs):
        # ... 实现 ...
        return response_text
```

```python
# src/auto_deployer/llm/base.py
def create_llm_provider(config):
    if config.provider == "newprovider":
        from .newprovider import NewProvider
        return NewProvider(config)
    # ...
```

## 常见问题

### Q: 如何选择最合适的提供商？
A: 查看 [docs/LLM_PROVIDERS.md](../docs/LLM_PROVIDERS.md) 的性能和成本对比。

### Q: 原有的Gemini配置还能用吗？
A: 完全可以，默认就是Gemini，无需修改。

### Q: 如何使用国内的DeepSeek？
A: 设置provider为"deepseek"，设置API密钥即可。

### Q: 可以使用本地模型吗？
A: 可以！使用Ollama等工具，配置为"openai-compatible"提供商。

### Q: 如何配置代理？
A: 在config.json中设置proxy字段，或设置环境变量`AUTO_DEPLOYER_LLM_PROXY`。

## 未来计划

- [ ] 添加Azure OpenAI支持
- [ ] 添加Cohere支持
- [ ] 添加Google Vertex AI支持
- [ ] 自动选择最优提供商（基于成本/性能）
- [ ] 提供商降级（主提供商失败时自动切换）

## 贡献

欢迎贡献新的提供商实现！请遵循现有代码风格，并更新相关文档。

---

**实现时间**: 2025-01
**作者**: Claude Code
**版本**: 1.0
