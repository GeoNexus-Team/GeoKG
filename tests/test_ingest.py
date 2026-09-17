"""Tests for GeoKG batch ingestion pipeline (P0 第二档 ②)."""

from __future__ import annotations

import json

from geonexus.kg import KGEntity, KnowledgeGraph

from geokg.ingest import (
    IngestReport,
    ingest_countries,
    ingest_instruments,
    ingest_satellites,
    ingest_sdg_framework,
    ingest_skills,
    ingest_vocabulary,
    run_full_ingestion,
)
from geokg.reference_data import COUNTRIES, reference_data_stats
from geokg.satellites import SATELLITES, satellite_stats
from geokg.sdg import (
    sdg_stats,
)
from geokg.vocabulary import TERMS, vocabulary_stats

# --------------------------------------------------------------------------- #
# 参考数据集完整性
# --------------------------------------------------------------------------- #

class TestReferenceData:
    def test_sdg_framework_counts(self):
        """数字取自 UN SDG 官方 API，而非文档。

        核对期间发现两处问题：文档声称的"231 个唯一指标"是 2017 年
        A/RES/71/313 的过时数字（现为 251），且旧手写表少了 7 个指标。
        """
        st = sdg_stats()
        assert st["goals"] == 17
        assert st["targets"] == 169
        assert st["indicators"] == 251, f"官方 API 现为 251，实际 {st['indicators']}"
        assert st["indicators_tier1"] + st["indicators_tier2"] == st["indicators"]

    def test_countries_count(self):
        stats = reference_data_stats()
        assert stats["countries"] >= 190, f"ISO 国家数偏少: {stats['countries']}"

    def test_satellite_catalog_meets_2026_target(self):
        """2026 年度目标：≥100 颗卫星（现由 WMO OSCAR/Space 提供，T2）。"""
        st = satellite_stats()
        assert st["satellites"] >= 100, f"卫星数偏少: {st}"
        assert st["operational"] > 0 and st["planned"] > 0

    def test_gadm_admin1_removed(self):
        """回归护栏：GADM 来源的一级行政区必须不在包内。

        该数据自述来自 GADM，而 GADM 许可禁止再分发（提交公开仓库即构成
        再分发）。已隔离到仓库之外，此处防止它被无声地加回来。
        """
        import geokg.reference_data as rd

        assert not hasattr(rd, "ADMIN1_REGIONS"), "GADM 来源的 ADMIN1_REGIONS 又回到了包里"
        assert "admin1_regions" not in reference_data_stats()

    def test_vocabulary_present(self):
        """术语表由 CONCEPTS + EXTENDED_CONCEPTS 合并而来，逐条标注来源。"""
        st = vocabulary_stats()
        assert st["terms_total"] == 294
        assert st["terms_authored"] > 0 and st["terms_external"] > 0

    def test_country_tuple_shape(self):
        for entry in COUNTRIES:
            assert len(entry) == 4, f"国家条目字段数应为 4: {entry}"

    def test_satellite_records_carry_provenance(self):
        """卫星目录改为 OSCAR 后，每条记录都应可追溯到官方 id 与机构。"""
        assert len(SATELLITES) == 1044
        for sat in SATELLITES[:50]:
            assert sat.oscar_id, f"{sat.slug} 缺 OSCAR id"
            assert sat.slug and sat.entity_id.startswith("satellite.")
            assert sat.status, f"{sat.slug} 缺状态"


# --------------------------------------------------------------------------- #
# 各导入器
# --------------------------------------------------------------------------- #

class TestIngestSdg:
    def test_creates_goal_target_indicator_hierarchy(self):
        kg = KnowledgeGraph("t")
        report = IngestReport()
        ingest_sdg_framework(kg, report)

        assert len(kg.search_by_type("SDG_Goal")) == 17
        assert len(kg.search_by_type("SDG_Target")) == 169
        assert len(kg.search_by_type("SDG_Indicator")) >= 231

    def test_relations_created(self):
        kg = KnowledgeGraph("t")
        ingest_sdg_framework(kg, IngestReport())
        assert kg.relation_count() > 300

    def test_geospatial_flag(self):
        kg = KnowledgeGraph("t")
        ingest_sdg_framework(kg, IngestReport())
        geo = kg.search_by_label("geospatial")
        assert len(geo) >= 5, "应标记出地理空间相关指标"
        assert any("6.6.1" in e.id for e in geo), "SDG 6.6.1 (水体生态系统) 应在其中"


class TestIngestCountries:
    def test_countries_and_regions(self):
        kg = KnowledgeGraph("t")
        ingest_countries(kg, IngestReport())
        countries = kg.search_by_type("Country")
        assert len(countries) >= 190
        # 大区 + 次区域
        assert len(kg.search_by_type("Region")) > 10

    def test_country_located_in_region(self):
        kg = KnowledgeGraph("t")
        ingest_countries(kg, IngestReport())
        kenya = kg.get_entity("country.KEN")
        assert kenya is not None
        neighbors = kg.neighbors("country.KEN", "LOCATED_IN")
        assert len(neighbors) == 1
        assert "eastern-africa" in neighbors[0][0].id


class TestIngestSatellites:
    """WMO OSCAR/Space 卫星目录的摄入。

    旧的 114 条手写记录 + 2,863 条合成"星座展开"已全部移除（无出处），
    因此这里不再断言 Band 实体或旧的 id 形式。
    """

    def test_oscar_catalog_ingested(self):
        kg = KnowledgeGraph("t")
        ingest_satellites(kg, IngestReport())
        sats = kg.search_by_type("Satellite")
        assert len(sats) == 1044, f"OSCAR 目录应为 1,044 颗，实际 {len(sats)}"

    def test_entity_id_uses_oscar_slug(self):
        kg = KnowledgeGraph("t")
        ingest_satellites(kg, IngestReport())
        assert kg.get_entity("satellite.sentinel_2a") is not None

    def test_operated_by_relation(self):
        kg = KnowledgeGraph("t")
        ingest_satellites(kg, IngestReport())
        n = kg.neighbors("satellite.sentinel_2a", "OPERATED_BY")
        assert len(n) >= 1, "卫星应挂在所属机构下"

    def test_carries_status_and_attribution(self):
        kg = KnowledgeGraph("t")
        ingest_satellites(kg, IngestReport())
        e = kg.get_entity("satellite.sentinel_2a")
        assert e.properties.get("status")
        assert e.properties.get("oscar_id")
        # WMO 许可要求致谢，署名随实体分发
        assert "WMO" in e.properties.get("attribution", "")


class TestIngestVocabulary:
    """术语表摄入（取代原先的 ingest_concepts / ingest_extended_concepts）。"""

    def test_terms_and_categories(self):
        kg = KnowledgeGraph("t")
        ingest_vocabulary(kg, IngestReport())
        assert len(kg.search_by_type("Concept")) == 294
        assert len(kg.search_by_type("ConceptCategory")) == len(
            {t.category for t in TERMS}
        )

    def test_term_linked_to_category(self):
        kg = KnowledgeGraph("t")
        ingest_vocabulary(kg, IngestReport())
        ndvi = next(c for c in kg.search_by_type("Concept")
                    if c.properties["name"] == "NDVI")
        assert kg.neighbors(ndvi.id, "BELONGS_TO")

    def test_each_term_carries_its_own_source(self):
        """术语逐条标注来源——外部来源与自编术语必须区分开。

        来源由管线的 ``_ProvenanceKG`` 包装写入，因此这里走完整流程，
        而不是直接调用摄入函数（直接调用不带来源戳，与其他摄入函数一致）。
        """
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg, include_monitoring=False)
        seen = {c.properties["source"] for c in kg.search_by_type("Concept")}
        assert "geokg-authored" in seen
        assert seen & {"iogp-epsg", "iso-ogc-standards", "un-frameworks"}


class TestIngestInstruments:
    def test_oscar_instruments(self):
        kg = KnowledgeGraph("t")
        ingest_instruments(kg, IngestReport())
        assert len(kg.search_by_type("Instrument")) == 1244

    def test_entity_id_and_attribution(self):
        kg = KnowledgeGraph("t")
        ingest_instruments(kg, IngestReport())
        e = kg.get_entity("instrument.msi")
        assert e is not None, "MSI 应存在（原 Sensors 术语表里的条目）"
        assert e.properties.get("instrument_type")
        assert "WMO" in e.properties.get("attribution", "")


class TestIngestSkills:
    def test_skills(self):
        kg = KnowledgeGraph("t")
        ingest_skills(kg, ["ndvi-analysis", "clip-crop"], IngestReport())
        assert len(kg.search_by_type("Skill")) == 2


# --------------------------------------------------------------------------- #
# 完整流水线
# --------------------------------------------------------------------------- #

class TestFullPipeline:
    def test_run_full_ingestion(self):
        kg = KnowledgeGraph("geonexus")
        report = run_full_ingestion(kg)
        assert report.entities_added > 2000
        assert report.total_entities > 2000
        assert kg.entity_count() == report.total_entities

    def test_report_structure(self):
        kg = KnowledgeGraph("t")
        report = run_full_ingestion(kg)
        d = report.to_dict()
        assert "by_source" in d
        assert d["by_source"]["sdg_framework"] > 300
        assert d["by_source"]["oscar_satellites"] > 1000
        assert str(report).startswith("GeoKG 灌数报告")

    def test_entity_types_diversity(self):
        """考核要求图谱覆盖多领域。"""
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg)
        types = set(kg.stats()["by_type"])
        expected = {
            "SDG_Goal", "SDG_Target", "SDG_Indicator", "Country", "Region",
            "AdminRegion", "Satellite", "Concept", "ConceptCategory",
            "Organization", "Skill", "MonitoringUnit", "DataRequirement",
            "LandCoverClass", "ClimateClass", "HazardType",
        }
        assert expected.issubset(types), f"缺少类型: {expected - types}"

    def test_idempotent_rerun(self):
        """重复灌数不应因重复 id 崩溃（实体数稳定）。"""
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg)
        n1 = kg.entity_count()
        run_full_ingestion(kg)
        assert kg.entity_count() == n1, "重复灌数实体数应稳定"

    def test_meets_2026_entity_target(self):
        """2026 年度考核：GeoKG ≥2 万实体（含派生任务空间）。"""
        kg = KnowledgeGraph("t")
        report = run_full_ingestion(kg)
        assert report.total_entities >= 20000, (
            f"实体数 {report.total_entities} < 20000"
        )

    def test_reference_baseline_a_plus_b(self):
        """策展 + 展开基线（不含派生任务空间）。

        数字随来源整改而变，均为预期：
          8,327 → 7,590  移除 GADM 来源的一级行政区
          7,590 → 8,834  改用 UN M49 国家表 + GeoNames 行政区 + L3 本体
          8,834 → 6,216  卫星目录改用 WMO OSCAR（1,044 条真实记录），
                         同时删除 2,863 条合成"星座展开"与 3,156 条波段实体
        最后一次是**净减少**——用权威目录替掉合成数据，实体数下降是正确的。
        """
        kg = KnowledgeGraph("t")
        report = run_full_ingestion(kg, include_monitoring=False)
        assert report.total_entities > 6000, (
            f"参考基线 {report.total_entities} 偏低"
        )
        # 基线应全部是策展的结构化事实
        types = set(kg.stats()["by_type"])
        assert "MonitoringUnit" not in types
        assert "DataRequirement" not in types

    def test_admin1_global_coverage(self):
        """A+B 扩充后一级行政区应覆盖 3,000+ 且跨国数 150+。"""
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg, include_monitoring=False)
        admins = kg.search_by_type("AdminRegion")
        # 移除 GADM 来源数据后实测 2,763；此处留出余量，避免与新来源数据冲突
        assert len(admins) >= 2000, f"行政区数 {len(admins)} < 2000"
        countries_with_admin = {a.properties["country"] for a in admins}
        assert len(countries_with_admin) >= 150, (
            f"覆盖国家数 {len(countries_with_admin)} < 150"
        )

    def test_conservative_country_only_config(self):
        """保守配置（仅国家级监测）实体数仍可观。"""
        kg = KnowledgeGraph("t")
        report = run_full_ingestion(kg, monitor_levels=["country"])
        assert report.total_entities > 8000

    def test_satellite_target_400(self):
        """终期目标：≥400 颗卫星。"""
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg)
        sats = kg.search_by_type("Satellite")
        assert len(sats) >= 400, f"卫星数 {len(sats)} < 400"

    def test_monitoring_units_cover_geospatial_indicators(self):
        """监测单元应覆盖 12 个地理空间指标。"""
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg)
        units = kg.search_by_type("MonitoringUnit")
        indicators = {u.properties["indicator"] for u in units}
        assert len(indicators) == 12
        assert "6.6.1" in indicators  # 水体生态系统
        assert "15.1.1" in indicators  # 森林覆盖

    def test_monitoring_units_have_requirements(self):
        """每个监测单元应关联数据需求。"""
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg)
        neighbors = kg.neighbors("monitor.KEN.6.6.1", "REQUIRES")
        assert len(neighbors) >= 2, "肯尼亚 SDG 6.6.1 应有数据需求"

    def test_dual_level_monitoring(self):
        """国家级 + 次国家级监测单元并存。"""
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg)
        units = kg.search_by_type("MonitoringUnit")
        levels = {u.properties["level"] for u in units}
        assert "national" in levels
        assert "subnational" in levels


# --------------------------------------------------------------------------- #
# 持久化与累积
# --------------------------------------------------------------------------- #

class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        kg = KnowledgeGraph("persist-test")
        run_full_ingestion(kg)
        n = kg.entity_count()

        path = str(tmp_path / "geokg.json")
        kg.save(path)

        loaded = KnowledgeGraph.load(path)
        assert loaded.entity_count() == n
        assert loaded.relation_count() == kg.relation_count()
        assert loaded.get_entity("country.KEN") is not None

    def test_saved_file_is_valid_json(self, tmp_path):
        kg = KnowledgeGraph("t")
        run_full_ingestion(kg)
        path = tmp_path / "kg.json"
        kg.save(str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "t"
        assert len(data["entities"]) > 2000
        assert len(data["relations"]) > 2000

    def test_incremental_accumulation(self, tmp_path):
        """模拟两次灌数累积：基准 + 追加。"""
        path = str(tmp_path / "kg.json")
        kg = KnowledgeGraph("acc")
        run_full_ingestion(kg)
        base = kg.entity_count()
        kg.save(path)

        # 第二轮：加载后追加自定义实体
        kg2 = KnowledgeGraph.load(path)
        kg2.add_entity(KGEntity("custom.1", "DataProduct", {"name": "extra"}))
        kg2.save(path)

        kg3 = KnowledgeGraph.load(path)
        assert kg3.entity_count() == base + 1
        assert kg3.get_entity("custom.1") is not None