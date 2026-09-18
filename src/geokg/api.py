"""GeoKG HTTP 管理面 —— 独立端口、只读公开、变更需鉴权。

## 为什么是独立服务

GeoKG 是**内容包**而不是 SDK 的一部分（依赖单向：``geokg → geonexus``）。
管理面沿用同一原则：``geokg-api`` 起自己的进程和端口，SDK 的 Web 服务
不需要知道 GeoKG 存在；平台 Web（portal）以**客户端**身份调用这里的接口。

## 分层：本模块只做协议，不做逻辑

::

    sources.py   数据
        ↓
    admin.py     逻辑（返回纯 dict）
        ↓
    cli.py      表现：人看的表格        ← 同一批 dict
    api.py      表现：HTTP/JSON         ← 同一批 dict

所以本模块**没有一行业务逻辑**：路由参数校验之后直接调用 ``admin.*``。
CLI 与 HTTP 因此不可能给出不一致的答案。

## 鉴权：只读放开，变更**失败关闭**

``GET`` 全部免鉴权——它们只读仓库内已随包分发的参考数据，不含机密。
``POST`` 复用 SDK 的 :class:`~geonexus.web.auth.APIKeyAuth`（``X-API-Key``），
键从 ``GEOKG_API_KEYS``（逗号分隔）读取。

⚠️ 这里有一处**刻意偏离 SDK 默认**：``APIKeyAuth`` 在键集为空时**放行**
（SDK 里真正的门是 JWT，API key 只是转发凭据）。但本服务的变更接口会
执行子进程、覆写数据文件——放行等于把写权限敞开给整个网段。因此本模块
在键集为空时**拒绝**变更请求（503），而不是放行。宁可运维发现"变更不可
用"，也不要静默地"变更人人可用"。

## 长任务

``refresh`` / ``build`` 交给 SDK 的 :class:`~geonexus.web.tasks.TaskManager`
在线程池里跑，立即返回 ``202`` + ``task_id``。随后：

* ``GET  /tasks/{id}``        轮询状态
* ``GET  /tasks/{id}/events`` SSE 增量推送（仅变化时发帧 + 心跳注释）
* ``POST /tasks/{id}/cancel`` 协作式取消

取消是**协作式**的：``refresh`` 只在数据集之间检查是否取消（生成脚本是
子进程，杀不掉），所以取消的语义是"当前这个刷完就停，不再开下一个"。
任务状态只存内存——进程重启后线程池已死，把旧记录读回来说"running"
只会误导，所以不落盘。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from geonexus.web.auth import require_api_key
from geonexus.web.tasks import (
    CANCELLED,
    DONE,
    FAILED,
    TaskManager,
    TaskNotCancellableError,
    TaskNotFoundError,
)
from pydantic import BaseModel, Field

from . import admin
from .sources import BY_ID, DATASET_VERSION

#: 路由前缀：显式版本号，平台 Web 可据此做兼容判断
API_PREFIX = "/api/v1/geokg"

#: 独立端口默认值（SDK Web 用 8787/8790，GeoKG 避让）
DEFAULT_PORT = 8788

#: 默认只监听回环：变更接口虽要鉴权，但没理由默认对外
DEFAULT_HOST = "127.0.0.1"

ENV_KEYS = "GEOKG_API_KEYS"
ENV_HOST = "GEOKG_HOST"
ENV_PORT = "GEOKG_PORT"

TERMINAL = (DONE, FAILED, CANCELLED)

#: 摄入支持的监测层级（HTTP 层先校验，避免让用户等一个深层的报错）
VALID_LEVELS = ("country", "admin1")

#: 图谱视图页面（单文件，无构建步骤、无 CDN，离线可用）
UI_FILE = Path(__file__).parent / "ui" / "index.html"


def _check_levels(level: list[str] | None) -> list[str] | None:
    """校验可重复的 ``level`` 查询参数，未知层级直接 400。"""
    if level is None:
        return None
    bad = [x for x in level if x not in VALID_LEVELS]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"未知监测层级 {bad}；可选 {list(VALID_LEVELS)}")
    return level


# --------------------------------------------------------------------------- #
# 请求体
# --------------------------------------------------------------------------- #
class RefreshRequest(BaseModel):
    """``POST /refresh`` 的请求体。"""

    dataset_id: str | None = Field(
        default=None, description="要刷新的数据集 id；与 all=true 二选一")
    all: bool = Field(default=False, description="刷新全部数据集")
    timeout: int = Field(default=1800, ge=30, le=7200,
                         description="单个数据集生成脚本的超时（秒）")


class BuildRequest(BaseModel):
    """``POST /build`` 的请求体。"""

    monitor_levels: list[str] | None = Field(
        default=None, description='监测层级，如 ["country","admin1"]；默认两者')
    include_monitoring: bool = Field(
        default=True, description="是否摄入监测单元（关掉可只量自编内容）")


# --------------------------------------------------------------------------- #
# 鉴权
# --------------------------------------------------------------------------- #
def resolve_keys(api_keys: set[str] | None = None) -> set[str]:
    """确定生效的 API key 集合：显式参数优先，其次 ``GEOKG_API_KEYS``。"""
    if api_keys is not None:
        return {k for k in api_keys if k}
    raw = os.environ.get(ENV_KEYS, "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def _gate(keys: set[str]) -> Any:
    """返回变更接口的依赖：有键则校验，无键则**失败关闭**。"""
    if keys:
        return require_api_key(keys)

    def _no_keys_configured() -> None:
        raise HTTPException(
            status_code=503,
            detail=(f"变更接口未启用：请设置 {ENV_KEYS}（逗号分隔的 API key）。"
                    "未配置时本服务拒绝任何写操作——只读接口不受影响。"),
        )

    return _no_keys_configured


# --------------------------------------------------------------------------- #
# 应用
# --------------------------------------------------------------------------- #
def create_app(api_keys: set[str] | None = None, *,
               max_workers: int | None = None) -> FastAPI:
    """构建 GeoKG 管理面应用。

    Args:
        api_keys: 允许调用变更接口的 key 集合；``None`` 时读 ``GEOKG_API_KEYS``。
        max_workers: 长任务线程池大小（默认交给 TaskManager 决定）。
    """
    keys = resolve_keys(api_keys)
    tasks = TaskManager(max_workers=max_workers)
    # 写操作串行化：两个刷新同时写同一个 TSV，或刷新中途建图读到半截文件，
    # 都会产生难以复现的坏数据。代价是变更不并发——对管理面完全可接受。
    write_lock = threading.Lock()
    inflight: dict[str, str] = {}
    inflight_lock = threading.Lock()
    gate = _gate(keys)

    # ---------------------------------------------------------------- 并发槽位
    def _claim(kind: str) -> str:
        """占用同类变更的槽位，返回预分配的任务 id。"""
        with inflight_lock:
            existing = inflight.get(kind)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"已有同类变更在进行中：{kind}（task {existing}）")
            tid = uuid.uuid4().hex
            inflight[kind] = tid
            return tid

    def _release(kind: str) -> None:
        with inflight_lock:
            inflight.pop(kind, None)

    def _inflight_view() -> dict[str, str]:
        with inflight_lock:
            return dict(inflight)

    def _schedule(kind: str, fn: Any, *args: Any, **kwargs: Any) -> str:
        """占位 → 提交 → 失败则释放占位。"""
        tid = _claim(kind)
        try:
            tasks.submit(fn, *args, task_id=tid, message=kind, **kwargs)
        except Exception:
            _release(kind)
            raise
        return tid

    # ---------------------------------------------------------------- 任务体
    def _refresh_worker(task_id: str, kind: str, dataset_id: str | None,
                        all_: bool, timeout: int) -> dict[str, Any]:
        def checkpoint(ev: dict[str, Any]) -> bool:
            frac = ev["index"] / max(1, ev["total"])
            tasks.update_progress(task_id, frac,
                                  f"抓取 {ev['dataset']}（{ev['index'] + 1}/{ev['total']}）")
            return not tasks.should_cancel(task_id)

        try:
            with write_lock:
                result = admin.refresh(dataset_id, all_=all_, timeout=timeout,
                                       checkpoint=checkpoint)
            if result["aborted"]:
                tasks.update_progress(task_id, 1.0, "已中止（不再开启下一个数据集）")
            else:
                tasks.update_progress(task_id, 1.0,
                                      "完成" if result["ok"] else "存在失败项")
            return result
        finally:
            _release(kind)

    def _build_worker(task_id: str, kind: str, monitor_levels: list[str] | None,
                      include_monitoring: bool) -> dict[str, Any]:
        try:
            tasks.update_progress(task_id, 0.1, "建图中…")
            with write_lock:
                result = admin.build(monitor_levels=monitor_levels,
                                     include_monitoring=include_monitoring)
            tasks.update_progress(task_id, 1.0,
                                  f"完成：{result['entities']} 实体 / {result['relations']} 关系")
            return result
        finally:
            _release(kind)

    # ---------------------------------------------------------------- 只读路由
    router = APIRouter(prefix=API_PREFIX, tags=["geokg"])

    @router.get("/health", summary="存活探针（不读数据文件）")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "geokg",
            "dataset_version": DATASET_VERSION,
            "writable": bool(keys),
            "inflight": _inflight_view(),
            # 易变的运行时状态只放这里；数据视图必须只由数据与查询决定
            "graph_cache": admin.graph_cache(),
        }

    @router.get("/status", summary="数据集状态、陈旧度告警与严格门禁")
    def get_status() -> dict[str, Any]:
        st = admin.status()
        # HTTP 层附加字段（不进入 admin.status 的契约）：客户端据此判断
        # 此刻读到的只读数据是否正被写入，避免把中间状态当成结论。
        st["inflight"] = _inflight_view()
        return st

    @router.get("/verify", summary="数据完整性与溯源门禁（离线）")
    def get_verify() -> dict[str, Any]:
        # 刻意不暴露 drift：漂移检查要联网、要跑生成脚本的 --check，属于
        # 运维批处理（`geokg verify --drift` / 定时 CI），不适合挂在 HTTP 上。
        return admin.verify(drift=False)

    @router.get("/licenses", summary="许可与署名汇总")
    def get_licenses() -> dict[str, Any]:
        return admin.licenses()

    @router.get("/counts", summary="计数口径与溯源审计（较重，会建图）")
    def get_counts(
        level: list[str] | None = Query(
            default=None, description='监测层级，可重复，如 ?level=country&level=admin1'),
    ) -> dict[str, Any]:
        return admin.counts(monitor_levels=_check_levels(level))

    # ------------------------------------------------------- 检索与图谱视图
    # 只读、免鉴权，与治理接口同一批 admin.* 逻辑层（因此 CLI 与 HTTP 不会给出
    # 不同答案）。这几个接口是 /ui 页面的后端，也可以被平台门户直接复用。
    @router.get("/search", summary="按关键词检索实体")
    def get_search(
        q: str = Query(default="", description="关键词；空串表示只做类型过滤"),
        type: list[str] | None = Query(default=None, description="实体类型，可重复"),
        limit: int = Query(default=20, ge=1, le=200, description="最多返回条数"),
        level: list[str] | None = Query(default=None, description="监测层级，可重复"),
    ) -> dict[str, Any]:
        return admin.search(
            q, types=type, limit=limit, monitor_levels=_check_levels(level),
            include_monitoring=True)

    @router.get("/entity/{entity_id}", summary="实体详情：属性、溯源与双向关系")
    def get_entity(
        entity_id: str,
        level: list[str] | None = Query(default=None, description="监测层级，可重复"),
    ) -> dict[str, Any]:
        result = admin.entity(entity_id, monitor_levels=_check_levels(level))
        if not result["found"]:
            raise HTTPException(
                status_code=404,
                detail=f"实体不存在: {entity_id}（可用 GET /search 先查 id）")
        return result

    @router.get("/graph", summary="以某实体为中心的子图（图谱视图数据）")
    def get_graph(
        focus: str = Query(description="中心实体 id；先用 /search 查 id"),
        depth: int = Query(default=2, ge=1, le=4, description="展开层数"),
        direction: str = Query(default="both", description="both / out / in"),
        limit: int = Query(default=200, ge=1, le=2000, description="节点数上限"),
        type: list[str] | None = Query(default=None, description="只保留这些实体类型"),
        level: list[str] | None = Query(default=None, description="监测层级，可重复"),
    ) -> dict[str, Any]:
        try:
            result = admin.subgraph(
                focus, depth=depth, direction=direction, limit=limit, types=type,
                monitor_levels=_check_levels(level), include_monitoring=True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # focus 是必填的身份而不是过滤器，所以查不到就是 404——与 /entity/{id}
        # 保持一致，免得同一个"实体不存在"在一处是 404、另一处是 200 空图。
        if not result["found"]:
            raise HTTPException(
                status_code=404,
                detail=f"实体不存在: {focus}（可用 GET /search 先查 id）")
        return result

    @router.get("/types", summary="实体类型清单与计数（检索界面的图例）")
    def get_types(
        level: list[str] | None = Query(default=None, description="监测层级，可重复"),
    ) -> dict[str, Any]:
        return admin.entity_types(monitor_levels=_check_levels(level))

    @router.get("/manifest", summary="数据清单（指纹 / 行数 / 取数日期）")
    def get_manifest() -> dict[str, Any]:
        return admin.manifest(write=False)

    @router.get("/version", summary="数据集版本与指纹（精简、可缓存）")
    def get_version() -> dict[str, Any]:
        m = admin.manifest()
        # 刻意不含"本次计算时间"：版本接口的响应必须只由数据状态决定，否则
        # 同一份数据的每次请求都不同，缓存 / 比对 / ETag 全部失效。
        return {
            "dataset_version": m["dataset_version"],
            "fingerprint": m["fingerprint"],
            "manifest_generated_at": m["stored_generated_at"],
            "files": len(m["files"]),
            "rows": sum(f["rows"] for f in m["files"].values()),
            "manifest_format": m["manifest_format"],
        }

    # ---------------------------------------------------------------- 变更路由
    @router.post("/manifest", dependencies=[Depends(gate)], status_code=200,
                 summary="重算并写回 data/manifest.json")
    def post_manifest() -> dict[str, Any]:
        with write_lock:
            return admin.manifest(write=True)

    @router.post("/refresh", dependencies=[Depends(gate)], status_code=202,
                 summary="重新生成数据文件（长任务）")
    def post_refresh(body: RefreshRequest) -> dict[str, Any]:
        if body.all and body.dataset_id:
            raise HTTPException(status_code=400,
                                detail="dataset_id 与 all=true 不能同时给出")
        if not body.all and not body.dataset_id:
            raise HTTPException(status_code=400,
                                detail="需给出 dataset_id 或 all=true")
        if body.dataset_id and body.dataset_id not in BY_ID:
            raise HTTPException(
                status_code=400,
                detail=f"未知数据集 {body.dataset_id!r}；可选 {sorted(BY_ID)}")
        kind = "refresh:*" if body.all else f"refresh:{body.dataset_id}"
        tid = _schedule(kind, _refresh_worker, kind,
                        body.dataset_id, body.all, body.timeout)
        return {"task_id": tid, "kind": kind, "status": "queued",
                "poll": f"{API_PREFIX}/tasks/{tid}",
                "events": f"{API_PREFIX}/tasks/{tid}/events"}

    @router.post("/build", dependencies=[Depends(gate)], status_code=202,
                 summary="按当前数据建图（长任务，不落盘）")
    def post_build(body: BuildRequest) -> dict[str, Any]:
        if body.monitor_levels is not None:
            bad = [x for x in body.monitor_levels if x not in VALID_LEVELS]
            if bad:
                raise HTTPException(
                    status_code=400,
                    detail=f"未知监测层级 {bad}；可选 {list(VALID_LEVELS)}")
        tid = _schedule("build", _build_worker, "build",
                        body.monitor_levels, body.include_monitoring)
        return {"task_id": tid, "kind": "build", "status": "queued",
                "poll": f"{API_PREFIX}/tasks/{tid}",
                "events": f"{API_PREFIX}/tasks/{tid}/events"}

    # ---------------------------------------------------------------- 任务路由
    @router.get("/tasks", dependencies=[Depends(gate)], summary="任务列表")
    def list_tasks() -> dict[str, Any]:
        return {"tasks": tasks.list(include_result=False),
                "inflight": _inflight_view()}

    @router.get("/tasks/{task_id}", dependencies=[Depends(gate)], summary="任务状态")
    def get_task(task_id: str) -> dict[str, Any]:
        try:
            return tasks.get(task_id, include_result=True)
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/tasks/{task_id}/cancel", dependencies=[Depends(gate)],
                 summary="协作式取消")
    def cancel_task(task_id: str) -> dict[str, Any]:
        try:
            return tasks.cancel(task_id)
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TaskNotCancellableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/tasks/{task_id}/events", dependencies=[Depends(gate)],
                summary="任务进度 SSE")
    def task_events(task_id: str) -> StreamingResponse:
        try:
            tasks.get(task_id, include_result=False)
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return StreamingResponse(
            _stream_events(tasks, task_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        yield
        # 先拒绝后续变更，再关线程池：否则 shutdown 期间的请求会拿到坏 id。
        with inflight_lock:
            inflight.clear()
        tasks.close()

    app = FastAPI(
        title="GeoKG 管理面",
        version=DATASET_VERSION,
        description=("GeoKG 数据治理与知识图谱 API。只读接口免鉴权；变更接口需 "
                     f"`X-API-Key`（{ENV_KEYS}），未配置时返回 503。\n\n"
                     "图谱视图（检索 + 子图可视化）在 [`/ui`](/ui)。"),
        lifespan=lifespan,
    )
    app.include_router(router)

    # ------------------------------------------------------------------ 视图页
    # 放在 /ui 而不是 API 前缀下：它是给人看的页面，不是 API。单独注册而不是
    # 挂到 router 上，免得出现 /api/v1/geokg/ui 这种别扭路径。
    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    def ui_page() -> HTMLResponse:
        if not UI_FILE.exists():
            raise HTTPException(
                status_code=500,
                detail=f"视图资源缺失: {UI_FILE}（重装本包以恢复）")
        return HTMLResponse(UI_FILE.read_text(encoding="utf-8"))

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        # 直接访问端口时给个去处，而不是 404
        return RedirectResponse(url="/ui")

    # 便于测试与平台 Web 直接取用同一个任务管理器
    app.state.tasks = tasks
    app.state.geokg_api_keys = keys
    return app


async def _stream_events(tasks: TaskManager, task_id: str) -> AsyncGenerator[str, None]:
    """任务进度 SSE：仅状态变化时发帧，空闲时发心跳注释。

    用 ``asyncio.sleep`` 而非 ``time.sleep``——后者会卡住事件循环，一个订阅者
    就能拖垮整个服务。心跳是为了让反代/浏览器不要把长时间无变化的连接掐掉。
    """
    previous = ""
    idle = 0
    while True:
        try:
            state = tasks.get(task_id, include_result=True)
        except TaskNotFoundError:
            break
        blob = json.dumps(state, ensure_ascii=False, sort_keys=True)
        if blob != previous:
            yield f"data: {blob}\n\n"
            previous = blob
            idle = 0
        if state["status"] in TERMINAL:
            break
        await asyncio.sleep(0.5)
        idle += 1
        if idle >= 30:  # ~15s 无变化
            yield ": keep-alive\n\n"
            idle = 0


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    """``geokg-api`` 命令入口。"""
    ap = argparse.ArgumentParser(
        prog="geokg-api",
        description="GeoKG 管理面 HTTP 服务（只读公开 / 变更需 API key）",
    )
    ap.add_argument("--host", default=os.environ.get(ENV_HOST, DEFAULT_HOST),
                    help=f"监听地址（默认 {DEFAULT_HOST}；环境变量 {ENV_HOST}）")
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get(ENV_PORT, DEFAULT_PORT)),
                    help=f"监听端口（默认 {DEFAULT_PORT}；环境变量 {ENV_PORT}）")
    ap.add_argument("--workers", type=int, default=None,
                    help="长任务线程池大小")
    ap.add_argument("--reload", action="store_true", help="开发热重载")
    args = ap.parse_args(argv)

    keys = resolve_keys()
    if not keys:
        print(f"⚠️  未设置 {ENV_KEYS}：变更接口（refresh/build/manifest 写回）"
              f"将返回 503，只读接口正常。", file=sys.stderr)
    if args.host not in ("127.0.0.1", "localhost", "::1") and not keys:
        print("⚠️  正在对外监听且未配置 API key —— 请确认这是有意的。",
              file=sys.stderr)

    import uvicorn

    app = create_app(keys, max_workers=args.workers)
    if args.reload:
        # reload 需要 import 字符串，让 uvicorn 能重新导入模块
        os.environ[ENV_KEYS] = ",".join(sorted(keys))
        uvicorn.run("geokg.api:create_app", factory=True,
                    host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
