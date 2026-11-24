from collections import Counter

from app.migration.service import inspect

# 迁移判定状态：
# - MIGRATED     只在旧签约编号登记，按映射改挂到新客户；
# - NEW_DIRECT   只在新编号登记，直接归属新客户；
# - PENDING      新旧编号都能命中，禁止改挂，保留待核与待核依据；
# - UNMAPPED_ID  登记编号不在任何映射身份内，无法判定归属，隔离；
# - AMBIGUOUS    同一交易命中多个不同客户身份，隔离。
MIGRATED = "MIGRATED"
NEW_DIRECT = "NEW_DIRECT"
PENDING_REVIEW = "PENDING_REVIEW"
UNMAPPED = "UNMAPPED_ID"
AMBIGUOUS = "AMBIGUOUS_CUSTOMER"


def build_identity(mappings):
    """返回 (old->(new,line))、身份集合与需要隔离的坏映射。"""
    rejects, forward = [], {}
    mapping = {row["customer"]: row["mapped_customer"] for row in mappings}
    target_ids = set(mapping.values())
    for row in mappings:
        old, new = row["customer"], row["mapped_customer"]
        if old == new:
            rejects.append((row["line"], row["record"], old, "MAPPING_SELF"))
            continue
        # 新编号同时又是另一映射的旧编号（映射链）会让切换期身份不唯一，隔离待人工确认。
        if new in mapping or old in target_ids:
            rejects.append((row["line"], row["record"], old, "MAPPING_CHAIN"))
            continue
        forward[old] = (new, row["line"])
    identities = set(forward) | {new for new, _line in forward.values()}
    return forward, identities, rejects


def classify(intake):
    forward, identities, bad_mapping = build_identity(intake["mappings"])
    rejected = [
        dict(line=line, record=record, customer=customer, reason=reason)
        for line, record, customer, reason in bad_mapping
    ]
    attributed, pending, ledger = [], [], Counter()
    attributed_amount = pending_amount = blocked_amount = blocked_count = 0
    for key, item in sorted(intake["transactions"].items()):
        hit_lines = item["customers"]
        canonical = {
            customer: forward[customer][0] if customer in forward else customer
            for customer in hit_lines
        }
        unknown = [customer for customer in hit_lines if customer not in identities]
        distinct = set(canonical.values()) - set(unknown)
        if unknown:
            rejected.append(
                dict(
                    line=min(hit_lines.values()),
                    record=key,
                    customer=unknown[0],
                    reason=UNMAPPED,
                )
            )
            blocked_count += 1
            blocked_amount += item["cents"]
            continue
        if len(distinct) > 1:
            rejected.append(
                dict(
                    line=min(hit_lines.values()),
                    record=key,
                    customer=sorted(distinct)[0],
                    reason=AMBIGUOUS,
                )
            )
            blocked_count += 1
            blocked_amount += item["cents"]
            continue
        new_customer = next(iter(distinct))
        old_hits = sorted(customer for customer in hit_lines if customer in forward)
        new_hits = sorted(customer for customer in hit_lines if customer not in forward)
        common = {
            "record": key,
            "new_customer": new_customer,
            "old_customer": old_hits[0] if old_hits else None,
            "cents": item["cents"],
        }
        if old_hits and new_hits:
            # 新旧编号都能命中：不直接改挂，保留待核，并固化待核依据（命中行与映射）。
            pending.append(
                dict(
                    **common,
                    status=PENDING_REVIEW,
                    basis=dict(
                        old_refs=old_hits,
                        new_refs=new_hits,
                        hit_lines=dict(sorted(hit_lines.items())),
                        mapping={old_hits[0]: forward[old_hits[0]][0]},
                    ),
                )
            )
            pending_amount += item["cents"]
            continue
        status = MIGRATED if old_hits else NEW_DIRECT
        attributed.append(
            dict(**common, status=status, hit_lines=dict(sorted(hit_lines.items())))
        )
        ledger[new_customer] += item["cents"]
        attributed_amount += item["cents"]
    isolation = sorted(intake["isolation"] + rejected, key=lambda row: row["line"])
    return dict(
        mappings=[
            dict(old=old, new=new, line=line)
            for old, (new, line) in sorted(forward.items())
        ],
        attributed=attributed,
        pending=pending,
        isolation=isolation,
        ledger={customer: ledger[customer] for customer in sorted(ledger)},
        blocked_count=blocked_count,
        totals=dict(
            attributed_count=len(attributed),
            attributed_cents=attributed_amount,
            pending_count=len(pending),
            pending_cents=pending_amount,
            blocked_count=blocked_count,
            blocked_cents=blocked_amount,
            source_count=len(intake["transactions"]),
            source_cents=sum(item["cents"] for item in intake["transactions"].values()),
        ),
    )


def balance(intake, result):
    totals = result["totals"]
    # 行数守恒以采信阶段口径为准：分类阶段的隔离只是对已采信行的重新归类，不新增源行。
    accounted = (
        intake["accepted"]
        + intake["rejected"]
        + intake["blank"]
        + intake["repeated"]
        + intake["replay"]
    )
    line_conservation = accounted == intake["input"]
    count_conservation = (
        totals["source_count"]
        == totals["attributed_count"] + totals["pending_count"] + totals["blocked_count"]
    )
    cents_conservation = (
        totals["source_cents"]
        == totals["attributed_cents"]
        + totals["pending_cents"]
        + totals["blocked_cents"]
    )
    ledger_conservation = totals["attributed_cents"] == sum(result["ledger"].values())
    balanced = all(
        (line_conservation, count_conservation, cents_conservation, ledger_conservation)
    )
    signable = (
        balanced
        and not result["isolation"]
        and totals["source_count"] > 0
        and bool(result["mappings"])
    )
    return dict(
        input=intake["input"],
        accepted=intake["accepted"],
        isolated=len(result["isolation"]),
        ignored=intake["blank"] + intake["repeated"] + intake["replay"],
        replay=intake["replay"],
        accounted=accounted,
        line_conservation=line_conservation,
        count_conservation=count_conservation,
        cents_conservation=cents_conservation,
        ledger_conservation=ledger_conservation,
        source=dict(count=totals["source_count"], cents=totals["source_cents"]),
        attributed=dict(count=totals["attributed_count"], cents=totals["attributed_cents"]),
        pending=dict(count=totals["pending_count"], cents=totals["pending_cents"]),
        blocked=dict(count=totals["blocked_count"], cents=totals["blocked_cents"]),
        issues=dict(sorted(Counter(row["reason"] for row in result["isolation"]).items())),
        balanced=balanced,
        signable=signable,
    )


def run(data):
    intake = inspect(data)
    result = classify(intake)
    return dict(
        intake={
            key: value
            for key, value in intake.items()
            if key not in ("mappings", "transactions")
        },
        mappings=result["mappings"],
        attributed=result["attributed"],
        pending=result["pending"],
        isolation=result["isolation"],
        ledger=result["ledger"],
        totals=result["totals"],
        balance=balance(intake, result),
    )
