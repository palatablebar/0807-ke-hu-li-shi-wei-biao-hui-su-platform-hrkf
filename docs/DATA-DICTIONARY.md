# 字段与业务定义

输入编码 UTF-8，允许 BOM。首行必须匹配样例列顺序。记录键和业务组保留原始字符串。`kind` 允许 version, transaction, expected。说明列 `note` 可以跨行，限制 200 字。

业务字段按 `start_day`、`end_day`、`segment`、`cents` 排列。数字接受非负整数、全角数字和完整千分位。空串、短横线、N/A、NULL 与未知为缺值。无关字段用 0 占位。

生效范围左闭右开。客户同一时段只允许一个生效版本。无法命中的交易单列明细且禁止发布，保留已经关联的金额。

`incoming.csv` 包含四个业务组，第二组提供不同边界，第三组触发业务拒收，第四组需要核对。另含重复表头、冲突记录、重复回放与错误列数。`ready.csv` 含可以签发的两个组。

## 客户迁移输入（`migration_*.csv`）

表头固定为 `record,kind,customer,mapped_customer,cents,note`，沿用 UTF-8/BOM、256 KiB 与 2000 行上限、标识符号与金额归一化规则。

- `kind=mapping`：`customer` 为旧签约编号，`mapped_customer` 为切换后的新编号，`cents` 置 0。自映射（`MAPPING_SELF`）与映射链/多目标（`MAPPING_CHAIN`）整组隔离。
- `kind=transaction`：`customer` 登记该笔交易当前使用的编号，`mapped_customer` 必须留空（`MAPPING_FIELD_ON_TX`），`cents` 为金额。

同一 `record` 是同一源交易。同编号同金额的副本记为重放（`replay`），只采信一条；同编号金额冲突或跨编号金额冲突记 `DUPLICATE_CONFLICT` 并整笔隔离。

归属判定：只命中旧编号的按映射改挂（`MIGRATED`），只命中新编号的直接归属（`NEW_DIRECT`）；新旧编号都命中的交易不直接改挂，记 `PENDING_REVIEW` 待核并保留依据（两侧编号、源行号、映射），不计入新客户台账。编号不在任何映射身份内记 `UNMAPPED_ID`，同一交易命中多个客户身份记 `AMBIGUOUS_CUSTOMER`，二者均隔离并禁止签发。

对账四守恒：行数守恒、源交易笔数 = 已归 + 待核 + 隔离、源金额 = 已归金额 + 待核金额 + 隔离金额、新客户台账金额合计 = 已归金额。守恒成立且无隔离行、存在映射与源交易时 `signable=true`。
