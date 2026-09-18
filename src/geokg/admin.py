"""GeoKG 管理面 —— 库 API（返回纯 dict，供 CLI 与未来的 Web 共用）。

## 分层约定

本模块是管理面的**逻辑层**：只做计算与读取，**不打印、不格式化**。
所有返回值都可 JSON 序列化，因此未来的平台 Web 管理面可以直接复用这些
函数，无需改动业务逻辑——这正是"CLI 先行、Web 复用"的落地方式。

``cli.py`` 只负责把这里的 dict 渲染成人看的表格；HTTP 层同理。

## 三类能力

**只读（零副作用、零网络）** —— ``status`` / ``verify`` / ``licenses`` / ``counts``
**有副作用** —— ``manifest(write=True)`` / ``refresh`` / ``build``

只读路径刻意不碰网络：本机网络不稳，且 CI 里也应能离线跑门禁。
需要联网的漂移检查必须显式开 ``drift=True``。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .sources import DATA_DIR, DATASET_VERSION, DATASETS, Dataset, get

#: 数据清单（记录每个数据文件的指纹与取数日期，用于陈旧度与版本追溯）
MANIFEST_FILE = DATA_DIR / "manifest.json"

#: 清单格式版本（与数据集版本无关）
MANIFEST_FORMAT = 1


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _rows(path: Path) -> int:
    """数据行数（不含注释与空行）。"""
    if not path.exists():
        return 0
    n = 0
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        # L3 数据文件带一行列头（"source_id\tlevel\t..."），加载器会跳过它，
        # 计数也应一致，否则状态页会比实际多算 1 行。
        if ln.startswith("source_id\t"):
            continue
        n += 1
    return n


def _load_manifest() -> dict[str, Any]:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _age_days(iso: str) -> int | None:
    if not iso:
        return None
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return None
    return (date.today() - d).days


# --------------------------------------------------------------------------- #
# 只读：状态
# --------------------------------------------------------------------------- #
def dataset_status(ds: Dataset, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """单个数据集的状态（文件是否在、指纹是否变、是否陈旧）。"""
    mf = (manifest or _load_manifest()).get("files", {}).get(ds.id, {})
    p = ds.path
    exists = p.exists()
    cur_hash = _sha256(p) if exists else None
    rec_hash = mf.get("sha256")
    retrieved = mf.get("retrieved", "")
    age = _age_days(retrieved)
    stale = bool(
        exists and ds.staleness_days is not None
        and age is not None and age > ds.staleness_days
    )
    return {
        "id": ds.id,
        "file": ds.file,
        "exists": exists,
        "size_bytes": p.stat().st_size if exists else 0,
        "rows": _rows(p) if exists else 0,
        "sha256": cur_hash,
        "recorded_sha256": rec_hash,
        # 文件与清单不一致 = 数据变了但清单没重算（或从未生成清单）
        "fingerprint_match": bool(cur_hash and rec_hash and cur_hash == rec_hash),
        "retrieved": retrieved,
        "age_days": age,
        "staleness_days": ds.staleness_days,
        "stale": stale,
        "tier": ds.tier,
        "license": ds.license,
        "attribution": ds.attribution,
        "upstream": ds.upstream,
        "requires_network": ds.requires_network,
        "generator": ds.generator,
        "sources": list(ds.sources),
        "produces": list(ds.produces),
    }


def status() -> dict[str, Any]:
    """全部数据集的整体状态 + 陈旧度告警 + 溯源覆盖。"""
    mf = _load_manifest()
    items = [dataset_status(d, mf) for d in DATASETS]

    warnings: list[dict[str, Any]] = []
    for it in items:
        if not it["exists"]:
            warnings.append({"level": "error", "reason": "missing", "gate": True,
                             "dataset": it["id"],
                             "message": f"数据文件缺失: {it['file']}"})
        elif it["stale"]:
            warnings.append({
                "level": "warning", "reason": "stale", "gate": True,
                "dataset": it["id"],
                "message": (f"数据已 {it['age_days']} 天未更新"
                            f"（阈值 {it['staleness_days']} 天，上游 {it['upstream']}）"),
            })
        elif it["retrieved"] and not it["fingerprint_match"]:
            # 指纹漂移不是数据本身的健康问题，只是"改了数据没重算清单"的提醒，
            # 因此不参与严格门禁（gate=False）——修复方式是重算清单，不是去抓数。
            warnings.append({
                "level": "warning", "reason": "drift", "gate": False,
                "dataset": it["id"],
                "message": "文件指纹与清单不符——数据已改但清单未重算，"
                           "请运行 `geokg manifest --write`",
            })

    return {
        "dataset_version": mf.get("dataset_version", DATASET_VERSION),
        "manifest_generated_at": mf.get("generated_at", ""),
        "manifest_present": MANIFEST_FILE.exists(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "datasets": items,
        "counts": {
            "datasets": len(items),
            "present": sum(1 for i in items if i["exists"]),
            "stale": sum(1 for i in items if i["stale"]),
            "rows_total": sum(i["rows"] for i in items),
        },
        "warnings": warnings,
        # 严格门禁的唯一判据（CI 与 HTTP 门禁共用）。以前 CLI 靠中文子串
        # 匹配 "未更新" 来推断，措辞一改门禁就静默失效——这里改成结构化字段。
        "ok_strict": not any(w["gate"] for w in warnings),
    }


# --------------------------------------------------------------------------- #
# 只读：校验
# --------------------------------------------------------------------------- #
def verify(*, drift: bool = False, timeout: int = 300) -> dict[str, Any]:
    """校验数据完整性与溯源门禁。

    Args:
        drift: 是否额外跑生成脚本的 ``--check`` 检测**上游漂移**（需要联网，
            默认关闭——CI 与离线环境应只跑本地校验）。
    """
    checks: list[dict[str, Any]] = []

    # ① 文件存在 + 行数
    for ds in DATASETS:
        exists = ds.path.exists()
        checks.append({
            "name": f"数据文件存在: {ds.file}",
            "ok": exists,
            "detail": f"{_rows(ds.path)} 行" if exists else "缺失",
        })

    # ② 加载器能解析（schema 校验，比"文件在"更强）
    load_errors: list[str] = []
    for mod, fn, label in (
        ("reference_data", "load_countries", "国家表"),
        ("admin1", "load_admin1", "一级行政区"),
        ("satellites", "load_satellites", "卫星目录"),
        ("instruments", "load_instruments", "仪器目录"),
        ("sdg", "load_sdg", "SDG 框架"),
        ("ontology", "load_all_terms", "本体"),
        ("vocabulary", "load_vocabulary", "术语表"),
    ):
        try:
            m = __import__(f"geokg.{mod}", fromlist=[fn])
            getattr(m, fn)()
        except Exception as exc:  # noqa: BLE001 - 校验要报告任何解析失败
            load_errors.append(f"{label}: {type(exc).__name__}: {exc}")
    checks.append({
        "name": "数据文件可被加载器解析",
        "ok": not load_errors,
        "detail": "全部通过" if not load_errors else "; ".join(load_errors[:3]),
    })

    # ③ 溯源强制：每条实体都要带 origin/source/license/retrieved
    prov_detail = ""
    try:
        from geonexus.kg import KnowledgeGraph

        from .ingest import run_full_ingestion
        from .provenance import provenance_report

        kg = KnowledgeGraph("verify")
        run_full_ingestion(kg, include_monitoring=False)
        prov = provenance_report(kg)
        missing = len(prov["missing_fields"])
        ok = missing == 0
        prov_detail = (f"{prov['total']} 条实体，来源已核实 "
                       f"{prov['verified_count']}（{prov['verified_ratio']:.1%}）")
        if missing:
            prov_detail += f"，{missing} 条缺必需字段"
        checks.append({"name": "溯源字段强制检查", "ok": ok, "detail": prov_detail})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "溯源字段强制检查", "ok": False,
                       "detail": f"{type(exc).__name__}: {exc}"})

    # ④ 清单指纹（数据变了没重算清单）
    mf = _load_manifest()
    fp_bad = [
        ds.id for ds in DATASETS
        if ds.path.exists() and mf.get("files", {}).get(ds.id, {}).get("sha256")
        and _sha256(ds.path) != mf["files"][ds.id]["sha256"]
    ]
    checks.append({
        "name": "数据指纹与清单一致",
        "ok": not fp_bad,
        "detail": "一致" if not fp_bad else f"不一致: {', '.join(fp_bad)}（请重算清单）",
    })

    # ⑤ 上游漂移（可选，联网）
    drift_results: list[dict[str, Any]] = []
    if drift:
        for ds in DATASETS:
            gen = ds.generator_path
            if not gen.exists():
                drift_results.append({"id": ds.id, "status": "skip",
                                      "detail": f"生成脚本不存在: {ds.generator}"})
                continue
            try:
                r = subprocess.run(
                    [sys.executable, str(gen), "--check"],
                    capture_output=True, text=True, timeout=timeout, cwd=str(gen.parent),
                )
                drift_results.append({
                    "id": ds.id,
                    "status": "clean" if r.returncode == 0 else "drift",
                    "detail": (r.stdout or r.stderr).strip().splitlines()[-1][:120]
                              if (r.stdout or r.stderr).strip() else "",
                })
            except subprocess.TimeoutExpired:
                drift_results.append({"id": ds.id, "status": "timeout",
                                      "detail": f"超过 {timeout}s"})
        checks.append({
            "name": "上游漂移检查（联网）",
            "ok": all(d["status"] in ("clean", "skip") for d in drift_results),
            "detail": ", ".join(f"{d['id']}={d['status']}" for d in drift_results),
        })

    return {
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "drift": drift_results,
        "drift_requested": drift,
    }


# --------------------------------------------------------------------------- #
# 只读：许可
# --------------------------------------------------------------------------- #
def licenses() -> dict[str, Any]:
    """许可与署名汇总 —— 公开发布前必须过一眼。"""
    seen: dict[str, dict[str, Any]] = {}
    for ds in DATASETS:
        key = ds.license
        entry = seen.setdefault(key, {"license": key, "tier": ds.tier,
                                      "datasets": [], "attributions": []})
        entry["datasets"].append(ds.id)
        if ds.attribution not in entry["attributions"]:
            entry["attributions"].append(ds.attribution)

    # 自编内容单独说明，避免与外部数据集混为一谈
    authored = [ds.id for ds in DATASETS if "geokg-authored" in ds.sources]
    return {
        "groups": list(seen.values()),
        "authored_note": (
            "含 GeoKG 自编内容（Apache-2.0）的数据集: "
            + ", ".join(authored) if authored else ""
        ),
        "requires_attribution": sorted({
            ds.attribution for ds in DATASETS
            if "geokg-authored" not in ds.sources and ds.attribution
        }),
    }


# --------------------------------------------------------------------------- #
# 只读：计数口径
# --------------------------------------------------------------------------- #
def counts(monitor_levels: list[str] | None = None) -> dict[str, Any]:
    """计数口径 + 溯源审计（复用既有实现）。"""
    from geonexus.kg import KnowledgeGraph

    from .ingest import run_full_ingestion
    from .provenance import counting_basis, provenance_report

    levels = ["country"] if monitor_levels is None else monitor_levels
    kg = KnowledgeGraph("counts")
    run_full_ingestion(kg, monitor_levels=levels,
                       include_monitoring=bool(levels))
    return {
        "monitor_levels": levels,
        "basis": counting_basis(kg),
        "provenance": provenance_report(kg),
    }


# --------------------------------------------------------------------------- #
# 只读：检索与子图（知识图谱视图的后端）
# --------------------------------------------------------------------------- #
# 图是**数据文件的函数**，不是状态：同一批文件必然建出同一张图。因此缓存按
# "数据文件的 (mtime_ns, size)" 失效，而不是按时间——数据一变键就变，既不需要
# TTL，也不可能读到过期图。
#
# 不用 manifest 指纹当键：那要哈希 9 个文件（实测 ~14 ms），而 os.stat 几乎免费。
# 指纹只在**真正建图时**算一次并随缓存存下，于是接口仍能回答"这张图对应哪个
# 数据集版本"，但每次请求不必重算。
#
# 注意：建图期间持有锁（admin1 层约 2 s）。这是有意的——宁可并发请求排队，
# 也不要为同一个键同时建两张图。
_GRAPH_CACHE: dict[tuple, dict[str, Any]] = {}
_GRAPH_LOCK = threading.Lock()

#: 取显示名时按顺序尝试的属性；取不到就退回实体 id
_NAME_KEYS = ("name", "title", "indicator_title", "fullname", "acronym", "label")

#: 溯源字段——这是 GeoKG 的立身之本，界面必须能直接展示
_PROVENANCE_KEYS = ("origin", "source", "source_tier", "license",
                    "retrieved", "attribution")


def _data_stamp() -> tuple[Any, ...]:
    """数据文件的 (mtime_ns, size) 快照：数据一变，这个元组就变。"""
    stamp = []
    for ds in DATASETS:
        try:
            st = ds.path.stat()
            stamp.append((ds.id, st.st_mtime_ns, st.st_size))
        except OSError:
            stamp.append((ds.id, 0, 0))
    return tuple(stamp)


def display_name(entity: Any) -> str:
    """实体的显示名：优先 name/title，取不到退回 id。

    ``KGEntity`` 的 ``labels`` 存的是**类型**标签（``['satellite']``、
    ``['monitoring','national','water']``），不是名字，所以 ``search_by_label``
    查不到 "Brazil"——人名/地名在 ``properties`` 里。
    """
    for key in _NAME_KEYS:
        value = entity.properties.get(key)
        if value:
            return str(value)
    return entity.id


def graph(monitor_levels: list[str] | None = None,
          include_monitoring: bool = True) -> dict[str, Any]:
    """取得（必要时构建并缓存）当前数据对应的图。

    Returns:
        缓存条目：``graph`` 是 :class:`KnowledgeGraph`，另含 stamp、数据集版本
        与指纹、实体/关系数、建图耗时、命中次数。
    """
    levels = ["country"] if monitor_levels is None else list(monitor_levels)
    key = (tuple(levels), bool(include_monitoring))
    stamp = _data_stamp()
    with _GRAPH_LOCK:
        entry = _GRAPH_CACHE.get(key)
        if entry is not None and entry["stamp"] == stamp:
            entry["hits"] += 1
            return entry

        from geonexus.kg import KnowledgeGraph

        from .ingest import run_full_ingestion

        started = time.time()
        kg = KnowledgeGraph("geokg")
        run_full_ingestion(kg, monitor_levels=levels,
                          include_monitoring=include_monitoring)
        mf = manifest()
        entry = {
            "graph": kg,
            "stamp": stamp,
            "monitor_levels": levels,
            "include_monitoring": bool(include_monitoring),
            "dataset_version": mf["dataset_version"],
            "fingerprint": mf["fingerprint"],
            "entities": kg.entity_count(),
            "relations": kg.relation_count(),
            "seconds": round(time.time() - started, 2),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "hits": 0,
        }
        _GRAPH_CACHE[key] = entry
        return entry


def _dataset_view(entry: dict[str, Any]) -> dict[str, Any]:
    """缓存条目里可以对外暴露的部分（不含图对象本身）。

    **刻意不含命中计数**：那会让同一个查询每次响应都不同，破坏"响应只由数据
    与查询决定"这一条（``/version`` 也遵循同一原则）。缓存诊断走
    :func:`graph_cache`，挂在 ``/health`` 上。
    """
    return {
        "dataset_version": entry["dataset_version"],
        "fingerprint": entry["fingerprint"],
        "monitor_levels": entry["monitor_levels"],
        "entities": entry["entities"],
        "relations": entry["relations"],
        "built_at": entry["built_at"],
        "build_seconds": entry["seconds"],
    }


def graph_cache() -> dict[str, Any]:
    """图缓存诊断：有哪些层级的图被缓存、各自建了多久、命中多少次。"""
    with _GRAPH_LOCK:
        return {
            "entries": [
                {
                    "monitor_levels": entry["monitor_levels"],
                    "include_monitoring": entry["include_monitoring"],
                    "entities": entry["entities"],
                    "relations": entry["relations"],
                    "built_at": entry["built_at"],
                    "build_seconds": entry["seconds"],
                    "hits": entry["hits"],
                }
                for entry in _GRAPH_CACHE.values()
            ],
            "cached": len(_GRAPH_CACHE),
        }


def _node_view(entity: Any) -> dict[str, Any]:
    """图视图里的紧凑节点：详情另走 ``entity()``，避免子图响应膨胀。"""
    return {
        "id": entity.id,
        "type": entity.type,
        "name": display_name(entity),
        "labels": list(entity.labels),
    }


def _entity_view(entity: Any) -> dict[str, Any]:
    """详情视图：紧凑节点 + 溯源字段 + 全量属性。"""
    view = _node_view(entity)
    view["provenance"] = {
        k: entity.properties[k] for k in _PROVENANCE_KEYS
        if entity.properties.get(k)
    }
    view["properties"] = dict(entity.properties)
    return view


def _score(entity: Any, query: str) -> int:
    """检索打分：id 精确 > 名字精确 > 前缀 > 子串 > 属性命中。

    只按 id 排序会让 ``country.BRA`` 落到一堆 ``*brazil*`` 卫星后面，所以名字
    与 id 分开给权，且精确匹配优先。
    """
    name = display_name(entity).lower()
    eid = entity.id.lower()
    if eid == query:
        return 100
    if name == query:
        return 90
    if eid.startswith(query) or name.startswith(query):
        return 70
    if query in eid or query in name:
        return 50
    if any(query in str(v).lower() for v in entity.properties.values()):
        return 30
    if query in " ".join(entity.labels).lower():
        return 10
    return 0


def search(query: str, *, types: list[str] | None = None, limit: int = 20,
           monitor_levels: list[str] | None = None,
           include_monitoring: bool = True) -> dict[str, Any]:
    """按关键词检索实体（图谱视图的搜索框后端）。

    Args:
        query: 关键词；大小写不敏感，空串表示只做类型过滤。
        types: 只返回这些实体类型的命中。
        limit: 最多返回多少条（按分数降序）。
    """
    entry = graph(monitor_levels, include_monitoring)
    kg = entry["graph"]
    needle = (query or "").strip().lower()
    wanted = set(types) if types else None

    hits: list[tuple[int, Any]] = []
    for entity in kg.entities():
        if wanted is not None and entity.type not in wanted:
            continue
        score = 100 if not needle else _score(entity, needle)
        if score:
            hits.append((score, entity))

    hits.sort(key=lambda pair: (-pair[0], pair[1].type, pair[1].id))
    top = hits[:max(0, limit)]
    return {
        "query": query,
        "count": len(hits),
        "returned": len(top),
        "truncated": len(hits) > len(top),
        "types": sorted(wanted) if wanted else None,
        "results": [{**_entity_view(e), "score": s} for s, e in top],
        "dataset": _dataset_view(entry),
    }


def entity(entity_id: str, *, monitor_levels: list[str] | None = None,
           include_monitoring: bool = True) -> dict[str, Any]:
    """单个实体的详情：属性、溯源，以及**两个方向**的关系。

    出边与入边必须分开给：领域图里大量边指向宿主（监测单元 → 国家、行政区 →
    国家），只看 ``neighbors()`` 会让国家节点看起来几乎是孤立的。
    """
    entry = graph(monitor_levels, include_monitoring)
    kg = entry["graph"]
    found = kg.get_entity(entity_id)
    if found is None:
        return {"found": False, "id": entity_id, "dataset": _dataset_view(entry)}
    return {
        "found": True,
        "entity": _entity_view(found),
        "out": [{"relation": rel.relation, "entity": _node_view(other)}
                for other, rel in kg.neighbors(entity_id)],
        "in": [{"relation": rel.relation, "entity": _node_view(other)}
               for other, rel in kg.incoming(entity_id)],
        "dataset": _dataset_view(entry),
    }


def entity_types(monitor_levels: list[str] | None = None,
                 include_monitoring: bool = True) -> dict[str, Any]:
    """实体类型清单与计数——给检索界面做筛选与图例。"""
    entry = graph(monitor_levels, include_monitoring)
    kg = entry["graph"]
    counts: dict[str, int] = {}
    sample: dict[str, str] = {}
    for e in kg.entities():
        counts[e.type] = counts.get(e.type, 0) + 1
        sample.setdefault(e.type, display_name(e))
    return {
        "count": len(counts),
        "types": [
            {"type": t, "entities": counts[t], "example": sample[t]}
            for t in sorted(counts, key=lambda t: (-counts[t], t))
        ],
        "relations": sorted({r.relation for r in kg.relations()}),
        "dataset": _dataset_view(entry),
    }


def subgraph(focus: str, *, depth: int = 2, direction: str = "both",
             limit: int = 200, types: list[str] | None = None,
             monitor_levels: list[str] | None = None,
             include_monitoring: bool = True) -> dict[str, Any]:
    """以 ``focus`` 为中心做 BFS，返回可直接渲染的子图。

    不做力导向布局：按 BFS 层级（``depth`` 字段）分层摆放既简单又**更有信息量**
    ——"离这个实体一跳/两跳"是读者真正关心的，而力导向图的距离没有语义。
    渲染端按 depth 画同心环即可。

    Args:
        depth: 展开层数（1 = 只看直接邻居）。
        direction: ``out`` / ``in`` / ``both``。
        limit: 节点数上限；超出时截断并置 ``truncated``。
        types: 只保留这些类型的节点（focus 本身始终保留）。
    """
    if direction not in ("out", "in", "both"):
        raise ValueError(f"direction 必须是 out/in/both，收到 {direction!r}")

    entry = graph(monitor_levels, include_monitoring)
    kg = entry["graph"]
    root = kg.get_entity(focus)
    if root is None:
        return {"found": False, "focus": focus, "nodes": [], "edges": [],
                "dataset": _dataset_view(entry)}

    wanted = set(types) if types else None

    def incident(node_id: str) -> list[tuple[Any, Any]]:
        pairs: list[tuple[Any, Any]] = []
        if direction in ("out", "both"):
            pairs.extend(kg.neighbors(node_id))
        if direction in ("in", "both"):
            pairs.extend(kg.incoming(node_id))
        return pairs

    depth_of: dict[str, int] = {focus: 0}
    allowed = {focus}
    edges: dict[tuple[str, str, str], Any] = {}
    queue = deque([(focus, 0)])
    truncated = False

    while queue:
        node_id, d = queue.popleft()
        if d >= depth:
            continue
        for other, rel in incident(node_id):
            edges.setdefault((rel.source_id, rel.target_id, rel.relation), rel)
            if other.id in depth_of:
                continue
            if wanted is not None and other.type not in wanted:
                continue
            if len(allowed) >= limit:
                truncated = True
                continue
            depth_of[other.id] = d + 1
            allowed.add(other.id)
            queue.append((other.id, d + 1))

    # 只保留两端都在子图里的边，否则会出现悬空连线
    kept = [rel for (s, t, _), rel in edges.items() if s in allowed and t in allowed]
    by_type: dict[str, int] = {}
    for eid in allowed:
        node = kg.get_entity(eid)
        if node is not None:
            by_type[node.type] = by_type.get(node.type, 0) + 1

    return {
        "found": True,
        "focus": focus,
        "depth": depth,
        "direction": direction,
        "truncated": truncated,
        "limit": limit,
        "nodes": [
            {**_node_view(kg.get_entity(eid)), "depth": depth_of[eid]}
            for eid in sorted(allowed, key=lambda i: (depth_of[i], i))
            if kg.get_entity(eid) is not None
        ],
        "edges": [
            {"source": rel.source_id, "target": rel.target_id,
             "relation": rel.relation}
            for rel in kept
        ],
        "by_type": by_type,
        "max_depth": max(depth_of.values(), default=0),
        "dataset": _dataset_view(entry),
    }


# --------------------------------------------------------------------------- #
# 版本与清单
# --------------------------------------------------------------------------- #
def manifest(*, write: bool = False) -> dict[str, Any]:
    """数据清单：每个文件的指纹、行数、取数日期 → 数据集版本指纹。

    ``write=True`` 时写回 ``data/manifest.json``（有副作用）。
    ``retrieved`` 保留清单里已有的日期，新文件才记今天——否则每次重算都会
    把"取数日期"刷成今天，陈旧度告警就永远不触发。

    两个时间字段分工明确，别混用：

    * ``generated_at`` —— **本次计算**的时间（每次都不同）；
    * ``stored_generated_at`` —— **磁盘上清单**的生成时间（``write=False``
      时才是"这份数据是什么时候定版的"）。

    只想要一个稳定的版本标识时，用 ``fingerprint`` 或
    ``stored_generated_at``；拿 ``generated_at`` 当版本时间会得到"永远刚刚生成"。
    """
    stored = _load_manifest()
    old = stored.get("files", {})
    today = date.today().isoformat()
    files: dict[str, Any] = {}
    for ds in DATASETS:
        p = ds.path
        prev = old.get(ds.id, {})
        files[ds.id] = {
            "file": ds.file,
            "sha256": _sha256(p) if p.exists() else None,
            "rows": _rows(p) if p.exists() else 0,
            "size_bytes": p.stat().st_size if p.exists() else 0,
            "retrieved": prev.get("retrieved") or today,
            "tier": ds.tier,
            "license": ds.license,
            "upstream": ds.upstream,
            "sources": list(ds.sources),
        }

    # 数据集指纹：对所有文件 sha256 排序后求哈希 → 可复现的版本标识
    digest = hashlib.sha256(
        json.dumps({k: v["sha256"] for k, v in sorted(files.items())},
                   sort_keys=True).encode()
    ).hexdigest()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = {
        "manifest_format": MANIFEST_FORMAT,
        "dataset_version": DATASET_VERSION,
        "generated_at": now,
        # 要写回时，"磁盘上的清单"就是这份——两个字段取同一个值，保证
        # 落盘后的文件自洽（否则存进去的 stored_generated_at 永远是上一版的时间）。
        "stored_generated_at": now if write else stored.get("generated_at", ""),
        "fingerprint": digest,
        "files": files,
    }
    if write:
        MANIFEST_FILE.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
# 有副作用：刷新
# --------------------------------------------------------------------------- #
def refresh(dataset_id: str | None = None, *, all_: bool = False,
            timeout: int = 1800,
            checkpoint: Callable[[dict[str, Any]], bool] | None = None) -> dict[str, Any]:
    """重新生成数据文件（联网抓取或离线转录），随后重算清单。

    一次只允许刷一个数据集或全部——避免"忘了刷某个"却以为已是最新。

    Args:
        checkpoint: 可选的**逐数据集**回调，在抓取每个数据集**之前**调用，
            收到 ``{"dataset", "index", "total", "done", "ok"}``。返回
            ``False`` 则不再开始下一个数据集（当前子进程仍会跑完——子进程
            不可中断，这是"停止后续"而不是"立即杀死"）。CLI 不传，HTTP
            管理面用它同时实现进度上报与协作式取消。
    """
    if all_:
        targets = list(DATASETS)
    elif dataset_id:
        targets = [get(dataset_id)]
    else:
        raise ValueError("需指定 dataset_id 或 all_=True")

    results: list[dict[str, Any]] = []
    aborted = False
    for index, ds in enumerate(targets):
        if checkpoint is not None and not checkpoint({
            "dataset": ds.id, "index": index, "total": len(targets),
            "done": list(results), "ok": all(r["ok"] for r in results),
        }):
            aborted = True
            break
        gen = ds.generator_path
        if not gen.exists():
            results.append({"id": ds.id, "ok": False,
                            "detail": f"生成脚本不存在: {ds.generator}"})
            continue
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, "-u", str(gen)],
                               capture_output=True, text=True,
                               timeout=timeout, cwd=str(gen.parent))
            ok = r.returncode == 0
            tail = (r.stdout or r.stderr).strip().splitlines()
            results.append({"id": ds.id, "ok": ok, "seconds": round(time.time() - t0, 1),
                            "detail": tail[-1][:120] if tail else ""})
        except subprocess.TimeoutExpired:
            results.append({"id": ds.id, "ok": False,
                            "detail": f"超时（>{timeout}s）"})

    ok_all = bool(results) and all(r["ok"] for r in results)
    # 只有**整套成功**才重算并写回清单。中止（半个批次刷完）或有失败项时：
    # 写清单会把没刷新的部分一并登记成"当前版本"；而只算不写又会返回一个与
    # 磁盘不符的指纹。所以这两种情况统一返回 manifest=None（= 清单未变）。
    mf = manifest(write=True) if (ok_all and not aborted) else None
    return {"results": results, "ok": ok_all, "aborted": aborted,
            "manifest": {"fingerprint": mf["fingerprint"],
                         "dataset_version": mf["dataset_version"]} if mf else None}


# --------------------------------------------------------------------------- #
# 有副作用：建图
# --------------------------------------------------------------------------- #
def build(*, monitor_levels: list[str] | None = None,
          include_monitoring: bool = True) -> dict[str, Any]:
    """按当前数据文件构建知识图谱，返回统计（不落盘）。"""
    from geonexus.kg import KnowledgeGraph

    from .ingest import run_full_ingestion
    from .provenance import provenance_report

    kg = KnowledgeGraph("geokg")
    levels = ["country", "admin1"] if monitor_levels is None else monitor_levels
    t0 = time.time()
    run_full_ingestion(kg, monitor_levels=levels, include_monitoring=include_monitoring)
    prov = provenance_report(kg)
    return {
        "entities": kg.entity_count(),
        "relations": kg.relation_count(),
        "by_type": kg.stats()["by_type"],
        "seconds": round(time.time() - t0, 2),
        "monitor_levels": levels,
        "provenance": {"verified": prov["verified_count"],
                       "total": prov["total"],
                       "ratio": prov["verified_ratio"]},
    }
