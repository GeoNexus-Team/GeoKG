"""GeoKG 批量灌数流水线 — 多源实体导入。

数据源：
1. 参考数据集（离线可用）：SDG 框架 / ISO 国家 / 卫星目录 / 行政区 / 概念表
2. GAAG 合约注册中心：已注册的数据产品
3. 适配器批量抓取（需网络）：OSM / Sentinel Hub

用法：
    from geonexus.kg import KnowledgeGraph
    from geokg.ingest import run_full_ingestion

    kg = KnowledgeGraph("geonexus")
    report = run_full_ingestion(kg)
    print(report)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from geonexus.kg import KGEntity, KnowledgeGraph

from .reference_data import (
    CONCEPTS,
    COUNTRIES,
    GEOSPATIAL_INDICATORS,
    SATELLITES,
    SDG_GOALS,
    SDG_INDICATOR_COUNTS,
    SDG_TARGETS,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# 溯源标记
#
# 来源分层（origin）与来源标识（source/license/retrieved）的定义与登记表
# 在 geokg.provenance 中；这里只负责在摄入时把它们**盖到每个实体上**。
# --------------------------------------------------------------------------- #
from .provenance import (  # noqa: E402
    ORIGIN_CURATED,
    ORIGIN_DERIVED,
    ORIGIN_EXPANDED,
    SOURCES,
    DataSource,
)


class _ProvenanceKG:
    """把摄入阶段的来源与许可写进每个新增实体的 properties。

    只重写 ``add_entity``，其余属性转发给真实图谱对象，因此摄入函数无需改动。
    未提供 ``source`` 时按 ``UNVERIFIED`` 记录——绝不静默当作已核实。
    """

    __slots__ = ("_kg", "_origin", "_src")

    def __init__(self, kg: KnowledgeGraph, origin: str, source: str | DataSource) -> None:
        self._kg = kg
        self._origin = origin
        ds = SOURCES.get(source) if isinstance(source, str) else source
        if ds is None:
            raise KeyError(f"未登记的来源: {source!r}——请先在 geokg.provenance.SOURCES 中登记")
        self._src = ds

    def add_entity(self, entity: Any) -> Any:
        pr = entity.properties
        pr.setdefault("origin", self._origin)
        pr.setdefault("source", self._src.id)
        pr.setdefault("source_tier", self._src.tier)
        pr.setdefault("license", self._src.license)
        pr.setdefault("retrieved", self._src.retrieved)
        return self._kg.add_entity(entity)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._kg, name)



@dataclass
class IngestReport:
    """灌数报告。"""

    entities_added: int = 0
    relations_added: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    total_entities: int = 0

    def record(self, source: str, entities: int, relations: int = 0) -> None:
        self.entities_added += entities
        self.relations_added += relations
        self.by_source[source] = entities

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities_added": self.entities_added,
            "relations_added": self.relations_added,
            "by_source": self.by_source,
            "total_entities": self.total_entities,
        }

    def __str__(self) -> str:
        lines = [
            "GeoKG 灌数报告",
            f"  本次新增实体: {self.entities_added}",
            f"  本次新增关系: {self.relations_added}",
            f"  图谱实体总数: {self.total_entities}",
            "  分来源:",
        ]
        for src, n in sorted(self.by_source.items(), key=lambda x: -x[1]):
            lines.append(f"    {src:24s} {n:>7d}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 1. SDG 框架
# --------------------------------------------------------------------------- #
def ingest_sdg_framework(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入 UN SDG 框架：目标 → 具体目标 → 指标（三级层级）。"""
    entities = 0
    relations = 0

    for num, title in SDG_GOALS.items():
        goal_id = f"sdg.goal.{num}"
        kg.add_entity(KGEntity(
            id=goal_id, type="SDG_Goal",
            properties={"number": num, "title": title},
            labels=["sdg", "goal"],
        ))
        entities += 1

        # 具体目标
        for t in range(1, SDG_TARGETS[num] + 1):
            target_id = f"sdg.target.{num}.{t}"
            kg.add_entity(KGEntity(
                id=target_id, type="SDG_Target",
                properties={"number": f"{num}.{t}", "goal": num},
                labels=["sdg", "target"],
            ))
            kg.add_relation(target_id, goal_id, "BELONGS_TO")
            entities += 1
            relations += 1

        # 指标
        for i in range(1, SDG_INDICATOR_COUNTS[num] + 1):
            ind_id = f"sdg.indicator.{num}.{i}"
            is_geo = f"{num}.{i}" in GEOSPATIAL_INDICATORS or any(
                k.startswith(f"{num}.{i}.") for k in GEOSPATIAL_INDICATORS
            )
            props: dict[str, Any] = {
                "number": f"{num}.{i}",
                "goal": num,
                "geospatial": is_geo,
            }
            # 补充已知的地理空间指标标题
            for key, title_txt in GEOSPATIAL_INDICATORS.items():
                if key == f"{num}.{i}":
                    props["title"] = title_txt
                    break
            kg.add_entity(KGEntity(
                id=ind_id, type="SDG_Indicator",
                properties=props,
                labels=["sdg", "indicator"] + (["geospatial"] if is_geo else []),
            ))
            kg.add_relation(ind_id, f"sdg.target.{num}.{t if t <= SDG_TARGETS[num] else 1}", "MEASURES")
            entities += 1
            relations += 1

    # 已知标题的地理空间指标补全（可能超出编号范围）
    for key, title in GEOSPATIAL_INDICATORS.items():
        ind_id = f"sdg.indicator.{key}"
        if kg.get_entity(ind_id) is None:
            goal_num = int(key.split(".")[0])
            kg.add_entity(KGEntity(
                id=ind_id, type="SDG_Indicator",
                properties={"number": key, "title": title, "goal": goal_num, "geospatial": True},
                labels=["sdg", "indicator", "geospatial"],
            ))
            entities += 1

    report.record("sdg_framework", entities, relations)


# --------------------------------------------------------------------------- #
# 2. 国家与区域
# --------------------------------------------------------------------------- #
def ingest_countries(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入 ISO 3166-1 国家 + 大区/次区域层级。"""
    entities = 0
    relations = 0
    regions_seen: set[str] = set()
    subregions_seen: set[str] = set()

    for iso3, name, region, subregion in COUNTRIES:
        # 大区实体
        region_id = f"region.{region.lower().replace(' ', '-')}"
        if region_id not in regions_seen:
            kg.add_entity(KGEntity(region_id, "Region", {"name": region, "level": "macro"}, ["region", "macro"]))
            regions_seen.add(region_id)
            entities += 1

        # 次区域实体
        sub_id = f"region.{subregion.lower().replace(' ', '-').replace(',', '')}"
        if sub_id not in subregions_seen:
            kg.add_entity(KGEntity(sub_id, "Region", {"name": subregion, "level": "sub"}, ["region", "subregion"]))
            kg.add_relation(sub_id, region_id, "LOCATED_IN")
            subregions_seen.add(sub_id)
            entities += 1
            relations += 1

        # 国家实体
        country_id = f"country.{iso3}"
        kg.add_entity(KGEntity(
            id=country_id, type="Country",
            properties={"iso3": iso3, "name": name, "region": region, "subregion": subregion},
            labels=["country", "region"],
        ))
        kg.add_relation(country_id, sub_id, "LOCATED_IN")
        entities += 1
        relations += 1

    report.record("countries", entities, relations)


# --------------------------------------------------------------------------- #
# 3. 卫星与载荷
# --------------------------------------------------------------------------- #
def ingest_satellites(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入对地观测卫星目录 + 波段实体。"""
    entities = 0
    relations = 0

    for sat_id, name, agency, sat_type, sensor, res, bands in SATELLITES:
        sid = f"satellite.{sat_id}"
        kg.add_entity(KGEntity(
            id=sid, type="Satellite",
            properties={
                "name": name, "agency": agency, "type": sat_type,
                "sensor": sensor, "resolution_m": res, "band_count": len(bands),
            },
            labels=["satellite", sat_type],
        ))
        entities += 1

        # 机构实体
        org_id = f"org.{agency.split('/')[0].lower().replace(' ', '-')}"
        if kg.get_entity(org_id) is None:
            kg.add_entity(KGEntity(org_id, "Organization", {"name": agency}, ["organization"]))
            entities += 1
        kg.add_relation(sid, org_id, "OWNS")
        relations += 1

        # 波段实体
        for band in bands:
            bid = f"band.{sat_id}.{band}"
            kg.add_entity(KGEntity(
                id=bid, type="Band",
                properties={"satellite": sat_id, "name": band, "sensor": sensor},
                labels=["band", "sensor"],
            ))
            kg.add_relation(bid, sid, "BELONGS_TO")
            entities += 1
            relations += 1

    report.record("satellites", entities, relations)


# --------------------------------------------------------------------------- #
# 4. 概念本体
# --------------------------------------------------------------------------- #
def ingest_concepts(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入领域概念/术语表，并关联到所属类别。"""
    entities = 0
    relations = 0

    for category, terms in CONCEPTS.items():
        cat_id = f"concept.{category.lower()}"
        kg.add_entity(KGEntity(
            id=cat_id, type="ConceptCategory",
            properties={"name": category, "term_count": len(terms)},
            labels=["concept", "category"],
        ))
        entities += 1

        for term in terms:
            slug = term.lower().replace(" ", "-").replace(":", "").replace(".", "-").replace("/", "-")
            tid = f"term.{slug}"
            if kg.get_entity(tid) is None:
                kg.add_entity(KGEntity(
                    id=tid, type="Concept",
                    properties={"name": term, "category": category},
                    labels=["concept", category.lower()],
                ))
                entities += 1
            kg.add_relation(tid, cat_id, "BELONGS_TO")
            relations += 1

    report.record("concepts", entities, relations)


# --------------------------------------------------------------------------- #
# 5. 技能与数据产品
# --------------------------------------------------------------------------- #
def ingest_skills(kg: KnowledgeGraph, skill_names: list[str], report: IngestReport) -> None:
    """导入 GeoSkill 实体。"""
    entities = 0
    relations = 0
    skill_cat = "concept.skills"
    if kg.get_entity(skill_cat) is None:
        kg.add_entity(KGEntity(skill_cat, "ConceptCategory", {"name": "GeoSkills"}, ["concept", "category"]))
        entities += 1

    for name in skill_names:
        sid = f"skill.{name}"
        kg.add_entity(KGEntity(
            id=sid, type="Skill",
            properties={"name": name},
            labels=["skill", "geoskill"],
        ))
        kg.add_relation(sid, skill_cat, "BELONGS_TO")
        entities += 1
        relations += 1

    report.record("skills", entities, relations)


def ingest_gaag_contracts(kg: KnowledgeGraph, registry: Any, report: IngestReport) -> None:
    """从 GAAG 注册中心导入数据产品实体。"""
    before = kg.entity_count()
    kg.import_from_gaag(registry)
    added = kg.entity_count() - before
    report.record("gaag_contracts", added)


# --------------------------------------------------------------------------- #
# 6. 扩充数据集（gazetteer）
# --------------------------------------------------------------------------- #
def ingest_satellite_constellations(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入大型卫星星座（Planet/Jilin-1/ICEYE 等），扩充至 ≥400 颗。"""
    from .gazetteer import expand_satellite_constellations

    entities = 0
    relations = 0

    for sat_id, name, agency, sat_type, sensor, res, bands in expand_satellite_constellations():
        sid = f"satellite.{sat_id}"
        if kg.get_entity(sid) is not None:
            continue
        kg.add_entity(KGEntity(
            id=sid, type="Satellite",
            properties={
                "name": name, "agency": agency, "type": sat_type,
                "sensor": sensor, "resolution_m": res, "band_count": len(bands),
                "constellation": sat_id.rsplit("-", 1)[0],
            },
            labels=["satellite", sat_type, "constellation"],
        ))
        entities += 1

        org_id = f"org.{agency.split('/')[0].lower().replace(' ', '-')}"
        if kg.get_entity(org_id) is None:
            kg.add_entity(KGEntity(org_id, "Organization", {"name": agency}, ["organization"]))
            entities += 1
        kg.add_relation(sid, org_id, "OWNS")
        relations += 1

        for band in bands:
            bid = f"band.{sat_id}.{band}"
            if kg.get_entity(bid) is not None:
                continue
            kg.add_entity(KGEntity(
                id=bid, type="Band",
                properties={"satellite": sat_id, "name": band, "sensor": sensor},
                labels=["band", "sensor"],
            ))
            kg.add_relation(bid, sid, "BELONGS_TO")
            entities += 1
            relations += 1

    report.record("satellite_constellations", entities, relations)


def ingest_extended_admin1(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入扩充的一级行政区划（gazetteer + admin1_global）。"""
    from .admin1_global import ADMIN1_GLOBAL
    from .gazetteer import ADMIN1_EXTENDED

    entities = 0
    relations = 0

    merged: dict[str, list[str]] = {}
    for source in (ADMIN1_EXTENDED, ADMIN1_GLOBAL):
        for iso3, regions in source.items():
            merged.setdefault(iso3, []).extend(regions)

    for iso3, regions in merged.items():
        country_id = f"country.{iso3}"
        if kg.get_entity(country_id) is None:
            continue
        for name in regions:
            slug = (name.lower().replace(" ", "-").replace("'", "")
                    .replace(".", "").replace("(", "").replace(")", "").replace(",", ""))
            admin_id = f"admin1.{iso3}.{slug}"
            if kg.get_entity(admin_id) is not None:
                continue
            kg.add_entity(KGEntity(
                id=admin_id, type="AdminRegion",
                properties={"name": name, "country": iso3, "level": 1},
                labels=["admin", "admin1"],
            ))
            kg.add_relation(admin_id, country_id, "LOCATED_IN")
            entities += 1
            relations += 1

    report.record("admin1_extended", entities, relations)


def ingest_extended_concepts(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入扩充的领域词汇。"""
    from .gazetteer import EXTENDED_CONCEPTS

    entities = 0
    relations = 0

    for category, terms in EXTENDED_CONCEPTS.items():
        cat_id = f"concept.{category.lower()}"
        if kg.get_entity(cat_id) is None:
            kg.add_entity(KGEntity(
                id=cat_id, type="ConceptCategory",
                properties={"name": category, "term_count": len(terms)},
                labels=["concept", "category"],
            ))
            entities += 1

        for term in terms:
            slug = (term.lower().replace(" ", "-").replace(":", "").replace(".", "-")
                    .replace("/", "-").replace("(", "").replace(")", ""))
            tid = f"term.{slug}"
            if kg.get_entity(tid) is None:
                kg.add_entity(KGEntity(
                    id=tid, type="Concept",
                    properties={"name": term, "category": category},
                    labels=["concept", category.lower()],
                ))
                entities += 1
            kg.add_relation(tid, cat_id, "BELONGS_TO")
            relations += 1

    report.record("concepts_extended", entities, relations)


def ingest_monitoring_units(
    kg: KnowledgeGraph,
    report: IngestReport,
    levels: list[str] | None = None,
) -> None:
    """生成 SDG 监测工作单元与数据需求图。

    这是 GeoNexus 的**系统任务空间**（课题3 "国家级、城市级 SDGs 评估监测"），
    不含任何观测值：

        行政单元（国家 / 一级行政区）× 地理空间指标  →  MonitoringUnit
        每个监测单元                                  →  3 个 DataRequirement

    数据需求按**行政单元**粒度建实体：肯尼亚的 Sentinel-2 需求与巴西的
    Sentinel-2 需求解析到不同 AOI 与场景目录，是语义上不同的实体。

    Args:
        levels: 监测层级，可选 "country" / "admin1"。默认仅 "country"。
    """
    from .gazetteer import MONITORED_INDICATORS, REQUIRED_INPUTS

    # 同 run_full_ingestion：显式空列表表示「不生成监测单元」，不能回退到默认层级
    if levels is None:
        levels = ["country"]
    entities = 0
    relations = 0

    # 收集行政单元
    units: list[tuple[str, str, dict[str, Any]]] = []  # (unit_id, iso3, props)
    if "country" in levels:
        for c in kg.search_by_type("Country"):
            iso3 = c.properties.get("iso3") or c.id.split(".")[-1]
            units.append((c.id, iso3, {"level": "national", "scope": iso3}))
    if "admin1" in levels:
        for a in kg.search_by_type("AdminRegion"):
            iso3 = a.properties.get("country", "UNK")
            slug = a.id.split(".", 2)[-1]
            units.append((a.id, iso3, {"level": "subnational", "scope": f"{iso3}.{slug}"}))

    for admin_id, iso3, unit_props in units:
        for ind_num, ind_title, theme in MONITORED_INDICATORS:
            scope = unit_props["scope"]
            unit_id = f"monitor.{scope}.{ind_num}"
            if kg.get_entity(unit_id) is not None:
                continue
            kg.add_entity(KGEntity(
                id=unit_id, type="MonitoringUnit",
                properties={
                    "country": iso3,
                    "admin_unit": admin_id,
                    "indicator": ind_num,
                    "indicator_title": ind_title,
                    "theme": theme,
                    "level": unit_props["level"],
                    "status": "not_started",
                },
                labels=["monitoring", unit_props["level"], theme, iso3],
            ))
            entities += 1

            kg.add_relation(unit_id, admin_id, "LOCATED_IN")
            ind_id = f"sdg.indicator.{ind_num}"
            if kg.get_entity(ind_id) is not None:
                kg.add_relation(unit_id, ind_id, "MEASURES")
            relations += 2

            # 数据需求（按行政单元粒度）
            for input_name in REQUIRED_INPUTS.get(theme, []):
                slug = (input_name.lower().replace(" ", "-").replace("/", "-")
                        .replace(".", "-").replace("+", "p"))
                req_id = f"datareq.{scope}.{slug}"
                if kg.get_entity(req_id) is None:
                    kg.add_entity(KGEntity(
                        id=req_id, type="DataRequirement",
                        properties={
                            "name": input_name, "theme": theme,
                            "country": iso3, "scope": scope,
                        },
                        labels=["datareq", theme, iso3],
                    ))
                    entities += 1
                kg.add_relation(unit_id, req_id, "REQUIRES")
                relations += 1

    report.record(f"monitoring_units[{'+'.join(levels)}]", entities, relations)


# --------------------------------------------------------------------------- #
# 7. 适配器批量抓取（需网络）
# --------------------------------------------------------------------------- #
def ingest_from_osm(
    kg: KnowledgeGraph,
    bboxes: list[tuple[str, list[float]]],
    query_types: list[str] | None = None,
    report: IngestReport | None = None,
) -> int:
    """通过 OSM Overpass API 批量抓取要素实体。

    Args:
        bboxes: [(region_label, [south, west, north, east]), ...]
        query_types: building / water / road / landuse

    Returns: 新增实体数
    """
    from geonexus.adapters.osm import query_osm

    query_types = query_types or ["water", "landuse"]
    entities = 0

    for label, bbox in bboxes:
        for qtype in query_types:
            try:
                result = query_osm(bbox, qtype)
            except Exception as exc:
                logger.warning("OSM ingest failed for %s/%s: %s", label, qtype, exc)
                continue
            for el in result.get("elements", []):
                eid = f"osm.{el.get('type', 'way')}.{el['id']}"
                if kg.get_entity(eid) is not None:
                    continue
                kg.add_entity(KGEntity(
                    id=eid, type="OSMFeature",
                    properties={
                        "osm_id": el["id"], "osm_type": el.get("type"),
                        "query_type": qtype, "region": label,
                        "tags": el.get("tags", {}),
                    },
                    labels=["osm", qtype, label],
                ))
                entities += 1

    if report:
        report.record("osm_features", entities)
    return entities


# --------------------------------------------------------------------------- #
# 编排
# --------------------------------------------------------------------------- #
def run_full_ingestion(
    kg: KnowledgeGraph | None = None,
    *,
    gaag_registry: Any = None,
    skill_names: list[str] | None = None,
    include_reference: bool = True,
    include_expansion: bool = True,
    include_monitoring: bool = True,
    monitor_levels: list[str] | None = None,
    include_gaag: bool = True,
    include_skills: bool = True,
) -> IngestReport:
    """执行完整灌数流水线。

    Args:
        kg: 目标知识图谱（None 时新建）。
        gaag_registry: GAAG 注册中心（可选，用于导入数据产品）。
        skill_names: 技能名列表（可选）。
        include_reference: 是否导入基础参考数据集。
        include_expansion: 是否导入扩充星座/行政区/词汇。
        include_monitoring: 是否生成 SDG 监测工作单元与数据需求图。
        monitor_levels: 监测层级 ["country"] 或 ["country", "admin1"]。
        include_gaag: 是否导入 GAAG 合约。
        include_skills: 是否导入技能实体。
    """
    kg = kg or KnowledgeGraph("geonexus")
    report = IngestReport()
    # NOTE: an explicit empty list must mean "no monitoring units". Written as
    # `monitor_levels or [...]`, an empty list silently fell back to the LARGEST
    # configuration, which made the documented "curated only" figure unreachable
    # through this parameter -- the source of the counting-basis confusion.
    if monitor_levels is None:
        monitor_levels = ["country", "admin1"]

    if include_reference:
        ingest_sdg_framework(_ProvenanceKG(kg, ORIGIN_CURATED, "un-sdg-framework"), report)
        ingest_countries(_ProvenanceKG(kg, ORIGIN_CURATED, "iso-3166-1"), report)
        # ⚠️ 以下两项来源待核实（审计债务），显式标注而非默认放行
        ingest_satellites(
            _ProvenanceKG(kg, ORIGIN_CURATED, "unverified-satellites"), report)
        ingest_concepts(
            _ProvenanceKG(kg, ORIGIN_CURATED, "unverified-concepts"), report)

    if include_expansion:
        ingest_satellite_constellations(
            _ProvenanceKG(kg, ORIGIN_EXPANDED, "unverified-satellite-constellations"), report)
        ingest_extended_admin1(
            _ProvenanceKG(kg, ORIGIN_EXPANDED, "unverified-extended-admin1"), report)
        ingest_extended_concepts(
            _ProvenanceKG(kg, ORIGIN_EXPANDED, "unverified-extended-concepts"), report)

    if include_monitoring:
        ingest_monitoring_units(
            _ProvenanceKG(kg, ORIGIN_DERIVED, "geokg-derived"), report,
            levels=monitor_levels,
        )

    if include_skills:
        names = skill_names or [
            "ndvi-analysis", "ndwi-analysis", "ndbi-analysis", "evi-analysis",
            "ndvi-change", "terrain-slope", "terrain-aspect", "buffer-analysis",
            "zonal-stats", "reproject", "clip-crop", "composite-bands",
        ]
        ingest_skills(_ProvenanceKG(kg, ORIGIN_CURATED, "geokg-authored"), names, report)

    if include_gaag and gaag_registry is not None:
        ingest_gaag_contracts(
            _ProvenanceKG(kg, ORIGIN_CURATED, "geokg-authored"), gaag_registry, report)

    report.total_entities = kg.entity_count()
    logger.info("GeoKG ingestion complete: %d entities", report.total_entities)
    return report