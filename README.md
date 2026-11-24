# 客户历史维表回溯台

数仓维度维护员可在工作台上传来源 CSV，对照规则判断差异，签发合格批次或记录暂缓意见。

按交易时点关联客户维度，拒收区间重叠和历史断档。

## 启动

```sh
docker compose up --build -d --wait
```

打开 <http://localhost:18301>。页面预览带异常样例。选中阶段查看计算证据，选择可签发样例并执行批次，然后提交复核意见。

客户编号切换迁移台位于 <http://localhost:18301/migration>：新旧编号都命中的交易保留「待核」并固化原签约客户依据，不直接改挂；同一来源重跑幂等；源交易、已归客户、待核交易的笔数与金额四守恒对平且无隔离行才能签发，签发失败保留旧版归属与待核依据。

## 核验

```sh
docker compose exec -T app pytest -q
```

[输入字段](docs/DATA-DICTIONARY.md) · [阶段接口](docs/HTTP.md) · [操作步骤](docs/OPERATIONS.md) · [规则与测试](docs/DEPTH.md)
