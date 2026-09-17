"""GeoKG — GeoNexus 领域知识图谱内容包。

本包只包含**领域内容与内容专属 ETL**，不包含图引擎本身：

* 参考数据集：SDG 框架（17 目标 / 169 具体目标 / 256 指标）、
  221 个国家、114 颗卫星 / 781 波段、一级行政区划、117 个概念
* 一级行政区：GeoNames admin1（CC BY 4.0，见 admin1.py）
* 扩充数据集：星座展开、EXTENDED_CONCEPTS、
  受监测指标、必需输入
* 摄入管道：把上述内容写入 :class:`geonexus.kg.KnowledgeGraph`

通用的图原语（``KnowledgeGraph`` / ``KGEntity`` / ``KGRelation``）与持久化
（gzip / NDJSON / 增量 append）位于 SDK 的 ``geonexus.kg``，本包**依赖**它：

    geokg  ──依赖──▶  geonexus.kg          （图原语 + 持久化）
    geokg  ──依赖──▶  geonexus.adapters    （OSM 适配器，可选路径）

反向依赖为零：SDK 不导入本包。这样领域数据可以独立版本化、独立发布，
SDK 保持精简。

用法::

    from geonexus.kg import KnowledgeGraph
    from geokg.ingest import run_full_ingestion

    kg = KnowledgeGraph()
    report = run_full_ingestion(kg)
"""

from __future__ import annotations

from .ingest import (
    IngestReport,
    ingest_admin1,
    ingest_concepts,
    ingest_countries,
    ingest_extended_concepts,
    ingest_from_osm,
    ingest_gaag_contracts,
    ingest_monitoring_units,
    ingest_satellites,
    ingest_sdg_framework,
    ingest_skills,
    run_full_ingestion,
)
from .provenance import (
    ORIGIN_CURATED,
    ORIGIN_DERIVED,
    ORIGIN_EXPANDED,
    ORIGINS,
    SOURCES,
    UNVERIFIED,
    counting_basis,
    format_provenance_report,
    provenance_report,
)
from .reference_data import (
    CONCEPTS,
    COUNTRIES,
    SDG_GOALS,
    SDG_INDICATOR_COUNTS,
    SDG_TARGETS,
    reference_data_stats,
)

__version__ = "0.1.0"

__all__ = [
    # 溯源（来源/许可/口径）
    "ORIGINS", "ORIGIN_CURATED", "ORIGIN_EXPANDED", "ORIGIN_DERIVED",
    "SOURCES", "UNVERIFIED",
    "counting_basis", "provenance_report", "format_provenance_report",

    # 摄入管道
    "IngestReport",
    "ingest_concepts",
    "ingest_countries",
    "ingest_admin1",
    "ingest_extended_concepts",
    "ingest_from_osm",
    "ingest_gaag_contracts",
    "ingest_monitoring_units",
    "ingest_satellites",
    "ingest_sdg_framework",
    "ingest_skills",
    "run_full_ingestion",
    # 参考数据
    "CONCEPTS",
    "COUNTRIES",
    "SDG_GOALS",
    "SDG_INDICATOR_COUNTS",
    "SDG_TARGETS",
    "reference_data_stats",
]
