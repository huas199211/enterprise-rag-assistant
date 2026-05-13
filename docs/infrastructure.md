# 基础设施

本项目本地开发环境使用 Docker Compose 启动基础组件。

## 组件

| 组件 | 端口 | 用途 |
| --- | --- | --- |
| PostgreSQL | 5432 | 业务数据库，保存文档、会话、日志、反馈、评估结果 |
| Qdrant | 6333 | 向量数据库，保存 chunk embedding 和检索 payload |
| Adminer | 8080 | PostgreSQL 可视化管理页面 |

## 启动

```powershell
docker compose up -d
```

## 验证

```powershell
docker compose ps
docker exec rag-postgres pg_isready -U rag -d rag
Invoke-WebRequest http://127.0.0.1:6333/collections
```

## Adminer 登录

打开：

```text
http://127.0.0.1:8080
```

填写：

```text
System: PostgreSQL
Server: postgres
Username: rag
Password: rag_password
Database: rag
```

## 面试讲法

这个阶段的目标是把原型里的本地 SQLite 和 JSON 向量文件替换为企业常见的持久化组件：

- PostgreSQL 管理结构化业务数据。
- Qdrant 管理向量索引和相似度检索。
- Docker Compose 固定依赖版本，保证项目可以复现和演示。
