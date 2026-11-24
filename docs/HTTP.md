# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean` 或 `file=<CSV>` 三选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批和当前复核状态。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、业务证据和复核信息的 JSON。

## 客户编号切换迁移

迁移接口与维表批次使用独立的 `migrations` 表，互不影响。

`POST /api/migrations/preview` 接收同样的 `sample`/`file` 输入，返回完整迁移报告但不入库。

`POST /api/migrations/runs` 执行迁移批次，`run_id` 由规则版本与来源 SHA-256 决定：字节相同的来源重放返回同一批次，不重复入库、不改变归属。`GET /api/migrations/runs` 列出最近 50 批，`GET /api/migrations/runs/<id>` 查询单批。

`PATCH /api/migrations/runs/<id>` 接收 `revision`、`status`（`APPROVED`/`HELD`）和 `note`。未对平或存在隔离行时签发返回 409 `MIGRATION_NOT_BALANCED`，且不写入任何修改，旧版归属与待核依据原样保留。乐观锁冲突返回 409 `STALE_REVIEW`。

`GET /api/migrations/runs/<id>/evidence` 下载 `migration-evidence/1`：含新客户台账、已归客户交易、待核交易及其待核依据（原签约编号、命中行号、编号映射）、对账明细与复核信息。页面位于 `/migration`，样例在 `/migration/examples/<dirty|clean>`。
