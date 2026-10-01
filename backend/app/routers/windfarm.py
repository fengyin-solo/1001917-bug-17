"""风电场站接口：维护风电场站，覆盖并网投运、申请限功率、转入检修等动作。"""
from __future__ import annotations

import csv
import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.windfarm import CODE_FIELD, WindfarmService

router = APIRouter(prefix="/api/windfarm", tags=["风电场站"])

service = WindfarmService()

LIST_FIELDS = ["场站编码", "场站名称", "所在区域", "装机容量", "并网日期", "运营单位", "海拔高度", "场站状态"]
STATUSES = ["在建", "运行中", "限功率", "停运检修"]
# HTTP 头值在 ASGI 层按 latin-1 解码，中文角色名直接放进头会变成乱码，
# 因此对外用 ASCII 令牌，这里再映射回中文角色。
ROLE_ALIASES = {
    "admin": "值班管理员",
    "supervisor": "运维主管",
    "值班管理员": "值班管理员",
    "运维主管": "运维主管",
}
SUBMIT_ROLES = {"值班管理员", "运维主管"}


def require_submit_role(x_operator_role: str | None = Header(default=None)) -> str:
    """登记、动作等提交类操作只对值班管理员/运维主管开放，其余身份一律拦下。"""
    role = ROLE_ALIASES.get((x_operator_role or "").strip())
    if role is None:
        raise HTTPException(status_code=403, detail="当前身份无权提交风电场站操作，请联系值班管理员")
    return role


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按场站编码检索"),
    region: str | None = Query(default=None, description="按所在区域检索"),
    status: str | None = Query(default=None, description="在建、运行中、限功率、停运检修"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按场站编码、所在区域与状态过滤风电场站列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, region=region, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


# 注意：/export 必须声明在 /{entry_id} 之前，否则固定路径会被当成 entry_id 匹配，
# int 转换失败直接 422，导出入口就会跳到报错页。
@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按场站编码检索"),
    region: str | None = Query(default=None, description="按所在区域检索"),
    status: str | None = Query(default=None, description="在建、运行中、限功率、停运检修"),
) -> StreamingResponse:
    """按当前过滤条件导出风电场站清单 CSV，文件内容与列表命中的记录一致。"""
    items, _ = service.list_entries(keyword=keyword, region=region, status=status, page=1, size=10000)

    buffer = io.StringIO()
    # 加 BOM，Excel 直接打开不会把中文读成乱码
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow(LIST_FIELDS)
    for item in items:
        writer.writerow([item.get(field, "") if item.get(field) is not None else "" for field in LIST_FIELDS])
    buffer.seek(0)

    filename = quote("风电场站清单.csv")
    headers = {"Content-Disposition": f"attachment; filename=windfarm.csv; filename*=UTF-8''{filename}"}
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条风电场站明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"风电场站 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, _role: str = Depends(require_submit_role)) -> ActionResult:
    """登记一条风电场站，缺字段时说明原因而不是静默丢弃。

    场站编码重复时以台账已有记录为准，重复提交只算一次，不会新增第二条。
    """
    entry, missing, duplicated = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if duplicated:
        return ActionResult(ok=True, message=f"场站编码「{entry.get(CODE_FIELD)}」已存在于台账，重复提交未重复登记", entry=entry)
    return ActionResult(ok=True, message="风电场站已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload, _role: str = Depends(require_submit_role)) -> ActionResult:
    """对单条风电场站执行并网投运、申请限功率、转入检修；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
