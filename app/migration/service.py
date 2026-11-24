from collections import Counter, defaultdict
from csv import Error

from app.business import DomainIssue
from app.migration.reader import records
from app.migration.schema import HEADER, record as parse_record


def _issue(line, row, reason):
    return dict(line=line, record=row["record"], customer=row["customer"], reason=reason)


def _dedup_mappings(rows):
    """映射行按记录键去重：完全相同为重放，任一差异为映射冲突，冲突全行隔离。"""
    grouped = defaultdict(list)
    for line, row in rows:
        grouped[row["record"]].append((line, row))
    accepted, rejected, replay = [], [], 0
    for key, copies in grouped.items():
        first = copies[0][1]
        if any(row != first for _, row in copies[1:]):
            rejected.extend(_issue(line, row, "MAPPING_CONFLICT") for line, row in copies)
            continue
        accepted.append(dict(first, line=copies[0][0]))
        replay += len(copies) - 1
    return accepted, rejected, replay


def _dedup_transactions(rows):
    """同一源交易（record）可在多个客户编号下登记。

    - 同 record 同 customer 同金额的副本：重放，只保留一条，不重复入库；
    - 同 record 同 customer 金额不一致：数据冲突，整笔隔离；
    - 同 record 不同 customer 金额不一致：跨编号金额冲突，整笔隔离；
    - 同 record 不同 customer 金额一致：保留为该交易的多个编号命中（待分类）。
    """
    grouped = defaultdict(list)
    for line, row in rows:
        grouped[row["record"]].append((line, row))
    index, rejected, replay = {}, [], 0
    for key, copies in grouped.items():
        per_customer = defaultdict(list)
        for line, row in copies:
            per_customer[row["customer"]].append((line, row))
        customers, cents_seen, tainted = [], set(), False
        for customer, entries in per_customer.items():
            amounts = {row["cents"] for _, row in entries}
            if len(amounts) > 1:
                tainted = True
                rejected.extend(
                    _issue(line, row, "DUPLICATE_CONFLICT") for line, row in entries
                )
                continue
            canonical = entries[0][1]
            customers.append((customer, canonical["cents"], entries[0][0]))
            cents_seen.update(amounts)
            replay += len(entries) - 1
        if tainted or len(cents_seen) > 1:
            rejected.extend(
                dict(line=line, record=key, customer=customer, reason="DUPLICATE_CONFLICT")
                for customer, _cents, line in customers
            )
            continue
        index[key] = {
            "record": key,
            "cents": customers[0][1],
            "customers": {customer: line for customer, _cents, line in customers},
        }
    return index, rejected, replay


def inspect(data):
    counted = repeated = blanks = replay = 0
    schema_rejects = []
    mapping_rows, tx_rows = [], []
    try:
        for line, values in records(data):
            counted += 1
            if not any(v.strip() for v in values):
                blanks += 1
                continue
            if tuple(values) == HEADER:
                repeated += 1
                continue
            try:
                row = parse_record(values)
            except DomainIssue as error:
                schema_rejects.append(
                    dict(
                        line=line,
                        record=values[0][:36] if values else "",
                        customer=values[2][:36] if len(values) > 2 else "",
                        reason=error.code,
                    )
                )
                continue
            if row["kind"] == "mapping":
                mapping_rows.append((line, row))
            else:
                tx_rows.append((line, row))
    except Error as error:
        raise DomainIssue("CSV_MALFORMED") from error

    mappings, map_rejects, map_replay = _dedup_mappings(mapping_rows)
    transactions, tx_rejects, tx_replay = _dedup_transactions(tx_rows)
    replay += map_replay + tx_replay
    isolation = sorted(schema_rejects + map_rejects + tx_rejects, key=lambda r: r["line"])
    accepted = len(mappings) + sum(len(item["customers"]) for item in transactions.values())
    return dict(
        input=counted,
        accepted=accepted,
        repeated=repeated,
        blank=blanks,
        replay=replay,
        rejected=len(isolation),
        reasons=dict(Counter(row["reason"] for row in isolation)),
        isolation=isolation,
        mappings=mappings,
        transactions=transactions,
    )
