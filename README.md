# 企业知识库智能助手

这是一个面向企业内部知识库的检索增强问答工具，不是单纯聊天机器人。它支持文档上传、切分、向量化、检索召回、可选重排序、基于来源片段回答、多轮会话、后台参数配置、日志记录、反馈和评估集。

## 功能范围

- 上传 PDF / Word / Markdown / TXT
- 文档解析、片段切分、向量化、入库
- PostgreSQL 保存文档、片段、会话、问答日志、反馈和配置
- Qdrant 保存向量索引
- 检索召回，支持简单重排序
- 基于检索片段回答，并返回引用来源
- 无相关资料时明确回答不知道
- 多轮会话
- 后台配置片段长度、召回数量、模型、向量化和重排序
- 支持相似度阈值 `min_score`，低相关召回直接拒答
- 记录问题、答案、检索片段、耗时
- 答案反馈按钮
- `data/eval_set.jsonl` 内置 35 条评估样例

## 快速启动

```powershell
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

## 基础设施

```text
PostgreSQL: 127.0.0.1:5432
Qdrant:     http://127.0.0.1:6333/dashboard
Adminer:    http://127.0.0.1:8080
```

Adminer 登录：

```text
System: PostgreSQL
Server: postgres
Username: rag
Password: rag_password
Database: rag
```

## DeepSeek 配置

项目通过 OpenAI-compatible API 接入 DeepSeek：

```env
LLM_PROVIDER=openai_compatible
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=你的 DeepSeek 接口密钥
CHAT_MODEL=deepseek-v4-flash
```

## 中文向量模型配置

中文知识库默认使用 `BAAI/bge-m3` 配置，维度 `1024`。开发环境可以使用本地备用向量化，生产环境可接入兼容 OpenAI 格式的向量服务。

```env
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
DEFAULT_MIN_SCORE=0.18
```

## 重排序配置

默认使用本地词覆盖重排序，不依赖外部服务。生产环境可以把 `RERANK_PROVIDER` 改为 `remote`，并配置兼容 `/rerank` 接口的重排序服务。

```env
RERANK_PROVIDER=local
RERANK_BASE_URL=
RERANK_API_KEY=
RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

## API

- `POST /api/documents/upload` 上传并入库
- `GET /api/documents` 查看文档
- `POST /api/documents/{document_id}/reindex` 重建单个文档的向量索引
- `POST /api/chat` 提问，返回 answer、sources、latency_ms、message_id
- `POST /api/feedback` 反馈答案质量
- `GET /api/config` 查看配置
- `POST /api/config` 更新配置
- `GET /api/logs` 查看问答日志
- `POST /api/evaluate` 运行评估集，返回关键词命中、来源覆盖、召回命中率、拒答率和耗时指标

## 测试和评估

```powershell
python -m unittest discover -s tests
python -c "import asyncio, json; from app.evaluation import run_evaluation; print(json.dumps(asyncio.run(run_evaluation()), ensure_ascii=False, indent=2))"
```

当前测试覆盖基础分词、评估指标、本地/远程重排序回退，以及配置、问答、上传、重建索引、反馈、评估等 API 路由。

## 演示问题

```text
报销差旅费用需要提供哪些材料？
公司年假折算规则是什么？
```

## 后续路线

1. 增加混合检索：向量召回 + BM25。
2. 接入真实重排序模型。
3. 持续完善评估指标：引用准确率、不同检索策略对比、按问题类型分组统计。
4. 增加权限、部门知识库隔离、审计日志。
