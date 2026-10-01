"""风电场站业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "windfarm"
CODE_FIELD = "场站编码"
NAME_FIELD = "场站名称"
REGION_FIELD = "所在区域"
REQUIRED_FIELDS = [CODE_FIELD, NAME_FIELD, REGION_FIELD]
STATUS_ORDER = ["在建", "运行中", "限功率", "停运检修"]
ACTION_RULES = {"并网投运": "运行中", "申请限功率": "限功率", "转入检修": "停运检修"}
NEGATIVE_ACTIONS = []


class WindfarmService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        region: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """按场站编码、所在区域做包含匹配，可叠加状态过滤。

        列表、导出走同一口径，保证两处拿到的数据始终一致。
        """
        rows = store.rows(MODULE)
        if keyword and keyword.strip():
            code = keyword.strip()
            rows = [row for row in rows if code in str(row.get(CODE_FIELD, ""))]
        if region and region.strip():
            area = region.strip()
            rows = [row for row in rows if area in str(row.get(REGION_FIELD, ""))]
        if status and status.strip():
            target = status.strip()
            rows = [row for row in rows if row.get("status") == target]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记场站。

        返回 (记录, 缺失字段, 是否命中已有台账)。场站编码是台账唯一键：重复提交
        （即使附带了冲突字段）只保留台账里原来的那一条，以台账为准，不新增记录。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        rows = store.rows(MODULE)
        code = str(values.get(CODE_FIELD) or "").strip()
        for row in rows:
            if str(row.get(CODE_FIELD, "")).strip() == code:
                return row, [], True
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: str(values.get(field) or "").strip() for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, [], False

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"风电场站 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于风电场站可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"风电场站已{action}"
