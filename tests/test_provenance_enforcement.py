"""溯源强制检查测试。

对应决策："强制每条实体带 source/license/retrieved"。

这些测试锁住的是**可追溯性**，而不只是功能：
* 任何实体缺任一溯源字段都必须被 :func:`check_required_fields` 抓出来；
* 来源未核实的数据必须显式标 ``UNVERIFIED``，不得静默当作已核实；
* 已登记来源必须齐备（id / version / license / retrieved / tier）；
* GADM 一类"禁止再分发"的来源不得出现在登记表中被当作可用来源。
"""

from __future__ import annotations

import pytest
from geonexus.kg import KGEntity, KnowledgeGraph

from geokg.ingest import ORIGIN_CURATED, run_full_ingestion
from geokg.provenance import (
    REQUIRED_FIELDS,
    SOURCES,
    UNVERIFIED,
    check_required_fields,
    counting_basis,
    format_provenance_report,
    provenance_report,
)


@pytest.fixture(scope="module")
def kg() -> KnowledgeGraph:
    g = KnowledgeGraph("t-prov")
    run_full_ingestion(g, include_monitoring=False)
    return g


class TestRequiredFields:
    def test_every_entity_has_all_required_fields(self, kg: KnowledgeGraph) -> None:
        bad = check_required_fields(kg)
        assert bad == [], f"{len(bad)} 个实体缺溯源字段，例如 {bad[:3]}"

    def test_required_fields_constant_is_enforced(self, kg: KnowledgeGraph) -> None:
        """字段齐全性必须覆盖 REQUIRED_FIELDS 里声明的每一项。"""
        for e in kg.search(""):
            for f in REQUIRED_FIELDS:
                assert f in e.properties, f"{e.id} 缺 {f}"

    def test_untagged_entity_is_detected(self) -> None:
        g = KnowledgeGraph("t-bad")
        g.add_entity(KGEntity("manual.1", "Concept", {"name": "手工塞入"}, []))
        bad = check_required_fields(g)
        assert len(bad) == 1
        assert set(bad[0]["missing"]) == set(REQUIRED_FIELDS)

    def test_provenance_report_flags_missing(self) -> None:
        g = KnowledgeGraph("t-bad2")
        g.add_entity(KGEntity("manual.2", "Concept", {"origin": ORIGIN_CURATED}, []))
        text = format_provenance_report(provenance_report(g))
        assert "缺少必需溯源字段" in text


class TestSourceRegistry:
    def test_every_registered_source_is_complete(self) -> None:
        for sid, ds in SOURCES.items():
            assert ds.id == sid
            if ds.verified:
                assert ds.version, f"{sid} 缺版本"
                assert ds.license and ds.license != "UNKNOWN", f"{sid} 缺许可"
                assert ds.retrieved, f"{sid} 缺检索日期"
                assert ds.url, f"{sid} 缺 URL"
                assert ds.tier in ("T1", "T2", "T3", "T4"), f"{sid} 分级非法: {ds.tier}"
            else:
                assert ds.tier == "T5", f"{sid} 未核实却标了 {ds.tier}"

    def test_unverified_sources_are_marked_t5(self) -> None:
        for sid, ds in SOURCES.items():
            if sid == UNVERIFIED or sid.startswith("unverified"):
                assert not ds.verified
                assert ds.tier == "T5"

    def test_no_redistribution_forbidden_source_registered(self) -> None:
        """GADM 禁止再分发，不得作为可用来源出现在登记表中。"""
        for sid, ds in SOURCES.items():
            blob = f"{sid} {ds.name} {ds.license} {ds.note}".lower()
            assert "gadm" not in blob or not ds.verified, (
                f"{sid} 引用了 GADM 却被标为已核实来源"
            )

    def test_unknown_source_id_raises(self) -> None:
        from geokg.ingest import _ProvenanceKG

        with pytest.raises(KeyError):
            _ProvenanceKG(KnowledgeGraph("t"), ORIGIN_CURATED, "no-such-source")


class TestProvenanceReport:
    def test_totals_reconcile(self, kg: KnowledgeGraph) -> None:
        prov = provenance_report(kg)
        assert prov["total"] == kg.entity_count()
        assert prov["verified_count"] + prov["unverified_count"] == prov["total"]

    def test_ratio_in_range(self, kg: KnowledgeGraph) -> None:
        r = provenance_report(kg)["verified_ratio"]
        assert 0.0 <= r <= 1.0

    def test_verified_sources_declare_tier_and_limits(self, kg: KnowledgeGraph) -> None:
        """已核实 ≠ T1。T3/T4（学术共识、聚合数据）同样可以"已核实"，
        但**必须**在 note 里写明局限，否则等于把聚合数据当权威标准用。
        """
        prov = provenance_report(kg)
        for sid in prov["by_source"]:
            ds = SOURCES[sid]
            if not ds.verified:
                continue
            assert ds.tier in ("T1", "T2", "T3", "T4"), f"{sid} 分级非法 {ds.tier}"
            if ds.tier in ("T3", "T4"):
                assert ds.note, f"{sid} 为 {ds.tier}（非权威标准），必须说明局限"

    def test_regulatory_sources_are_t1(self, kg: KnowledgeGraph) -> None:
        """联合国/ISO 这类规范源必须是 T1。"""
        for sid in ("un-m49", "un-sdg-framework"):
            assert SOURCES[sid].tier == "T1"

    def test_report_mentions_unverified_warning(self, kg: KnowledgeGraph) -> None:
        text = format_provenance_report(provenance_report(kg))
        if provenance_report(kg)["unverified_count"]:
            assert "不得对外引用" in text


class TestCountingBasisUnaffected:
    """溯源改造不应改变口径分层的结果。"""

    def test_origins_unchanged(self, kg: KnowledgeGraph) -> None:
        basis = counting_basis(kg)
        assert basis["unclassified"] == []
        assert basis["total"] == kg.entity_count()
        assert basis["by_origin"][ORIGIN_CURATED] > 0
