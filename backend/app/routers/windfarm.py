"""风电场站接口：维护风电场站，覆盖并网投运、申请限功率、转入检修等动作。"""
from __future__ import annotations

import csv
import io
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.windfarm import LIST_FIELDS, WindfarmService

router = APIRouter(prefix="/api/windfarm", tags=["风电场站"])

service = WindfarmService()

# 角色通过 X-Operator-Role 传递，取值用 ASCII 枚举，避免中文 header 编码问题。
SUBMIT_ROLES = {"admin", "manager"}
ROLE_LABELS = {"admin": "管理员", "manager": "值班管理员", "viewer": "观察员"}


def require_submit_role(x_operator_role: str | None) -> None:
    role = (x_operator_role or "").strip().lower()
    if role and role not in SUBMIT_ROLES:
        label = ROLE_LABELS.get(role, role)
        raise HTTPException(status_code=403, detail=f"当前身份「{label}」无权登记风电场站，请联系值班管理员")


@router.get("", response_model=PageResult[dict])
def list_entries(
    code: str | None = Query(default=None, description="按场站编码检索"),
    name: str | None = Query(default=None, description="按场站名称检索"),
    region: str | None = Query(default=None, description="按所在区域检索"),
    keyword: str | None = Query(default=None, description="旧参数，按场站编码检索"),
    status: str | None = Query(default=None, description="在建、运行中、限功率、停运检修"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按场站编码、场站名称、所在区域与状态过滤风电场站列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        code=code, name=name, region=region, keyword=keyword, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def entry_stats() -> dict[str, Any]:
    """列表页统计卡：数字与台账同源，保证和总览入口的场站数量一致。"""
    return {"items": service.stats()}


@router.get("/export")
def export_entries(
    code: str | None = None,
    name: str | None = None,
    region: str | None = None,
    keyword: str | None = None,
    status: str | None = None,
) -> Response:
    """导出风电场站清单：按当前筛选条件导出全量 CSV，口径与列表一致。"""
    items, _ = service.list_entries(
        code=code, name=name, region=region, keyword=keyword, status=status, page=1, size=10000
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(LIST_FIELDS)
    for row in items:
        writer.writerow(["" if row.get(field) is None else row.get(field) for field in LIST_FIELDS])
    filename = quote("风电场站清单.csv")
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=windfarm.csv; filename*=UTF-8''{filename}"},
    )


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条风电场站明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"风电场站 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult, status_code=201)
def create_entry(
    payload: EntryPayload,
    x_operator_role: str | None = Header(default=None),
) -> ActionResult:
    """登记一条风电场站，缺字段时说明原因而不是静默丢弃。

    越权身份直接拦下；台账中已存在相同场站编码时按台账为准，重复提交只算一次。
    """
    require_submit_role(x_operator_role)
    entry, missing, duplicated = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if duplicated:
        return ActionResult(ok=True, message=f"场站编码已存在，已按台账记录返回，未重复登记", entry=entry)
    return ActionResult(ok=True, message="风电场站已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条风电场站执行并网投运、申请限功率、转入检修；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
