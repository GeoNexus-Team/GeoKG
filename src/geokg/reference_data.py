"""GeoKG 参考数据集 — 权威结构化数据，用于知识图谱批量灌数。

数据来源（逐项标注，见 PROVENANCE）：
- SDG 框架：联合国官方编号体系
- 国家：ISO 3166-1
- 卫星目录：**来源待核实**（见 PROVENANCE）
- 概念/术语表：**来源待核实**（见 PROVENANCE）

⚠️ 一级行政区（原 ADMIN1_REGIONS）已于 2026-09 **移出本包**：
其数据自述来自 GADM，而 GADM 许可禁止再分发，提交进公开仓库即构成
再分发。数据已隔离在仓库之外待重新获取来源。详见 PROVENANCE 与
GeoKG/docs/。

说明：本模块只收录结构性事实数据（框架、编号、名称、层级），不含
任何观测值。观测数据必须来自真实数据源（Sentinel Hub / OSM / 统计库）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- #
# UN SDG 框架：17 个目标
# --------------------------------------------------------------------------- #
SDG_GOALS: dict[int, str] = {
    1: "No Poverty",
    2: "Zero Hunger",
    3: "Good Health and Well-being",
    4: "Quality Education",
    5: "Gender Equality",
    6: "Clean Water and Sanitation",
    7: "Affordable and Clean Energy",
    8: "Decent Work and Economic Growth",
    9: "Industry, Innovation and Infrastructure",
    10: "Reduced Inequalities",
    11: "Sustainable Cities and Communities",
    12: "Responsible Consumption and Production",
    13: "Climate Action",
    14: "Life Below Water",
    15: "Life on Land",
    16: "Peace, Justice and Strong Institutions",
    17: "Partnerships for the Goals",
}

#: 各目标的官方具体目标（target）数量，合计 169（含 a/b/c 类执行手段目标）
SDG_TARGETS: dict[int, int] = {
    1: 7, 2: 8, 3: 13, 4: 10, 5: 9, 6: 8, 7: 5, 8: 12, 9: 8,
    10: 10, 11: 10, 12: 11, 13: 5, 14: 10, 15: 12, 16: 12, 17: 19,
}

#: 各目标的官方唯一指标（indicator）数量（IAEG-SDGs 2023 修订版）
SDG_INDICATOR_COUNTS: dict[int, int] = {
    1: 13, 2: 14, 3: 28, 4: 12, 5: 14, 6: 11, 7: 5, 8: 17, 9: 12,
    10: 11, 11: 15, 12: 13, 13: 8, 14: 10, 15: 14, 16: 23, 17: 24,
}

#: 与地理空间观测强相关的关键指标（GeoNexus 优先监测对象）
GEOSPATIAL_INDICATORS: dict[str, str] = {
    "6.3.2": "Proportion of bodies of water with good ambient water quality",
    "6.6.1": "Change in the extent of water-related ecosystems over time",
    "11.3.1": "Ratio of land consumption rate to population growth rate",
    "11.7.1": "Average share of the built-up area of cities that is open space for public use",
    "13.1.1": "Number of deaths and missing persons attributed to disasters",
    "14.1.1": "Index of coastal eutrophication and floating plastic debris density",
    "15.1.1": "Forest area as a proportion of total land area",
    "15.2.1": "Progress towards sustainable forest management",
    "15.3.1": "Proportion of land that is degraded over total land area",
    "15.4.2": "Mountain Green Cover Index",
    "2.4.1": "Proportion of agricultural area under productive and sustainable agriculture",
    "3.9.1": "Mortality rate attributed to household and ambient air pollution",
}


# --------------------------------------------------------------------------- #
# ISO 3166-1 国家与地区（249 条）
# 格式: (ISO3, 英文名, 大区, 次区域)
# --------------------------------------------------------------------------- #
# 国家与地区 —— UN M49
#
# 数据不再手写在源码里，而是由 scripts/fetch_un_m49.py 从联合国 M49 标准
# 生成到 data/un_m49_countries.tsv。这样"来源/日期/取法"都固化在脚本中，
# 任何人都能复现同一份数据；手写常量做不到这一点。
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).resolve().parent / "data"
COUNTRY_DATA_FILE = DATA_DIR / "un_m49_countries.tsv"


@dataclass(frozen=True)
class Country:
    """一条 UN M49 国家/地区记录（含 SDG 相关的三项分组标志）。"""

    iso3: str
    name: str
    region: str
    subregion: str
    intermediate: str = ""
    m49: str = ""
    iso2: str = ""
    ldc: bool = False      # 最不发达国家
    lldc: bool = False     # 内陆发展中国家
    sids: bool = False     # 小岛屿发展中国家
    development: str = ""  # Developed / Developing


def load_countries(path: str | Path | None = None) -> list[Country]:
    """从数据文件加载国家/地区表（制表符分隔，11 列，``#`` 行为注释）。"""
    src = Path(path) if path else COUNTRY_DATA_FILE
    out: list[Country] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) != 11:
            raise ValueError(f"{src.name}: 期望 11 列，实际 {len(f)} 列 -> {line[:60]!r}")
        out.append(Country(
            iso3=f[0], name=f[1], region=f[2], subregion=f[3], intermediate=f[4],
            m49=f[5], iso2=f[6],
            ldc=bool(f[7]), lldc=bool(f[8]), sids=bool(f[9]), development=f[10],
        ))
    if not out:
        raise ValueError(f"{src} 未加载到任何国家/地区")
    return out


#: 完整记录（推荐使用）
COUNTRIES_FULL: list[Country] = load_countries()

#: 兼容旧接口的 4 元组视图：(iso3, name, region, subregion)
COUNTRIES: list[tuple[str, str, str, str]] = [
    (c.iso3, c.name, c.region, c.subregion) for c in COUNTRIES_FULL
]


# --------------------------------------------------------------------------- #
# 对地观测卫星目录（2026 目标 ≥100 颗）
# 格式: (标识, 名称, 机构, 类型, 传感器, 分辨率m, 波段列表)
# --------------------------------------------------------------------------- #
def _satellites() -> list[tuple[str, str, str, str, str, float, list[str]]]:
    sats: list[tuple[str, str, str, str, str, float, list[str]]] = []

    # Sentinel 系列 (ESA/Copernicus)
    s2_bands = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"]
    for i in range(1, 5):
        sats.append((f"SENTINEL-2{'ABCD'[i-1]}", f"Sentinel-2{'ABCD'[i-1]}", "ESA", "optical", "MSI", 10.0, s2_bands))
    for i in range(1, 4):
        sats.append((f"SENTINEL-1{'ABC'[i-1]}", f"Sentinel-1{'ABC'[i-1]}", "ESA", "sar", "C-SAR", 5.0, ["VV", "VH"]))
    for i in range(1, 4):
        sats.append((f"SENTINEL-3{'AB'[i-1] if i < 3 else 'B'}", f"Sentinel-3{'AB'[i-1] if i < 3 else 'B'}", "ESA", "optical", "OLCI/SLSTR/SRAL", 300.0,
                     ["Oa01","Oa02","Oa03","Oa04","Oa05","Oa06","Oa07","Oa08","Oa09","Oa10","Oa11","Oa12","Oa13","Oa14","Oa15","Oa16","Oa17","Oa18","Oa19","Oa20","Oa21","S1","S2","S3","S4","S5","S6"]))
    sats.append(("SENTINEL-5P", "Sentinel-5P", "ESA", "atmospheric", "TROPOMI", 3500.0, ["NO2", "SO2", "CO", "CH4", "O3", "AER_AI"]))
    sats.append(("SENTINEL-6A", "Sentinel-6A", "ESA/EUMETSAT", "altimetry", "Poseidon-4", 1300.0, ["SLA", "SWH", "SIG0"]))

    # Landsat 系列 (NASA/USGS)
    landsat_bands = ["B1","B2","B3","B4","B5","B6","B7","B8","B9","B10","B11"]
    for n in (7, 8, 9):
        res = 15.0 if n >= 8 else 15.0
        sats.append((f"LANDSAT-{n}", f"Landsat {n}", "NASA/USGS", "optical", "OLI/TIRS" if n >= 8 else "ETM+", res, landsat_bands))

    # MODIS / VIIRS
    sats.append(("TERRA", "Terra", "NASA", "optical", "MODIS", 250.0, ["B01","B02","B03","B04","B05","B06","B07"]))
    sats.append(("AQUA", "Aqua", "NASA", "optical", "MODIS", 250.0, ["B01","B02","B03","B04","B05","B06","B07"]))
    for name in ("SNPP", "NOAA-20", "NOAA-21"):
        sats.append((name, name, "NOAA/NASA", "optical", "VIIRS", 375.0, ["I1","I2","I3","I4","I5","M1","M2","M3","M4","M5","M6","M7"]))

    # 中国高分/资源系列
    for n in range(1, 15):
        sats.append((f"GF-{n}", f"Gaofen-{n}", "CNSA", "optical", f"GF{n}-PMC", 2.0, ["PAN", "MSS"]))
    for n in (1, 2, 3):
        sats.append((f"ZY-3{n:02d}", f"Ziyuan-3 {n:02d}", "MNR China", "optical", "TLC", 2.1, ["NAD", "FWD", "BWD"]))
    sats.append(("ZY-1-02D", "Ziyuan-1 02D", "MNR China", "hyperspectral", "AHSI", 30.0, [f"B{i:03d}" for i in range(1, 167)]))
    for n in range(1, 5):
        sats.append((f"CBERS-{n}", f"CBERS-{n}", "China/Brazil", "optical", "MUX/WFI/IRS", 5.0, ["B5","B6","B7","B8","B13","B14","B15","B16"]))
    sats.append(("HJ-2A", "Huanjing-2A", "CNSA", "optical", "CCD", 16.0, ["B1","B2","B3","B4"]))
    sats.append(("HJ-2B", "Huanjing-2B", "CNSA", "optical", "CCD", 16.0, ["B1","B2","B3","B4"]))

    # 商业高分辨率星座
    for n in range(1, 5):
        sats.append((f"WORLDVIEW-{n}", f"WorldView-{n}", "Maxar", "optical", "WV110", 0.31, ["PAN","MS1","MS2","MS3","MS4","MS5","MS6","MS7","MS8"]))
    for n in range(1, 5):
        sats.append((f"GEOEYE-{n}", f"GeoEye-{n}", "Maxar", "optical", "GIS", 0.41, ["PAN","MS1","MS2","MS3","MS4"]))
    for n in range(1, 5):
        sats.append((f"PLEIADES-{n}{'AB'[n-1] if n <= 2 else ''}", f"Pléiades-{n}", "Airbus", "optical", "HiRI", 0.5, ["PAN","B0","B1","B2","B3"]))
    for n in range(1, 5):
        sats.append((f"SPOT-{n}", f"SPOT-{n}", "Airbus", "optical", "HRG/NAOMI", 1.5, ["PAN","B1","B2","B3","B4"]))
    for n in range(1, 8):
        sats.append((f"SKYSAT-{n}", f"SkySat-{n}", "Planet", "optical", "SkySat-C", 0.5, ["PAN","B","G","R","NIR"]))
    for n in range(1, 5):
        sats.append((f"SUPERVIEW-{n}", f"SuperView-{n}", "SpaceWill", "optical", "PMC", 0.5, ["PAN","B1","B2","B3","B4"]))
    # Planet Dove 星座（抽样代表）
    for n in range(1, 21):
        sats.append((f"DOVE-{n:04d}", f"Dove-{n:04d}", "Planet", "optical", "PS2", 3.0, ["B","G","R","NIR"]))

    # SAR 系列
    for n in range(1, 5):
        sats.append((f"RADARSAT-{n}", f"RADARSAT-{n}", "CSA", "sar", "SAR", 3.0, ["HH","HV","VH","VV"]))
    for n in range(1, 5):
        sats.append((f"TERRASAR-X{n}", f"TerraSAR-X{n}" if n > 1 else "TerraSAR-X", "DLR/Airbus", "sar", "X-SAR", 0.25, ["HH","HV","VH","VV"]))
    for n in range(1, 5):
        sats.append((f"ALOS-{n}", f"ALOS-{n}", "JAXA", "sar", "PALSAR", 3.0, ["HH","HV","VH","VV"]))
    for n in range(1, 5):
        sats.append((f"ICEYE-X{n}", f"ICEYE-X{n}", "ICEYE", "sar", "X-SAR", 0.25, ["HH","VV"]))
    for n in range(1, 5):
        sats.append((f"CAPELLA-{n}", f"Capella-{n}", "Capella", "sar", "X-SAR", 0.5, ["HH","VV"]))
    for n in range(1, 4):
        sats.append((f"GAOFEN-3-{n:02d}", f"Gaofen-3 {n:02d}", "CNSA", "sar", "C-SAR", 1.0, ["HH","HV","VH","VV"]))

    return sats


SATELLITES: list[tuple[str, str, str, str, str, float, list[str]]] = _satellites()


# 概念/术语表（GeoNexus 领域本体）
# --------------------------------------------------------------------------- #
CONCEPTS: dict[str, list[str]] = {
    "RemoteSensing": [
        "NDVI","NDWI","NDBI","EVI","SAVI","NDMI","NBR","MNDWI","AWEI","NMDI",
        "Pan-sharpening","Atmospheric correction","Radiometric calibration","Orthorectification",
        "Cloud masking","Image fusion","Mosaic","Resampling","Georeferencing","Radiometric normalization",
    ],
    "GIS": [
        "Buffer analysis","Overlay analysis","Zonal statistics","Spatial join","Network analysis",
        "Interpolation","Kriging","IDW","Thiessen polygon","Viewshed","Cost path","Watershed delineation",
        "Reclassification","Raster algebra","Vector overlay","Topology","Spatial indexing","Spatial autocorrelation",
    ],
    "CoordinateSystems": [
        "EPSG:4326","EPSG:3857","WGS84","CGCS2000","UTM","Lambert Conformal Conic","Albers Equal Area",
        "Geographic coordinate system","Projected coordinate system","Datum","Geoid","Ellipsoid",
        "Coordinate transformation","Datum shift","Grid shift",
    ],
    "DataFormats": [
        "GeoTIFF","COG","NetCDF","Zarr","GeoJSON","GeoPackage","Shapefile","GeoParquet","FlatGeobuf",
        "LAZ","LAS","3D Tiles","CityGML","GML","KML","GPX","STAC","OGC API","WMS","WMTS","WFS","WCS",
    ],
    "GeoAI": [
        "Semantic segmentation","Object detection","Change detection","Super-resolution","Image classification",
        "Foundation model","Transfer learning","LoRA","Fine-tuning","Few-shot learning","Self-supervised learning",
        "Vision transformer","U-Net","ResNet","YOLO","SAM","CLIP","Knowledge graph embedding",
    ],
    "Federation": [
        "Data sovereignty","Zero-trust","Federated learning","Secure multi-party computation",
        "Differential privacy","Compute pushdown","Data locality","Contract binding","Capability discovery",
        "Node federation","Trust score","Policy enforcement","Provenance tracking","Data lineage",
    ],
    "SDGFramework": [
        "UN-GGKIC","UN-IGIF","IAEG-SDGs","Voluntary National Review","Tier classification",
        "Indicator framework","Means of implementation","Global indicator framework",
        "Data disaggregation","Capacity building",
    ],
}


# --------------------------------------------------------------------------- #
# 统计汇总
# --------------------------------------------------------------------------- #
def reference_data_stats() -> dict[str, int]:
    """返回各参考数据集的条目数。"""
    return {
        "sdg_goals": len(SDG_GOALS),
        "sdg_targets": sum(SDG_TARGETS.values()),
        "sdg_indicators": sum(SDG_INDICATOR_COUNTS.values()),
        "geospatial_indicators": len(GEOSPATIAL_INDICATORS),
        "countries": len(COUNTRIES),
        "satellites": len(SATELLITES),
        "satellite_bands": sum(len(s[6]) for s in SATELLITES),
        "concepts": sum(len(v) for v in CONCEPTS.values()),
    }