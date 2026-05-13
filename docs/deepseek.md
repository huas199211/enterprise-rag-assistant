# DeepSeek API 接入

本项目通过 OpenAI-compatible 格式接入 DeepSeek。

## 配置项

```env
LLM_PROVIDER=openai_compatible
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=你的 DeepSeek API Key
CHAT_MODEL=deepseek-v4-flash
```

## 模型选择

- `deepseek-v4-flash`：适合普通企业知识库问答，响应速度更适合在线演示。
- `deepseek-v4-pro`：适合需要更强推理能力的场景。

当前项目默认使用 `deepseek-v4-flash`，因为 RAG 的主要事实来源来自检索片段，模型负责基于上下文组织答案和拒答。

## 常见错误

- `402 Payment Required`：API Key 有效，但 DeepSeek 账户余额或计费状态不可用。
- `401/403`：API Key 无效、权限不足或请求头配置错误。

## Embedding

DeepSeek 主要用于聊天补全。本项目中文向量检索默认配置为 `BAAI/bge-m3`，维度 `1024`。开发环境使用本地 fallback，生产环境可以接入支持 `BAAI/bge-m3` 的 OpenAI-compatible embedding 服务。
