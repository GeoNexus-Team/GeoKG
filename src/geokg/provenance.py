"""GeoKG 溯源与计数口径 —— 让"数据从哪来"成为可强制检查的字段。

## 两个问题

**① 计数口径**：考核要求"GeoKG ≥2 万实体"，但"实体"从未定义。同一个图谱可以
诚实地报告出四个差一个数量级的数字，取决于把什么算进去。

**② 数据来源**：历史上 GeoKG 的数据没有 `source` / `license` / `retrieved` 字段，
导致两个后果——一是无法回答"这条数据凭什么可信"，二是**发现了合规问题**：
原 `reference_data.ADMIN1_REGIONS` 自述来自 GADM，而 GADM 许可禁止再分发。

## 本模块的做法

不靠文档解释，把**来源与口径都写进实体本身**：

* ``properties["origin"]``       — curated / expanded / derived（口径分层）
* ``properties["source"]``       — 稳定来源 id，或 ``"UNVERIFIED"``
* ``properties["license"]``      — 许可标识
* ``properties["retrieved"]``    — 取数日期（ISO）
* ``properties["source_tier"]``  — T1 规范 / T2 官方 / T3 学术共识 / T4 聚合

四个字段**必须存在**（:func:`check_required_fields` 会报错），因此新增数据
不可能再"忘记标来源"。未核实的数据必须显式写 ``UNVERIFIED``，
由 :func:`provenance_report` 统计并可在 CI 中作为门禁——
**不允许沉默地混入策展数据**。

来源分级：

T1
    规范/标准（定义即真理）：UN SDG 框架、ISO 3166、IOGP EPSG、OGC
T2
    官方机构：NASA/ESA/USGS、FAO、WMO、各国统计局
T3
    同行评议共识：Köppen-Geiger、WRB 土壤、已发表指数
T4
    聚合/社区：GeoNames、OSM、Wikidata——可用但质量不均
UNVERIFIED
    来源未核实，**不得对外引用**
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "AUTHORED_LICENSE",
    "DataSource",
    "ORIGINS",
    "ORIGIN_CURATED",
    "ORIGIN_DERIVED",
    "ORIGIN_EXPANDED",
    "REQUIRED_FIELDS",
    "SOURCES",
    "TIER_DEFINITIONS",
    "UNKNOWN_LICENSE",
    "UNVERIFIED",
    "check_required_fields",
    "counting_basis",
    "format_provenance_report",
    "format_report",
    "provenance_report",
]

# --------------------------------------------------------------------------- #
# 口径来源分层
# --------------------------------------------------------------------------- #
ORIGIN_CURATED = "curated"
ORIGIN_EXPANDED = "expanded"
ORIGIN_DERIVED = "derived"
ORIGINS = (ORIGIN_CURATED, ORIGIN_EXPANDED, ORIGIN_DERIVED)

#: 每条实体必须存在的溯源字段
REQUIRED_FIELDS = ("origin", "source", "license", "retrieved")

#: 未核实来源的占位值——显式标注，而不是留空
UNVERIFIED = "UNVERIFIED"
UNKNOWN_LICENSE = "UNKNOWN"
#: GeoKG 自行整理/派生部分使用本仓库许可
AUTHORED_LICENSE = "Apache-2.0"


# --------------------------------------------------------------------------- #
# 来源登记表
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DataSource:
    """一个可追溯的数据来源。

    ``version`` 与 ``retrieved`` 必须具体——"权威来源"这种描述不算溯源。
    """

    id: str
    name: str
    version: str
    license: str
    url: str
    retrieved: str
    tier: str
    note: str = ""

    @property
    def verified(self) -> bool:
        return self.id != UNVERIFIED and not self.id.startswith("unverified")


def _unverified(note: str) -> DataSource:
    """尚未追溯出处的数据。**不得对外引用**，仅在审计中计数。"""
    return DataSource(
        id=UNVERIFIED,
        name="来源待核实",
        version="",
        license=UNKNOWN_LICENSE,
        url="",
        retrieved="",
        tier="T5",
        note=note,
    )


#: 来源登记表。键即 ``properties["source"]``。
SOURCES: dict[str, DataSource] = {
    # ── T1 规范 ──
    "un-m49": DataSource(
        id="un-m49",
        name="UN M49 标准国家或地区代码（Standard country or area codes for statistical use）",
        version="M49（UN Statistics Division 在线版）",
        license="联合国公开数据",
        url="https://unstats.un.org/unsd/methodology/m49/overview/",
        retrieved="2026-09-16",
        tier="T1",
        note="248 国家/地区，另由 ISO 3166-1 补 TWN 共 249；"
             "由 scripts/fetch_un_m49.py 生成，可复现",
    ),
    "un-sdg-framework": DataSource(
        id="un-sdg-framework",
        name="联合国可持续发展目标全球指标框架",
        version="A/RES/71/313（17 目标 / 169 具体目标）",
        license="UN 公开文件",
        url="https://unstats.un.org/sdgs/indicators/indicators-list/",
        retrieved="2026-09-16",
        tier="T1",
        note="目标与具体目标为规范值；指标计数与原文档声明（231/256）不一致，待与官方清单核对",
    ),
    "iso-3166-1": DataSource(
        id="iso-3166-1",
        name="ISO 3166-1 国家与地区代码",
        version="ISO 3166-1:2020",
        license="ISO 标准（代码表可自由使用，标准文本需购买）",
        url="https://www.iso.org/iso-3166-country-codes.html",
        retrieved="2026-09-16",
        tier="T1",
        note="仅用于补充 UN M49 未单列的 TWN；国家表主体已改用 un-m49",
    ),
    # ── T4 聚合/社区 ──
    "geonames-admin1": DataSource(
        id="geonames-admin1",
        name="GeoNames 一级行政区（admin1）",
        version="admin1CodesASCII.txt + countryInfo.txt（在线最新版）",
        license="Creative Commons Attribution 4.0 (CC BY 4.0)",
        url="https://download.geonames.org/export/dump/",
        retrieved="2026-09-16",
        tier="T4",
        note="3,858 条 / 227 国；由 scripts/fetch_geonames_admin1.py 生成，可复现。"
             "署名：GeoNames, https://www.geonames.org/",
    ),
    # ── T1 规范 ──
    "iogp-epsg": DataSource(
        id="iogp-epsg",
        name="EPSG 大地测量参数数据集（坐标参考系代码）",
        version="EPSG Dataset（经 PROJ 分发）",
        license="EPSG Terms of Use：可分发、须署名 IOGP、禁止以数据集本身牟利",
        url="https://epsg.org/",
        retrieved="2026-09-16",
        tier="T1",
        note="仅收录坐标参考系代码与名称；本地可经 pyproj 离线获取 6,942 条",
    ),
    "iso-ogc-standards": DataSource(
        id="iso-ogc-standards",
        name="ISO / OGC 地理信息标准编号",
        version="ISO 19100 系列 / OGC 标准族",
        license="标准编号与标题为事实性引用；标准文本须向 ISO/OGC 获取",
        url="https://www.ogc.org/standards/",
        retrieved="2026-09-16",
        tier="T1",
        note="仅收录标准编号与名称，不含标准正文",
    ),
    # ── T2 官方机构 ──
    "un-frameworks": DataSource(
        id="un-frameworks",
        name="联合国政策框架（2030 议程 / 巴黎协定 / 仙台框架等）",
        version="各框架正式文本",
        license="联合国公开文件",
        url="https://www.un.org/sustainabledevelopment/",
        retrieved="2026-09-16",
        tier="T2",
        note="框架名称与简称的引用",
    ),
    "wmo-oscar-instruments": DataSource(
        id="wmo-oscar-instruments",
        name="WMO OSCAR/Space 对地观测仪器目录",
        version="OSCAR/Space v2.7（官方 REST API）",
        license="可自由使用与再分发，须致谢 WMO；WMO 不对准确性作担保",
        url="https://space.oscar.wmo.int/apidoc/",
        retrieved="2026-09-16",
        tier="T2",
        note="1,244 台仪器 / 86 机构；由 scripts/fetch_oscar_instruments.py 抓取。"
             "署名：WMO OSCAR/Space",
    ),

    "wmo-oscar-satellites": DataSource(
        id="wmo-oscar-satellites",
        name="WMO OSCAR/Space 对地观测卫星目录",
        version="OSCAR/Space v2.7（官方 REST API）",
        license="可自由使用与再分发，须致谢 WMO；WMO 不对准确性作担保",
        url="https://space.oscar.wmo.int/apidoc/",
        retrieved="2026-09-16",
        tier="T2",
        note="1,044 颗卫星（406 在轨/381 退役/131 规划）；由 "
             "scripts/fetch_oscar_satellites.py 抓取。署名：WMO OSCAR/Space",
    ),

    "esa-worldcover": DataSource(
        id="esa-worldcover",
        name="ESA WorldCover 土地覆盖分类（遵循 FAO LCCS 方案）",
        version="WorldCover v100/v200（11 类）",
        license="Creative Commons Attribution 4.0 (CC BY 4.0)",
        url="https://docs.planet.com/data/public-data/other-datasets/esa-worldcover/",
        retrieved="2026-09-16",
        tier="T2",
        note="转录自产品文档（无官方机器可读清单）；署名随实体分发",
    ),
    # ── T3 同行评议 / 技术报告 ──
    "koppen-geiger-beck2018": DataSource(
        id="koppen-geiger-beck2018",
        name="Köppen-Geiger 气候分类",
        version="Beck et al. 2018, Scientific Data 5:180214（5 主群 / 30 气候型）",
        license="Creative Commons Attribution 4.0 (CC BY 4.0)",
        url="https://doi.org/10.1038/sdata.2018.214",
        retrieved="2026-09-16",
        tier="T3",
        note="转录自该文 Table 1（无官方机器可读清单）",
    ),
    "irdr-peril-classification-2014": DataSource(
        id="irdr-peril-classification-2014",
        name="IRDR 灾害分类（Peril Classification and Hazard Glossary）",
        version="IRDR DATA Publication No. 1, 2014",
        license="IRDR 公开技术报告",
        url="https://www.irdrinternational.org/pdf/uploads/files/sc11/"
            "IRDR_DATA-Project-Report-No.-1.pdf",
        retrieved="2026-09-16",
        tier="T3",
        note="转录自报告正文与图 3/4。⚠️ 原文献明确 peril 与 main event 非一对一，"
             "故 peril 未指定父级；family→main_event 层级照实建立",
    ),
    # ── 自行整理 ──
    "geokg-authored": DataSource(
        id="geokg-authored",
        name="GeoKG 自行整理的技能 / 术语表（自编内容，非外部数据集）",
        version="v0.1.0",
        license=AUTHORED_LICENSE,
        url="https://github.com/muyang/GeoKG",
        retrieved="2026-09-16",
        tier="T1",
        note="本仓库自有内容，非外部引用",
    ),
    "geokg-derived": DataSource(
        id="geokg-derived",
        name="GeoKG 派生规则（监测任务空间、数据需求）",
        version="ingest.py v0.1.0",
        license=AUTHORED_LICENSE,
        url="https://github.com/muyang/GeoKG",
        retrieved="2026-09-16",
        tier="T1",
        note="由策展表交叉积生成，不含观测值",
    ),
}

# 逐个登记"来源待核实"的存量数据（审计发现的债务，保留各自的可读 id）
_UNVERIFIED_NOTES = {
    "unverified-satellite-constellations": "星座展开：无出处",
    "unverified-concepts": "概念/术语表 117 条：无出处",
    "unverified-extended-concepts": "扩充词汇：无出处",
}
for _sid, _note in _UNVERIFIED_NOTES.items():
    SOURCES[_sid] = DataSource(
        id=_sid, name="来源待核实", version="", license=UNKNOWN_LICENSE,
        url="", retrieved="", tier="T5", note=_note,
    )
SOURCES[UNVERIFIED] = _unverified("存量数据未记录来源，需逐个追溯")

#: 各口径包含哪些来源
TIER_DEFINITIONS: dict[str, tuple[str, ...]] = {
    "reference": (ORIGIN_CURATED,),
    "reference+expansion": (ORIGIN_CURATED, ORIGIN_EXPANDED),
    "reference+expansion+country": (ORIGIN_CURATED, ORIGIN_EXPANDED, ORIGIN_DERIVED),
}


# --------------------------------------------------------------------------- #
# 强制检查
# --------------------------------------------------------------------------- #
def check_required_fields(kg: Any) -> list[dict[str, Any]]:
    """返回缺少必需溯源字段的实体（空列表 = 全部合规）。

    这是**硬性**检查：任何实体都必须带 origin/source/license/retrieved。
    值可以是 ``UNVERIFIED``，但字段不能缺席。
    """
    bad: list[dict[str, Any]] = []
    for e in _iter_entities(kg):
        missing = [f for f in REQUIRED_FIELDS if f not in e.properties]
        if missing:
            bad.append({"id": e.id, "type": e.type, "missing": missing})
    return bad


def _iter_entities(kg: Any) -> list[Any]:
    """取出全部实体（KnowledgeGraph 未暴露全量迭代，用空关键字检索）。"""
    return list(kg.search(""))


def provenance_report(kg: Any) -> dict[str, Any]:
    """按来源/分级统计，并列出未核实条目。"""
    by_source: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    unverified: dict[str, int] = {}

    for e in _iter_entities(kg):
        src = e.properties.get("source", UNVERIFIED)
        tier = e.properties.get("source_tier", "T5")
        by_source[src] = by_source.get(src, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1
        if src == UNVERIFIED or src.startswith("unverified"):
            unverified[src] = unverified.get(src, 0) + 1

    total = sum(by_source.values())
    n_unver = sum(unverified.values())
    return {
        "total": total,
        "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        "by_tier": dict(sorted(by_tier.items())),
        "unverified": unverified,
        "unverified_count": n_unver,
        "verified_count": total - n_unver,
        "verified_ratio": (total - n_unver) / total if total else 0.0,
        "missing_fields": check_required_fields(kg),
    }


# --------------------------------------------------------------------------- #
# 计数口径
# --------------------------------------------------------------------------- #
def counting_basis(kg: Any) -> dict[str, Any]:
    """按来源分层统计图谱实体，返回可直接引用的口径报告。"""
    by_origin: dict[str, int] = {o: 0 for o in ORIGINS}
    by_type: dict[str, int] = {}
    by_origin_type: dict[str, dict[str, int]] = {o: {} for o in ORIGINS}
    unclassified: list[str] = []

    for entity in _iter_entities(kg):
        by_type[entity.type] = by_type.get(entity.type, 0) + 1
        origin = entity.properties.get("origin")
        if origin in by_origin:
            by_origin[origin] += 1
            by_origin_type[origin][entity.type] = (
                by_origin_type[origin].get(entity.type, 0) + 1
            )
        else:
            unclassified.append(entity.id)

    tiers = {
        name: sum(by_origin.get(o, 0) for o in origins)
        for name, origins in TIER_DEFINITIONS.items()
    }

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
    add("  按来源分层：")
    add(f"    curated   人工整理参考表      {b.get(ORIGIN_CURATED, 0):>9,}")
    add(f"    expanded  策展表系统性展开    {b.get(ORIGIN_EXPANDED, 0):>9,}")
    add(f"    derived   交叉积/规则派生     {b.get(ORIGIN_DERIVED, 0):>9,}")

    if basis["unclassified"]:
        add("")
        add(f"  ⚠️ unclassified {len(basis['unclassified']):,} 个实体未标记来源分层")

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


def format_provenance_report(prov: dict[str, Any]) -> str:
    """把 :func:`provenance_report` 渲染成审计文本。"""
    out: list[str] = []
    add = out.append
    add("=" * 74)
    add(" GeoKG 数据来源审计")
    add("=" * 74)
    add("")
    add(f"  实体总数            {prov['total']:>9,}")
    add(f"  来源已核实          {prov['verified_count']:>9,}  ({prov['verified_ratio']:.1%})")
    add(f"  来源未核实          {prov['unverified_count']:>9,}")
    add("")

    if prov["missing_fields"]:
        add(f"  ❌ {len(prov['missing_fields'])} 个实体缺少必需溯源字段：")
        for r in prov["missing_fields"][:10]:
            add(f"       {r['type']:<20} {r['id']:<34} 缺 {r['missing']}")
    else:
        add("  ✅ 全部实体均带 origin/source/license/retrieved")

    add("")
    add("  按来源：")
    for s, n in prov["by_source"].items():
        src = SOURCES.get(s)
        tier = src.tier if src else "?"
        flag = "  ⚠️ 未核实" if (s == UNVERIFIED or s.startswith("unverified")) else ""
        add(f"    {tier:<4}{s:<38}{n:>7,}{flag}")

    add("")
    add("  按来源分级：")
    for t, n in prov["by_tier"].items():
        add(f"    {t:<6}{n:>9,}")
    add("")

    if prov["unverified_count"]:
        add("  ⚠️ 未核实来源的数据**不得对外引用**，须先补齐 source/license/retrieved。")
        add("")
    return "\n".join(out)
