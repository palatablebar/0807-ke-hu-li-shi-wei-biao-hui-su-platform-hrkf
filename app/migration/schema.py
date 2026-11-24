import re

from app.business import DomainIssue
from app.intake.numeric import quantity

# record: 源交易/映射的记录键；kind: mapping 或 transaction；
# customer: 本行登记的客户编号（mapping 行为旧编号，交易行为其登记编号）；
# mapped_customer: 仅 mapping 行使用，登记旧编号对应的新编号；
# cents: 仅交易行使用，金额（分）；note: 说明。
HEADER = (
    "record",
    "kind",
    "customer",
    "mapped_customer",
    "cents",
    "note",
)
KINDS = ("mapping", "transaction")
IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,35}"


def _identifier(value, field):
    text = value.strip()
    if not re.fullmatch(IDENTIFIER, text):
        raise DomainIssue("BAD_IDENTIFIER")
    return text


def record(values):
    if len(values) != len(HEADER):
        raise DomainIssue("COLUMN_COUNT")
    row = dict(zip(HEADER, values))
    row["record"] = _identifier(row["record"], "record")
    if row["kind"] not in KINDS:
        raise DomainIssue("UNKNOWN_KIND")
    row["customer"] = _identifier(row["customer"], "customer")
    if len(row["note"]) > 200:
        raise DomainIssue("NOTE_TOO_LONG")
    if row["kind"] == "mapping":
        row["mapped_customer"] = _identifier(row["mapped_customer"], "mapped_customer")
        row["cents"] = 0
    else:
        # 交易行不允许携带映射目标；编号自身身份由迁移映射在分区阶段解析。
        if row["mapped_customer"].strip():
            raise DomainIssue("MAPPING_FIELD_ON_TX")
        row["mapped_customer"] = ""
        row["cents"] = quantity(row["cents"])
    return row
