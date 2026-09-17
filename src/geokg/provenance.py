"""GeoKG 计数口径 —— 把"实体数"变成一个可复现、可审计的定义。

## 为什么需要这个模块

考核要求"GeoKG ≥2 万实体"，但"实体"从未定义。同一个图谱可以诚实地报告出
四个差了一个数量级的数字，取决于把什么算进去：

| 口径 | 实体数 | 含义 |
|------|--------|------|
| 基础策展 | 2,471 | 人工整理的参考表（SDG 框架、国家、卫星目录、概念） |
| + 系统性展开 | 8,327 | 加上星座成员、扩展行政区、扩展词汇 |
| + 国家级监测 | 14,736 | 加上「国家 × 监测指标」任务空间 |
| + 次国家级监测 | 116,236 | 加上「一级行政区 × 监测指标」任务空间 |

对一个正在评审的项目来说，报哪个数字不是文风问题：116,236 里 92.8% 是
交叉积的产物，抽查时会直接损伤可信度；而 8,327 只有考核线（2 万）的 41%。

## 本模块的做法

不靠文档解释，而是把**来源写进实体本身**（``properties["origin"]``），
由 :func:`counting_basis` 从数据算出各口径的规模。因此：

* 任何口径都能被独立复现（``python scripts/counting_basis.py``）；
* 新增实体若未被分类，会出现在 ``unclassified`` 里而不是被默认算作策展数据；
* 口径变化会立刻反映在数字上，不会静默漂移。

来源三类（见 :mod:`geokg.ingest`）：

``curated``
    人工整理的参考表。
``expanded``
    由策展表**系统性展开**——例如星座成员（Sentinel-2A/2B/2C）、扩展行政区、
    扩展词汇。每一行都可追溯到策展表的一行，但不是逐条人工核定的。
``derived``
    由交叉积/规则**派生**——``MonitoringUnit``（行政单元 × 指标）与
    ``DataRequirement``。它们表达的是"某国需要监测某指标"这一任务空间，
    本身不含任何观测值。
"""

from __future__ import annotations

from typing import Any

from .ingest import ORIGIN_CURATED, ORIGIN_DERIVED, ORIGIN_EXPANDED, ORIGINS

__all__ = [
    "ORIGIN_CURATED",
    "ORIGIN_DERIVED",
    "ORIGIN_EXPANDED",
    "ORIGINS",
    "TIER_DEFINITIONS",
    "counting_basis",
    "format_report",
]

#: 各口径包含哪些来源。键即对外报告时使用的口径名。
TIER_DEFINITIONS: dict[str, tuple[str, ...]] = {
    "reference": (ORIGIN_CURATED,),
    "reference+expansion": (ORIGIN_CURATED, ORIGIN_EXPANDED),
    "reference+expansion+country": (ORIGIN_CURATED, ORIGIN_EXPANDED, ORIGIN_DERIVED),
}

UNCLASSIFIED = "unclassified"


def counting_basis(kg: Any) -> dict[str, Any]:
    """按来源统计图谱实体，返回可直接引用的口径报告。

    Args:
        kg: :class:`geonexus.kg.KnowledgeGraph` 实例。

    Returns:
        含 ``by_origin`` / ``by_type`` / ``tiers`` / ``unclassified`` 的字典。
        ``unclassified`` 非空说明有实体未经来源标记——应当视为错误，而不是
        默认并入策展数据。
    """
    by_origin: dict[str, int] = {o: 0 for o in ORIGINS}
    by_type: dict[str, int] = {}
    by_origin_type: dict[str, dict[str, int]] = {o: {} for o in ORIGINS}
    unclassified: list[str] = []

    for entity in kg.search("") if hasattr(kg, "search") else []:
        by_type[entity.type] = by_type.get(entity.type, 0) + 1
        origin = entity.properties.get("origin")
        if origin in by_origin:
            by_origin[origin] += 1
            by_origin_type[origin][entity.type] = (
                by_origin_type[origin].get(entity.type, 0) + 1
            )
        else:
            unclassified.append(entity.id)

    # 口径规模（累加制：可加性由来源互斥保证）
    tiers: dict[str, int] = {}
    for name, origins in TIER_DEFINITIONS.items():
        tiers[name] = sum(by_origin.get(o, 0) for o in origins)

    return {
        "total": sum(by_origin.values()) + len(unclassified),
        "by_origin": by_origin,
        "by_origin_type": by_origin_type,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "tiers": tiers,
        "unclassified": unclassified,
    }


def format_report(basis: dict[str, Any], *, title: str = "GeoKG 计数口径报告") -> str:
    """把 :func:`counting_basis` 的结果渲染成可粘进材料的文本。"""
    lines: list[str] = []
    add = lines.append

    add("=" * 74)
    add(f" {title}")
    add("=" * 74)
    add("")

    b = basis["by_origin"]
    add(f"  实体总数                {basis['total']:>9,}")
    add("")
    add("  按来源：")
    add(f"    curated   人工整理参考表      {b.get(ORIGIN_CURATED, 0):>9,}")
    add(f"    expanded  策展表系统性展开    {b.get(ORIGIN_EXPANDED, 0):>9,}")
    add(f"    derived   交叉积/规则派生     {b.get(ORIGIN_DERIVED, 0):>9,}")

    if basis["unclassified"]:
        add("")
        add(f"  ⚠️ unclassified {len(basis['unclassified']):,} 个实体未标记来源——"
            "计数不可信，请先修 ingest 的来源包装")

    add("")
    add("  按口径（累加）：")
    ref = basis["tiers"].get("reference", 0)
    refexp = basis["tiers"].get("reference+expansion", 0)
    allder = basis["tiers"].get("reference+expansion+country", 0)
    pct = (allder - refexp) / allder * 100 if allder else 0.0
    add(f"    ① 基础策展参考数据              {ref:>9,}")
    add(f"    ② ① + 系统性展开                {refexp:>9,}")
    add(f"    ③ ② + 国家级监测任务空间         {allder:>9,}")
    add(f"       （其中派生实体占 ③ 的 {pct:.1f}%）")

    add("")
    add("  按实体类型：")
    for t, n in basis["by_type"].items():
        add(f"    {t:<22}{n:>9,}")
    add("")
    return "\n".join(lines)
