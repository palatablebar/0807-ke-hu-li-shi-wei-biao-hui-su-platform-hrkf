from flask import jsonify

LABELS = {
    "FILE_TOO_LARGE": "文件超过 256 KiB",
    "FILE_EMPTY": "文件没有内容",
    "FILE_BLANK": "文件只有空白",
    "HEADER_ONLY": "文件只有标题行",
    "HEADER_MISMATCH": "列名与字段字典不一致",
    "ENCODING_INVALID": "请使用 UTF-8 CSV",
    "CSV_MALFORMED": "CSV 引号或行格式异常",
    "ROW_LIMIT": "文件超过 2000 行",
    "FILE_REQUIRED": "请选择 CSV 文件",
    "RUN_NOT_FOUND": "批次不存在",
    "REVIEW_FIELDS": "请填写 3 至 200 字复核意见",
    "STALE_REVIEW": "批次已更新，请刷新",
    "RUN_FINALIZED": "批次已签发",
    "UNRESOLVED_ISSUES": "存在待处理差异",
    "SAMPLE_UNKNOWN": "样例不存在",
    "STAGE_UNKNOWN": "处理阶段不存在",
    "MIGRATION_NOT_FOUND": "迁移批次不存在",
    "MIGRATION_NOT_BALANCED": "迁移数量或金额未对平，或仍有待处理隔离行",
    "MAPPING_FIELD_ON_TX": "交易行不能携带映射目标编号",
    "MAPPING_CONFLICT": "同一映射记录存在冲突版本",
    "MAPPING_SELF": "旧编号与新编号相同，无法迁移",
    "MAPPING_CHAIN": "存在映射链或多重目标，身份不唯一",
    "UNMAPPED_ID": "登记编号不在迁移映射身份内",
    "AMBIGUOUS_CUSTOMER": "同一交易命中多个客户身份",
}


def response(error):
    code = error.code
    status = (
        404
        if code in {"RUN_NOT_FOUND", "SAMPLE_UNKNOWN", "STAGE_UNKNOWN", "MIGRATION_NOT_FOUND"}
        else (
            409
            if code
            in {
                "STALE_REVIEW",
                "RUN_FINALIZED",
                "UNRESOLVED_ISSUES",
                "MIGRATION_NOT_BALANCED",
            }
            else 413 if code == "FILE_TOO_LARGE" else 422
        )
    )
    return jsonify(code=code, message=LABELS.get(code, code)), status
