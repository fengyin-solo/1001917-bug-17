"""风电场站业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "windfarm"
LIST_FIELDS = ["场站编码", "场站名称", "所在区域", "装机容量", "并网日期", "运营单位", "海拔高度", "场站状态"]
REQUIRED_FIELDS = ["场站编码", "场站名称", "所在区域"]
STATUS_ORDER = ["在建", "运行中", "限功率", "停运检修"]
ACTION_RULES = {"并网投运": "运行中", "申请限功率": "限功率", "转入检修": "停运检修"}
NEGATIVE_ACTIONS = []


class WindfarmService:
    def list_entries(
        self,
        *,
        code: str | None = None,
        name: str | None = None,
        region: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """按场站编码、场站名称、所在区域与状态过滤；所有条件取交集。

        keyword 保留给旧调用方，口径与场站编码一致。统计、导出与列表共用这一份
        过滤逻辑，保证三处看到的是同一批台账记录。
        """
        rows = store.rows(MODULE)
        if code:
            needle = code.strip().lower()
            rows = [row for row in rows if needle in str(row.get("场站编码", "")).lower()]
        if name:
            needle = name.strip()
            rows = [row for row in rows if needle in str(row.get("场站名称", ""))]
        if region:
            needle = region.strip()
            rows = [row for row in rows if needle in str(row.get("所在区域", ""))]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("场站编码", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def stats(self) -> list[dict[str, Any]]:
        """汇总卡片直接从台账现算，避免和列表、总览入口各说各话。"""
        rows = store.rows(MODULE)
        capacity = 0.0
        for row in rows:
            try:
                capacity += float(str(row.get("装机容量") or "").strip())
            except ValueError:
                continue
        capacity_value: Any = int(capacity) if capacity.is_integer() else round(capacity, 2)
        return [
            {"label": "在运场站", "value": sum(1 for row in rows if row.get("status") == "运行中")},
            {"label": "装机容量", "value": capacity_value},
            {"label": "限功率场站", "value": sum(1 for row in rows if row.get("status") == "限功率")},
        ]

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记场站。台账中已有相同场站编码时直接返回台账记录，不重复落表。

        返回值第三项表示是否命中了台账已有记录（重复提交幂等）。
        """
        cleaned = {field: str(values.get(field) or "").strip() for field in REQUIRED_FIELDS}
        missing = [field for field in REQUIRED_FIELDS if not cleaned[field]]
        if missing:
            return None, missing, False
        rows = store.rows(MODULE)
        for existing in rows:
            if str(existing.get("场站编码") or "").strip() == cleaned["场站编码"]:
                return existing, [], True
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update(cleaned)
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
