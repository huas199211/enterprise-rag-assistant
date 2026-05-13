# 企业级改造路线

## 已完成

- Docker Desktop 安装和验证。
- Docker Compose 启动 PostgreSQL、Qdrant、Adminer。
- 业务数据从 SQLite 迁移到 PostgreSQL。
- 向量存储从 JSON 文件迁移到 Qdrant。
- 增加 Alembic 迁移骨架和初始 schema。
- 增加文档处理状态和重建索引接口。
- 增加相似度阈值 `min_score` 和低相关拒答逻辑。
- 增加混合检索：向量召回 + BM25。
- 增加重排序模块抽象，支持本地重排序和远程重排序接口。
- 增强评估指标：关键词命中、来源覆盖、召回命中率、拒答率、耗时。
- 增加基础单元测试。
- 拆分 API 路由层到 `app/api`。
- 增加 FastAPI 路由测试。

## 下一步

1. 继续拆分工程结构：`app/services`、`app/repositories`。
2. 接入真实远程重排序服务并做效果对比。
3. 完善引用准确率和按问题类型分组统计。
4. 增加需要 PostgreSQL 和 Qdrant 的集成测试。
5. 增加权限、部门知识库隔离和审计日志。
