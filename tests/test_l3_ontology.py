"""L3 地球系统本体测试（土地覆盖 / 气候 / 灾害）。

锁住三层信息：

1. **条目与层级结构**正确（分类是转录的，条目数变了就说明转录被改动）；
2. **层级关系真的建立了**——曾经因为父级 id 少了 level 而静默丢失全部
   ``IS_A`` 关系，因此这里必须断言关系存在，而不只是断言实体存在；
3. **来源已登记且署名随数据分发**（CC BY 4.0 的合规要求）。
"""

from __future__ import annotations

import pytest
from geonexus.kg import KnowledgeGraph

from geokg.ingest import run_full_ingestion
from geokg.ontology import (
    CLIMATE_TERMS,
    HAZARD_TERMS,
    LANDCOVER_ATTRIBUTION,
    LANDCOVER_TERMS,
    ontology_stats,
)
from geokg.provenance import SOURCES


@pytest.fixture(scope="module")
def kg() -> KnowledgeGraph:
    g = KnowledgeGraph("t-l3")
    run_full_ingestion(g, include_monitoring=False)
    return g


class TestTermFiles:
    def test_expected_counts(self) -> None:
        s = ontology_stats()
        assert s["landcover_classes"] == 11        # ESA WorldCover
        assert s["climate_groups"] == 5            # Köppen 主群
        assert s["climate_classes"] == 30          # Köppen 气候型（Beck 2018 Table 1）
        assert s["hazard_families"] == 6           # IRDR family
        assert s["hazard_main_events"] == 20       # IRDR main event
        assert s["hazard_perils"] == 47            # IRDR peril
        assert s["total"] == 119

    def test_codes_unique_within_level(self) -> None:
        """唯一性按 **level 内** 判定：IRDR 把 "Airburst" 同时列在
        main_event 与 peril 两级，跨级重名是文献本意，不是错误。"""
        for name, terms in (("landcover", LANDCOVER_TERMS), ("climate", CLIMATE_TERMS),
                            ("hazard", HAZARD_TERMS)):
            seen: set[tuple[str, str]] = set()
            for t in terms:
                key = (t.level, t.code)
                assert key not in seen, f"{name} 在 level={t.level} 内重复 code={t.code}"
                seen.add(key)

    def test_climate_group_codes(self) -> None:
        assert {t.code for t in CLIMATE_TERMS if t.level == "group"} == set("ABCDE")

    def test_koppen_covers_all_families(self) -> None:
        classes = [t for t in CLIMATE_TERMS if t.level == "class"]
        assert {t.parent for t in classes} == set("ABCDE")

    def test_hazard_families_match_irdr(self) -> None:
        fams = {t.code for t in HAZARD_TERMS if t.level == "family"}
        assert fams == {"Geophysical", "Hydrological", "Meteorological",
                        "Climatological", "Biological", "Extraterrestrial"}


class TestHierarchyRelations:
    def test_climate_classes_linked_to_group(self, kg: KnowledgeGraph) -> None:
        classes = kg.search_by_type("ClimateClass")
        assert len(classes) == 35
        linked = [c for c in classes
                  if [t for t, _ in kg.neighbors(c.id, "IS_A")
                      if t.properties.get("level") == "group"]]
        assert len(linked) == 30, f"仅 {len(linked)}/30 个气候型挂上了主群"

    def test_main_events_linked_to_family(self, kg: KnowledgeGraph) -> None:
        evs = [h for h in kg.search_by_type("HazardType")
               if h.properties["ontology_level"] == "main_event"]
        assert len(evs) == 20
        linked = [e for e in evs if kg.neighbors(e.id, "IS_A")]
        assert len(linked) == 20, f"仅 {len(linked)}/20 个 main event 挂上了 family"

    def test_perils_have_no_forced_parent(self, kg: KnowledgeGraph) -> None:
        """IRDR 说明 peril 与 main event 非一对一，不得强行指定父级。"""
        perils = [h for h in kg.search_by_type("HazardType")
                  if h.properties["ontology_level"] == "peril"]
        assert len(perils) == 47
        assert all(not kg.neighbors(p.id, "IS_A") for p in perils), (
            "peril 被挂上了父级——原文献未定义该关系，属于编造")

    def test_total_is_a_relations(self, kg: KnowledgeGraph) -> None:
        n = sum(len(kg.neighbors(e.id, "IS_A"))
                for t in ("ClimateClass", "HazardType")
                for e in kg.search_by_type(t))
        assert n == 50, f"期望 30(气候) + 20(灾害 main event) = 50，实际 {n}"

    def test_airburst_kept_at_both_levels(self, kg: KnowledgeGraph) -> None:
        """IRDR 在两处列出 Airburst；id 带层级才不会静默合并。"""
        assert kg.get_entity("hazard.main_event.airburst") is not None
        assert kg.get_entity("hazard.peril.airburst") is not None


class TestProvenance:
    def test_sources_registered(self) -> None:
        for sid in ("esa-worldcover", "koppen-geiger-beck2018",
                    "irdr-peril-classification-2014"):
            assert sid in SOURCES, f"{sid} 未登记"
            assert SOURCES[sid].verified, f"{sid} 未标记为已核实"

    def test_tiers(self) -> None:
        assert SOURCES["esa-worldcover"].tier == "T2"          # 官方机构
        assert SOURCES["koppen-geiger-beck2018"].tier == "T3"  # 同行评议
        assert SOURCES["irdr-peril-classification-2014"].tier == "T3"

    def test_t4_sources_document_limits(self) -> None:
        for sid in ("esa-worldcover", "koppen-geiger-beck2018",
                    "irdr-peril-classification-2014"):
            assert SOURCES[sid].note, f"{sid} 必须说明转录/局限"

    def test_landcover_carries_attribution(self, kg: KnowledgeGraph) -> None:
        """CC BY 4.0 要求署名随数据分发，而不是只写在文档里。"""
        for e in kg.search_by_type("LandCoverClass"):
            assert e.properties.get("attribution") == LANDCOVER_ATTRIBUTION

    def test_entities_carry_source(self, kg: KnowledgeGraph) -> None:
        for t, sid in (("LandCoverClass", "esa-worldcover"),
                       ("ClimateClass", "koppen-geiger-beck2018"),
                       ("HazardType", "irdr-peril-classification-2014")):
            for e in kg.search_by_type(t):
                assert e.properties["source"] == sid
