"""GeoKG 参考数据扩充 — 结构化实体批量生成。

本模块生成**系统性结构实体**（非观测数据），用于把知识图谱扩展到考核规模：

1. 卫星星座扩充至 ≥400 颗（对应"卫星资源 ≥400 颗"指标）
2. 国别监测单元（国家 × 地理空间 SDG 指标）—— 对应课题3"国别诊断"需求
3. 行政区划扩充（更多国家的一级行政区）
4. 领域词汇扩充

⚠️ 只生成结构性事实（框架/编号/名称/层级/需求关系），不含任何观测值。
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# 2. 国别监测单元（国家 × 地理空间 SDG 指标）
# --------------------------------------------------------------------------- #
#: GeoNexus 优先监测的地理空间指标（与 reference_data.GEOSPATIAL_INDICATORS 对应）
MONITORED_INDICATORS: list[tuple[str, str, str]] = [
    ("6.6.1", "Change in the extent of water-related ecosystems", "water"),
    ("6.3.2", "Proportion of bodies of water with good ambient water quality", "water"),
    ("15.1.1", "Forest area as a proportion of total land area", "forest"),
    ("15.2.1", "Progress towards sustainable forest management", "forest"),
    ("15.3.1", "Proportion of land that is degraded over total land area", "land"),
    ("15.4.2", "Mountain Green Cover Index", "land"),
    ("11.3.1", "Ratio of land consumption rate to population growth rate", "urban"),
    ("11.7.1", "Average share of the built-up area of cities that is open space", "urban"),
    ("2.4.1", "Proportion of agricultural area under sustainable agriculture", "agriculture"),
    ("13.1.1", "Number of deaths and missing persons attributed to disasters", "disaster"),
    ("14.1.1", "Index of coastal eutrophication and floating plastic debris density", "ocean"),
    ("3.9.1", "Mortality rate attributed to household and ambient air pollution", "air"),
]

#: 监测单元所需的数据输入（真实系统需求，非观测值）
REQUIRED_INPUTS: dict[str, list[str]] = {
    "water": ["Sentinel-2 MSI L2A", "JRC Global Surface Water", "Admin boundaries L1"],
    "forest": ["Sentinel-2 MSI L2A", "Landsat 8/9 OLI", "Global Forest Change"],
    "land": ["Sentinel-2 MSI L2A", "MODIS NDVI", "SoilGrids"],
    "urban": ["Sentinel-1 SAR GRD", "Sentinel-2 MSI L2A", "GHS-SMOD"],
    "agriculture": ["Sentinel-2 MSI L2A", "MODIS EVI", "Cropland extent"],
    "disaster": ["Sentinel-1 SAR GRD", "Sentinel-2 MSI L2A", "Population grid"],
    "ocean": ["Sentinel-3 OLCI", "MODIS Ocean Color", "Coastline vector"],
    "air": ["Sentinel-5P TROPOMI", "CAMS reanalysis", "Population grid"],
}


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
def expansion_stats() -> dict[str, int]:
    """返回扩充数据的条目数统计（一级行政区已改由 GeoNames 提供，不计入本模块）。"""
    return {
        "monitored_indicators": len(MONITORED_INDICATORS),
        "required_input_types": len(REQUIRED_INPUTS),
    }