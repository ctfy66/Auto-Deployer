# LLM Providers Guide

Auto-Deployer支持多个主流LLM提供商。本文档说明如何配置和使用不同的LLM服务。

## 快速开始

### 1. 选择提供商

在 `config/default_config.json` 中设置：

```json
{
  "llm": {
    "provider": "gemini",
    "model": "gemini-2.0-flash-exp",
    "api_key": null,
    "temperature": 0.0
  }
}
```

### 2. 设置API密钥

通过环境变量设置API密钥（推荐）：

```bash
# Linux/Mac
export AUTO_DEPLOYER_GEMINI_API_KEY="your-api-key"

# Windows PowerShell
$env:AUTO_DEPLOYER_GEMINI_API_KEY = "your-api-key"

# 或者在.env文件中
AUTO_DEPLOYER_GEMINI_API_KEY=your-api-key
```

## 支持的提供商

### Google Gemini（推荐）

**优势**: 高性价比，快速响应，免费额度充足

**配置**:
```json
{
  "provider": "gemini",
  "model": "gemini-2.0-flash-exp"
}
```

**推荐模型**:
- `gemini-2.0-flash-exp` - 最新实验版本，速度快
- `gemini-1.5-pro` - 更强大的推理能力
- `gemini-1.5-flash` - 平衡性能和速度

**获取API密钥**: https://makersuite.google.com/app/apikey

**环境变量**: `AUTO_DEPLOYER_GEMINI_API_KEY`

---

### OpenAI

**优势**: 成熟稳定，广泛使用

**配置**:
```json
{
  "provider": "openai",
  "model": "gpt-4o"
}
```

**推荐模型**:
- `gpt-4o` - 最新旗舰模型
- `gpt-4o-mini` - 更经济的选择
- `gpt-4-turbo` - 速度优化版本
- `gpt-3.5-turbo` - 最经济但能力稍弱

**获取API密钥**: https://platform.openai.com/api-keys

**环境变量**: `AUTO_DEPLOYER_OPENAI_API_KEY`

---

### Anthropic Claude

**优势**: 出色的推理能力，长上下文支持

**配置**:
```json
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022"
}
```

**推荐模型**:
- `claude-3-5-sonnet-20241022` - 最新Sonnet版本，性能优异
- `claude-3-opus-20240229` - 最强大的模型
- `claude-3-haiku-20240307` - 快速经济的选择

**获取API密钥**: https://console.anthropic.com/

**环境变量**: `AUTO_DEPLOYER_ANTHROPIC_API_KEY`

---

### DeepSeek

**优势**: 国产模型，中文友好，性价比高

**配置**:
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat"
}
```

**推荐模型**:
- `deepseek-chat` - 通用对话模型
- `deepseek-coder` - 专门优化的代码模型

**获取API密钥**: https://platform.deepseek.com/

**环境变量**: `AUTO_DEPLOYER_DEEPSEEK_API_KEY`

---

### OpenRouter

**优势**: 一个API访问多个模型，灵活切换

**配置**:
```json
{
  "provider": "openrouter",
  "model": "anthropic/claude-3.5-sonnet"
}
```

**推荐模型**:
- `anthropic/claude-3.5-sonnet` - Claude 3.5 Sonnet
- `openai/gpt-4o` - GPT-4o
- `google/gemini-2.0-flash-exp` - Gemini 2.0 Flash
- `meta-llama/llama-3.1-405b-instruct` - Llama 3.1 405B

**获取API密钥**: https://openrouter.ai/keys

**环境变量**: `AUTO_DEPLOYER_OPENROUTER_API_KEY`

**特点**:
- 支持100+模型
- 自动负载均衡
- 统一的计费系统

---

### OpenAI兼容服务

**优势**: 使用本地模型或自定义端点

**配置**:
```json
{
  "provider": "openai-compatible",
  "model": "llama3.1",
  "endpoint": "http://localhost:11434/v1",
  "api_key": null
}
```

**支持的服务**:

#### Ollama（本地运行）
```json
{
  "provider": "openai-compatible",
  "model": "llama3.1",
  "endpoint": "http://localhost:11434/v1"
}
```
无需API密钥，本地运行完全免费。

#### LM Studio（本地运行）
```json
{
  "provider": "openai-compatible",
  "model": "your-model-name",
  "endpoint": "http://localhost:1234/v1"
}
```

#### Groq（高速推理）
```json
{
  "provider": "openai-compatible",
  "model": "mixtral-8x7b-32768",
  "endpoint": "https://api.groq.com/openai/v1",
  "api_key": "your-groq-api-key"
}
```
获取密钥: https://console.groq.com/

#### Together AI
```json
{
  "provider": "openai-compatible",
  "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
  "endpoint": "https://api.together.xyz/v1",
  "api_key": "your-together-api-key"
}
```
获取密钥: https://api.together.xyz/settings/api-keys

#### vLLM（自建服务）
```json
{
  "provider": "openai-compatible",
  "model": "your-model-name",
  "endpoint": "http://your-server:8000/v1"
}
```

---

## 高级配置

### 使用代理

如果需要通过代理访问API：

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "proxy": "http://127.0.0.1:7890"
  }
}
```

或通过环境变量:
```bash
export AUTO_DEPLOYER_LLM_PROXY="http://127.0.0.1:7890"
```

### 自定义端点

某些提供商支持自定义端点：

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "endpoint": "https://your-custom-endpoint.com/v1"
  }
}
```

### 调整温度参数

控制输出的随机性（0.0-2.0）：

```json
{
  "llm": {
    "temperature": 0.0  // 0.0 = 确定性输出（推荐）
  }
}
```

- `0.0`: 完全确定性，每次运行结果一致（推荐用于部署）
- `0.7`: 平衡创造性和一致性
- `1.5+`: 更高创造性，但可能不稳定

## 成本对比

| 提供商 | 模型 | 输入价格 (per 1M tokens) | 输出价格 (per 1M tokens) | 备注 |
|--------|------|-------------------------|-------------------------|------|
| Gemini | gemini-2.0-flash-exp | 免费 | 免费 | 实验版本 |
| Gemini | gemini-1.5-flash | $0.075 | $0.30 | 高性价比 |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | 经济选择 |
| OpenAI | gpt-4o | $2.50 | $10.00 | 旗舰模型 |
| Anthropic | claude-3-haiku | $0.25 | $1.25 | 经济选择 |
| Anthropic | claude-3-5-sonnet | $3.00 | $15.00 | 高性能 |
| DeepSeek | deepseek-chat | ¥1.0 | ¥2.0 | 人民币计价 |
| Ollama | 本地模型 | 免费 | 免费 | 本地运行 |

*价格会变化，请查看各提供商官网获取最新信息*

## 性能对比

根据部署任务的表现（主观评价）：

| 提供商 | 模型 | 推理能力 | 速度 | 稳定性 | 推荐场景 |
|--------|------|---------|------|--------|---------|
| Gemini | gemini-2.0-flash-exp | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 日常部署 |
| OpenAI | gpt-4o | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 复杂项目 |
| Anthropic | claude-3-5-sonnet | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 复杂推理 |
| DeepSeek | deepseek-chat | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 中文项目 |
| Ollama | llama3.1 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 离线/隐私 |

## 推荐配置

### 最佳性价比
```json
{
  "provider": "gemini",
  "model": "gemini-2.0-flash-exp"
}
```

### 最强性能
```json
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022"
}
```

### 本地部署
```json
{
  "provider": "openai-compatible",
  "model": "llama3.1",
  "endpoint": "http://localhost:11434/v1"
}
```

### 中文优化
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat"
}
```

## 故障排查

### 常见错误

**API密钥无效**
```
ValueError: Gemini API key is required
```
解决: 检查环境变量是否正确设置

**连接超时**
```
requests.exceptions.Timeout
```
解决:
1. 检查网络连接
2. 配置代理（如果在国内访问OpenAI）
3. 增加timeout参数

**模型不存在**
```
404 Not Found: model not found
```
解决: 确认模型名称正确，查看提供商文档

**速率限制**
```
429 Too Many Requests
```
解决: 系统会自动重试，或等待片刻后重试

### 测试配置

测试LLM配置是否正常：

```bash
python -c "
from src.auto_deployer.config import load_config
from src.auto_deployer.llm import create_llm_provider

config = load_config()
provider = create_llm_provider(config.llm)
response = provider.generate_response('Hello, respond with OK', response_format='text')
print(f'Provider test: {response}')
"
```

## 更多信息

- [项目文档](../CLAUDE.md)
- [配置文件示例](../config/default_config.json)
- [LLM提供商实现](../src/auto_deployer/llm/)

## 贡献

欢迎添加新的LLM提供商支持！查看 [CLAUDE.md](../CLAUDE.md#adding-a-new-llm-provider) 了解如何添加新提供商。
