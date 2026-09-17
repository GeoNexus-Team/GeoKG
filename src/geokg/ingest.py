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

from .admin1 import ADMIN1_UNITS
from .admin1 import ATTRIBUTION as ADMIN1_ATTRIBUTION
from .ontology import (
    CLIMATE_TERMS,
    HAZARD_TERMS,
    LANDCOVER_ATTRIBUTION,
    LANDCOVER_TERMS,
)
from .reference_data import (
    CONCEPTS,
    COUNTRIES_FULL,
    GEOSPATIAL_INDICATORS,
    SDG_GOALS,
    SDG_INDICATOR_COUNTS,
    SDG_TARGETS,
)
from .satellites import ATTRIBUTION as SATELLITE_ATTRIBUTION
from .satellites import SATELLITES

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



def _slug(text: str) -> str:
    """把名称转成实体 id 用的 slug（模块级共用）。"""
    return (text.lower().replace(" ", "-").replace(",", "").replace("/", "-")
            .replace(":", "").replace("(", "").replace(")", "").replace(".", ""))


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
    """导入 UN M49 国家/地区，并建立**三级**区域层级。

    UN M49 的区域结构是三层：Region（如 Africa）→ Sub-region
    （如 Sub-Saharan Africa）→ Intermediate Region（如 Eastern Africa）。
    国家挂到最细的一级。早先的数据把 Sub-region 与 Intermediate Region
    混为一谈（把 Kenya 直接挂到 Eastern Africa），这里按标准修正。

    数据来自 ``scripts/fetch_un_m49.py`` 生成的 ``data/un_m49_countries.tsv``。
    同时带入 SDG 相关的三项分组标志（LDC / LLDC / SIDS）与发达/发展中分类。

    Antarctica 在 UN M49 中没有区域，只建国家实体、不建区域关系。
    """
    entities = 0
    relations = 0
    seen: set[str] = set()

    def _slug(text: str) -> str:
        return (text.lower().replace(" ", "-").replace(",", "")
                .replace("(", "").replace(")", ""))

    for c in COUNTRIES_FULL:
        parent_id = ""
        # 由粗到细建立区域链，国家挂到最细一级
        for name, level in ((c.region, "macro"), (c.subregion, "sub"),
                            (c.intermediate, "intermediate")):
            if not name:
                continue
            rid = f"region.{_slug(name)}"
            if rid not in seen:
                kg.add_entity(KGEntity(
                    rid, "Region", {"name": name, "level": level},
                    ["region", level]))
                seen.add(rid)
                entities += 1
                if parent_id:
                    kg.add_relation(rid, parent_id, "LOCATED_IN")
                    relations += 1
            parent_id = rid

        country_id = f"country.{c.iso3}"
        props: dict[str, Any] = {
            "iso3": c.iso3, "name": c.name,
            "region": c.region, "subregion": c.subregion,
            "intermediate_region": c.intermediate,
            "m49": c.m49, "iso2": c.iso2,
            "development": c.development,
            "admin_status": c.admin_status,
        }
        if c.ldc:
            props["ldc"] = True
        if c.lldc:
            props["lldc"] = True
        if c.sids:
            props["sids"] = True
        kg.add_entity(KGEntity(
            id=country_id, type="Country", properties=props,
            labels=["country", "region"],
        ))
        entities += 1
        if parent_id:
            kg.add_relation(country_id, parent_id, "LOCATED_IN")
            relations += 1
        # 主权归属（一个中国原则）：HKG / MAC / TWN → CHN。
        # 名称已按 UN M49 / ISO 官方写法标明归属，这里再建立显式关系。
        if c.part_of:
            sovereign_id = f"country.{c.part_of}"
            if kg.get_entity(sovereign_id) is not None:
                kg.add_relation(country_id, sovereign_id, "PART_OF")
                relations += 1

    report.record("un_m49_countries", entities, relations)






# --------------------------------------------------------------------------- #
# 3. 卫星与载荷
# --------------------------------------------------------------------------- #
def ingest_satellites(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入 WMO OSCAR/Space 卫星目录（T2 官方机构）。

    取代了原先 114 条无出处的手写记录与 2,863 条按规则合成的"星座展开"实体
    （见 docs/provenance-audit.md）。OSCAR 是真实的官方目录，无需再用规则凑数。

    实体 id 用 OSCAR slug（官方 id 派生，稳定）；同时建立所属机构关系。
    """
    entities = 0
    relations = 0

    for s in SATELLITES:
        sid = s.entity_id
        if kg.get_entity(sid) is not None:
            continue
        props: dict[str, Any] = {
            "name": s.fullname or s.acronym or s.slug,
            "acronym": s.acronym,
            "oscar_id": s.oscar_id,
            "status": s.status,
            "orbit": s.orbit,
            "attribution": SATELLITE_ATTRIBUTION,
        }
        for key, val in (("space_agency", s.space_agency), ("launch_date", s.launch_date),
                         ("eol", s.eol), ("altitude_km", s.altitude_km),
                         ("ect", s.ect), ("wigos_id", s.wigos_id)):
            if val:
                props[key] = val
        if s.instrument_count:
            props["instrument_count"] = s.instrument_count
        kg.add_entity(KGEntity(
            id=sid, type="Satellite", properties=props,
            labels=["satellite", "oscar"],
        ))
        entities += 1

        if s.space_agency:
            org_id = "org." + _slug(s.space_agency.split(",")[0])
            if kg.get_entity(org_id) is None:
                kg.add_entity(KGEntity(org_id, "Organization",
                                       {"name": s.space_agency}, ["organization"]))
                entities += 1
            kg.add_relation(sid, org_id, "OPERATED_BY")
            relations += 1

    report.record("oscar_satellites", entities, relations)




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


def ingest_admin1(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入 GeoNames 一级行政区（admin1）。

    取代了原先三个不可审计的来源：GADM 来源的 ``ADMIN1_REGIONS``（已隔离），
    以及无出处的 ``gazetteer.ADMIN1_EXTENDED`` 与 ``admin1_global``（已隔离）。

    实体 id 用 ``admin1.{iso3}.{geonameid}``：名称在同国内可能重复，
    用名称生成 id 会静默丢数据。
    """
    entities = 0
    relations = 0

    for u in ADMIN1_UNITS:
        country_id = f"country.{u.iso3}"
        if kg.get_entity(country_id) is None:
            continue  # 该国家不在 UN M49 表中（脚本已过滤，此处为兜底）
        admin_id = u.entity_id
        if kg.get_entity(admin_id) is not None:
            continue
        kg.add_entity(KGEntity(
            id=admin_id, type="AdminRegion",
            properties={
                "name": u.name,
                "asciiname": u.asciiname,
                "country": u.iso3,
                "level": 1,
                "geonames_code": u.geonames_code,
                "geonameid": u.geonameid,
                "attribution": ADMIN1_ATTRIBUTION,
            },
            labels=["admin", "admin1"],
        ))
        kg.add_relation(admin_id, country_id, "LOCATED_IN")
        entities += 1
        relations += 1

    report.record("geonames_admin1", entities, relations)




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
def _ingest_terms(
    kg: KnowledgeGraph,
    report: IngestReport,
    terms: list,
    *,
    id_prefix: str,
    entity_type: str,
    label: str,
    source: str,
) -> None:
    """把本体条目写入图谱，并按 ``parent`` 建立层级关系。

    id 用条目 code（而非名称）——code 是文献中的稳定标识。
    """
    entities = 0
    relations = 0
    seen: set[str] = set()

    def _slug(text: str) -> str:
        return (text.lower().replace(" ", "-").replace(",", "")
                .replace("/", "-").replace(":", "").replace("(", "").replace(")", ""))

    def _id(term) -> str:
        # id 含层级：IRDR 的 "Airburst" 同时出现在 main_event 与 peril 两级，
        # 不带层级会**静默合并**成一条，丢失一级信息。
        return f"{id_prefix}.{term.level}.{_slug(term.code)}"

    for t in terms:
        tid = _id(t)
        if tid in seen or kg.get_entity(tid) is not None:
            continue
        seen.add(tid)
        props = {
            "name": t.name,
            "level": t.level,
            "code": t.code,
            "ontology_level": t.level,
        }
        if t.description:
            props["description"] = t.description
        if source == "esa-worldcover":
            props["attribution"] = LANDCOVER_ATTRIBUTION
        kg.add_entity(KGEntity(
            id=tid, type=entity_type, properties=props,
            labels=[label, t.level],
        ))
        entities += 1

    # 第二遍建层级（父级可能后出现）。
    # 父级 id 也要带层级，因此先按 code 查出父级条目拿到它的 level——
    # 否则 class 的父级会去匹配 group 的 id 而对不上（曾因此静默丢失全部层级关系）。
    by_code = {t.code: t for t in terms}
    for t in terms:
        if not t.parent:
            continue
        pt = by_code.get(t.parent)
        if pt is None:
            raise ValueError(
                f"本体父级未找到: {t.code!r} 的 parent={t.parent!r} 不在同一数据文件中")
        child = _id(t)
        parent = _id(pt)
        if kg.get_entity(child) is None or kg.get_entity(parent) is None:
            continue
        if any(rel.target_id == parent for _, rel in kg.neighbors(child, "IS_A")):
            continue
        kg.add_relation(child, parent, "IS_A")
        relations += 1

    report.record(f"l3_{label}", entities, relations)


def ingest_landcover(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入 ESA WorldCover 土地覆盖分类（11 类，FAO LCCS 方案）。"""
    _ingest_terms(kg, report, LANDCOVER_TERMS, id_prefix="landcover",
                  entity_type="LandCoverClass", label="landcover",
                  source="esa-worldcover")


def ingest_climate(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入 Köppen-Geiger 气候分类（5 主群 + 30 气候型）。"""
    _ingest_terms(kg, report, CLIMATE_TERMS, id_prefix="climate",
                  entity_type="ClimateClass", label="climate",
                  source="koppen-geiger-beck2018")


def ingest_hazards(kg: KnowledgeGraph, report: IngestReport) -> None:
    """导入 IRDR 灾害分类（6 family + 20 main event + 47 peril）。"""
    _ingest_terms(kg, report, HAZARD_TERMS, id_prefix="hazard",
                  entity_type="HazardType", label="hazard",
                  source="irdr-peril-classification-2014")


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
    include_ontology: bool = True,
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
        include_ontology: 是否导入 L3 本体（土地覆盖/气候/灾害）。
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
        ingest_countries(_ProvenanceKG(kg, ORIGIN_CURATED, "un-m49"), report)
        # ⚠️ 以下两项来源待核实（审计债务），显式标注而非默认放行
        ingest_satellites(
            _ProvenanceKG(kg, ORIGIN_CURATED, "wmo-oscar-satellites"), report)
        ingest_concepts(
            _ProvenanceKG(kg, ORIGIN_CURATED, "unverified-concepts"), report)

    if include_expansion:
        ingest_admin1(
            _ProvenanceKG(kg, ORIGIN_EXPANDED, "geonames-admin1"), report)
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

    if include_ontology:
        ingest_landcover(
            _ProvenanceKG(kg, ORIGIN_CURATED, "esa-worldcover"), report)
        ingest_climate(
            _ProvenanceKG(kg, ORIGIN_CURATED, "koppen-geiger-beck2018"), report)
        ingest_hazards(
            _ProvenanceKG(kg, ORIGIN_CURATED, "irdr-peril-classification-2014"),
            report)

    if include_gaag and gaag_registry is not None:
        ingest_gaag_contracts(
            _ProvenanceKG(kg, ORIGIN_CURATED, "geokg-authored"), gaag_registry, report)

    report.total_entities = kg.entity_count()
    logger.info("GeoKG ingestion complete: %d entities", report.total_entities)
    return report