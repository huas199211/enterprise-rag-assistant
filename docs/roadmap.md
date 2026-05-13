# 企业级改造路线

## 已完成

- Docker Desktop 安装和验证。
- Docker Compose 启动 PostgreSQL、Qdrant、Adminer。
- 业务数据从 SQLite 迁移到 PostgreSQL。
- 向量存储从 JSON 文件迁移到 Qdrant。
- 增加 Alembic 迁移骨架和初始 schema。
- 增加文档处理状态和重建索引接口。
- 增加相似度阈值 `min_score` 和低相关拒答逻辑。

## 下一步

1. 拆分工程结构：`app/api`、`app/services`、`app/repositories`。
2. 增加混合检索：向量召回 + BM25。
3. 增加重排序模型接入。
4. 完善评估指标：召回命中率、引用准确率、拒答率、耗时。
5. 增加单元测试和 API 测试。
