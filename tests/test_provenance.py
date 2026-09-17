"""计数口径（provenance）测试。

这些测试锁住的是**考核口径的可复现性**，不只是功能：

* 每个实体都必须带来源标记——否则计数不可信；
* ``monitor_levels=[]`` 必须真的不生成监测单元（曾因 ``levels or [...]``
  静默回退到最大配置，使"纯策展"数字无法通过该参数取得）；
* 各口径规模必须与实体总数自洽。
"""

from __future__ import annotations

import pytest
from geonexus.kg import KnowledgeGraph

from geokg.ingest import (
    ORIGIN_CURATED,
    ORIGIN_DERIVED,
    ORIGIN_EXPANDED,
    run_full_ingestion,
)
from geokg.provenance import counting_basis, format_report


@pytest.fixture(scope="module")
def curated_kg() -> KnowledgeGraph:
    kg = KnowledgeGraph("t-curated")
    run_full_ingestion(kg, monitor_levels=[], include_monitoring=False)
    return kg


@pytest.fixture(scope="module")
def country_kg() -> KnowledgeGraph:
    kg = KnowledgeGraph("t-country")
    run_full_ingestion(kg, monitor_levels=["country"])
    return kg


class TestOriginTagging:
    def test_every_entity_is_classified(self, country_kg: KnowledgeGraph) -> None:
        basis = counting_basis(country_kg)
        assert basis["unclassified"] == [], (
            f"{len(basis['unclassified'])} entities lack an origin tag"
        )

    def test_origins_sum_to_total(self, country_kg: KnowledgeGraph) -> None:
        basis = counting_basis(country_kg)
        assert sum(basis["by_origin"].values()) == country_kg.entity_count()

    def test_curated_run_has_no_derived(self, curated_kg: KnowledgeGraph) -> None:
        basis = counting_basis(curated_kg)
        assert basis["by_origin"][ORIGIN_DERIVED] == 0
        assert basis["by_origin"][ORIGIN_CURATED] > 0
        assert basis["by_origin"][ORIGIN_EXPANDED] > 0

    def test_monitoring_entities_are_derived(self, country_kg: KnowledgeGraph) -> None:
        for t in ("MonitoringUnit", "DataRequirement"):
            for e in country_kg.search_by_type(t):
                assert e.properties.get("origin") == ORIGIN_DERIVED

    def test_reference_entities_are_curated(self, curated_kg: KnowledgeGraph) -> None:
        for e in curated_kg.search_by_type("SDG_Goal"):
            assert e.properties.get("origin") == ORIGIN_CURATED
        for e in curated_kg.search_by_type("Country"):
            assert e.properties.get("origin") == ORIGIN_CURATED


class TestEmptyMonitorLevels:
    """回归：``[]`` 曾被 ``or`` 吞掉，静默变成"最大配置"。"""

    def test_empty_levels_means_no_monitoring(self) -> None:
        kg = KnowledgeGraph("t-empty")
        run_full_ingestion(kg, monitor_levels=[])
        assert kg.search_by_type("MonitoringUnit") == []
        assert kg.search_by_type("DataRequirement") == []

    def test_empty_levels_equals_include_monitoring_false(self) -> None:
        a = KnowledgeGraph("t-a")
        run_full_ingestion(a, monitor_levels=[])
        b = KnowledgeGraph("t-b")
        run_full_ingestion(b, monitor_levels=["country", "admin1"], include_monitoring=False)
        assert a.entity_count() == b.entity_count()

    def test_none_levels_uses_documented_default(self) -> None:
        kg = KnowledgeGraph("t-none")
        run_full_ingestion(kg, monitor_levels=None)
        # 默认 = country + admin1，即最大配置
        assert kg.search_by_type("MonitoringUnit")


class TestTiers:
    def test_tiers_are_monotonic(self, country_kg: KnowledgeGraph) -> None:
        t = counting_basis(country_kg)["tiers"]
        assert t["reference"] <= t["reference+expansion"] <= t["reference+expansion+country"]

    def test_reference_tier_matches_curated_origin(self, country_kg: KnowledgeGraph) -> None:
        basis = counting_basis(country_kg)
        assert basis["tiers"]["reference"] == basis["by_origin"][ORIGIN_CURATED]

    def test_admin1_grows_the_derived_share(self) -> None:
        c = KnowledgeGraph("t-c")
        run_full_ingestion(c, monitor_levels=["country"])
        a = KnowledgeGraph("t-a")
        run_full_ingestion(a, monitor_levels=["country", "admin1"])
        assert a.entity_count() > c.entity_count()
        assert counting_basis(a)["by_origin"][ORIGIN_DERIVED] > (
            counting_basis(c)["by_origin"][ORIGIN_DERIVED]
        )


class TestReport:
    def test_report_states_every_tier(self, country_kg: KnowledgeGraph) -> None:
        text = format_report(counting_basis(country_kg))
        assert "基础策展参考数据" in text
        assert "国家级监测任务空间" in text
        assert "派生实体占" in text

    def test_report_flags_unclassified(self) -> None:
        kg = KnowledgeGraph("t-bad")
        from geonexus.kg import KGEntity

        kg.add_entity(KGEntity("x.1", "Concept", {"name": "untagged"}, []))
        text = format_report(counting_basis(kg))
        assert "unclassified" in text
