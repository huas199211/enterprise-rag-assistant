# Project: Enterprise RAG Assistant

FastAPI + Vue 3 RAG（检索增强生成）知识库问答系统。

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Qdrant
- **Frontend**: Vue 3 + Vite
- **LLM**: HuggingFace Transformers / Torch
- **DB**: PostgreSQL + Qdrant vector store
- **Test**: pytest

## Commands

### Backend
- `uvicorn app.main:app --reload` — 启动开发服务器
- `pytest` — 运行所有测试
- `pytest -x --ff` — 失败时停止，重排优先跑上次失败的
- `ruff format .` — 格式化代码
- `ruff check .` — 代码检查
- `mypy app/` — 类型检查
- `alembic upgrade head` — 执行数据库迁移
- `alembic revision --autogenerate -m "desc"` — 生成迁移

### Frontend
- `cd frontend && npm run dev` — 启动 Vue 前端
- `cd frontend && npm run build` — 构建前端

提交前运行：`ruff format . && ruff check . && mypy app/ && pytest`

## Architecture

### Backend
- `app/api/routes.py` — API 路由，不含业务逻辑
- `app/services/` — 业务逻辑层（chat、document、auth）
- `app/repositories/` — 数据访问层（documents、chunks、messages、feedback）
- `app/rag.py` — 核心 RAG 检索生成逻辑
- `app/vector_store.py` — Qdrant 向量存储操作
- `app/llm.py` — LLM 模型加载与推理
- `app/embeddings.py` — 向量嵌入生成
- `app/schemas.py` — Pydantic 请求/响应模型
- `app/models.py` — SQLAlchemy ORM 模型（在 repositories 中定义）
- `app/security.py` — 认证与权限
- `migrations/` — Alembic 迁移脚本
- `tests/` — pytest 测试

### Frontend
- `frontend/src/App.vue` — 主应用组件
- `frontend/src/main.js` — 入口文件
- `frontend/src/styles.css` — 全局样式

## Coding Conventions

### Python
- 所有函数签名标注类型提示
- f-strings 字符串格式化（不用 .format() 或 %）
- Pydantic 模型用于所有 API 输入/输出 - 不返回原始 ORM 对象
- SQLAlchemy 2.0 风格（用 `select()` 而非 `session.query()`）
- 自定义异常类，在 API 边界捕获并映射为 HTTP 状态码

### Vue 3
- 使用 Composition API + `<script setup>`
- 单文件组件（.vue）
- Vite 作为构建工具

## Do NOT

- 不添加未确认的依赖
- 不在路由处理函数中写业务逻辑
- 不提交 `.env` 文件、`__pycache__`、`.pytest_cache`、`node_modules`
- 不用 `except Exception:` 而不重新抛出或写明原因
- 不返回原始 ORM 对象到前端

## Available skills

- `/api-endpoint` — 脚手架：创建新 API 端点（路由 + Pydantic schema + 服务函数 + 测试）
