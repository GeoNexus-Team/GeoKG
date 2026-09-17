#!/usr/bin/env python
"""构建 GeoKG 术语表（原 CONCEPTS + EXTENDED_CONCEPTS）并逐类标注来源。

## 为什么需要分类标注

审计发现 371 条术语**没有任何来源标注**。但把它们一概称为"来源未核实"
并不准确——它们的性质其实分三种，混在一起才是问题所在：

1. **外部数据集**（如仪器名、EPSG 代码、标准编号）——必须引用外部来源，
   且应当尽量换成权威数据源；
2. **我们自己编的术语表**（如"缓冲区分析""坐标参考系"）——来源**就是我们**，
   标注为 ``geokg-authored`` 才是准确的说法，而不是"缺来源"；
3. **已被其他层取代的**（如灾害术语）——删除，避免重复且口径不一。

因此本脚本给每条术语打上 ``source_id``，并按下表分派：

| 类别 | 来源 | 说明 |
|------|------|------|
| Sensors | **移除** | 改由 WMO OSCAR/Space 仪器目录提供（1,000+ 台，T2） |
| DisasterRisk | **移除** | 已由 IRDR 灾害分类（L3）覆盖 |
| CoordinateSystems | ``iogp-epsg`` | EPSG 代码属 IOGP |
| Standards | ``iso-ogc-standards`` | 标准编号属 ISO / OGC |
| PolicyFrameworks / SDGFramework | ``un-frameworks`` | 联合国文件 |
| 其余 9 类 | ``geokg-authored`` | **本仓库自编术语表**（Apache-2.0） |

⚠️ 最后一类是关键：把它标成 ``geokg-authored`` 表示"这是我们的编辑内容"，
而不是"我们不知道它从哪来"。这是**如实分类**，不是免除引用义务——
任何从外部数据集提取的内容都不在此列。

用法::

    python scripts/build_vocabulary.py [--check]
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "geokg" / "data" / "vocabulary.tsv"

COLUMNS = ["source_id", "category", "term"]

#: 类别 → 来源。未列出者一律视为本仓库自编术语表。
CATEGORY_SOURCE: dict[str, str] = {
    "CoordinateSystems": "iogp-epsg",
    "Standards": "iso-ogc-standards",
    "PolicyFrameworks": "un-frameworks",
    "SDGFramework": "un-frameworks",
}

#: 已被权威数据源取代、因此从术语表中移除的类别
SUPERSEDED: dict[str, str] = {
    "Sensors": "改由 WMO OSCAR/Space 仪器目录提供（见 geokg.instruments）",
    "DisasterRisk": "已由 IRDR 灾害分类覆盖（见 L3 本体）",
}

AUTHORED = "geokg-authored"


#: 术语数据（**脚本自身即权威记录**）。
#:
#: 原先从 ``reference_data.CONCEPTS`` / ``gazetteer.EXTENDED_CONCEPTS`` 读取，
#: 但那是**一次性迁移**——常量已随重构删除，脚本便再也跑不动。
#: 现把数据内联在脚本里，与 ``build_l3_ontology.py`` 同样的做法：
#: 转录/迁移的权威记录就是脚本本身，``--check`` 才有意义。
#: 每项为 (source_id, category, [term, ...])。
VOCABULARY: list[tuple[str, str, list[str]]] = [
    ("geokg-authored", "AnalysisMethods", [
        "Accuracy assessment", "Attention mechanism", "BFAST", "CCDC",
        "CVA", "Change vector analysis", "Confusion matrix", "Convolutional neural network",
        "Cross validation", "Deep learning", "Domain adaptation", "Endmember extraction",
        "Feature importance", "Harmonic regression", "Image differencing", "Kappa coefficient",
        "LandTrendr", "Machine learning", "Maximum likelihood", "Object-based image analysis",
        "Post-classification comparison", "Principal component analysis", "ROC curve", "Random Forest",
        "Recurrent neural network", "SHAP", "SVM", "Segmentation",
        "Spectral unmixing", "Sub-pixel analysis", "Supervised classification", "Tasseled cap transformation",
        "Time series analysis", "Transfer learning", "Transformer", "Uncertainty quantification",
        "Unsupervised classification", "Vegetation indices",
    ]),
    ("geokg-authored", "DataFormats", [
        "3D Tiles", "COG", "CityGML", "FlatGeobuf",
        "GML", "GPX", "GeoJSON", "GeoPackage",
        "GeoParquet", "GeoTIFF", "KML", "LAS",
        "LAZ", "NetCDF", "OGC API", "STAC",
        "Shapefile", "WCS", "WFS", "WMS",
        "WMTS", "Zarr",
    ]),
    ("geokg-authored", "DataProducts", [
        "Aspect", "Bathymetry", "Built-up area", "Burn scar",
        "Canopy Height Model", "Chlorophyll-a", "Coastline", "Cropland extent",
        "Curvature", "Digital Elevation Model", "Digital Surface Model", "Drought index",
        "EVI composite", "Flood depth", "Flood extent", "Flow accumulation",
        "Forest cover", "GDP grid", "Glacier outline", "Hillshade",
        "Ice extent", "Impervious surface", "Land cover classification", "Land surface temperature",
        "MNDWI water mask", "NBR burn severity", "NBR2", "NDBI built-up",
        "NDMI moisture", "NDVI composite", "NDWI water mask", "Nighttime lights",
        "Population grid", "SAVI composite", "Sea surface temperature", "Slope",
        "Snow cover", "Surface water occurrence", "Surface water seasonality", "Tree canopy height",
        "Turbidity", "Vegetation condition index", "Water quality index", "Watershed boundary",
        "dNBR",
    ]),
    ("geokg-authored", "Federation", [
        "Capability discovery", "Compute pushdown", "Contract binding", "Data lineage",
        "Data locality", "Data sovereignty", "Differential privacy", "Federated learning",
        "Node federation", "Policy enforcement", "Provenance tracking", "Secure multi-party computation",
        "Trust score", "Zero-trust",
    ]),
    ("geokg-authored", "GIS", [
        "Buffer analysis", "Cost path", "IDW", "Interpolation",
        "Kriging", "Network analysis", "Overlay analysis", "Raster algebra",
        "Reclassification", "Spatial autocorrelation", "Spatial indexing", "Spatial join",
        "Thiessen polygon", "Topology", "Vector overlay", "Viewshed",
        "Watershed delineation", "Zonal statistics",
    ]),
    ("geokg-authored", "GeoAI", [
        "CLIP", "Change detection", "Few-shot learning", "Fine-tuning",
        "Foundation model", "Image classification", "Knowledge graph embedding", "LoRA",
        "Object detection", "ResNet", "SAM", "Self-supervised learning",
        "Semantic segmentation", "Super-resolution", "Transfer learning", "U-Net",
        "Vision transformer", "YOLO",
    ]),
    ("geokg-authored", "GeospatialConcepts", [
        "Atmospheric window", "Azimuth angle", "Bit depth", "Boundary effect",
        "Brightness temperature", "Coordinate reference system", "Digital number", "Dynamic range",
        "Ecological fallacy", "Edge effect", "Elevation angle", "Equatorial crossing time",
        "Geary's C", "Geodesic", "Geostationary orbit", "Great circle",
        "Ground sample distance", "Incidence angle", "Map projection", "Mixed pixel",
        "Modifiable areal unit problem", "Moran's I", "Nadir", "Off-nadir",
        "Orbit inclination", "Point spread function", "Polar orbit", "Radiometric calibration coefficient",
        "Radiometric resolution", "Revisit time", "Saturation", "Scale effect",
        "Semivariance", "Signal-to-noise ratio", "Spatial autocorrelation", "Spatial resolution",
        "Spectral resolution", "Sun-synchronous orbit", "Surface reflectance", "Swath width",
        "Temporal resolution", "Top of atmosphere reflectance", "Variogram",
    ]),
    ("geokg-authored", "RemoteSensing", [
        "AWEI", "Atmospheric correction", "Cloud masking", "EVI",
        "Georeferencing", "Image fusion", "MNDWI", "Mosaic",
        "NBR", "NDBI", "NDMI", "NDVI",
        "NDWI", "NMDI", "Orthorectification", "Pan-sharpening",
        "Radiometric calibration", "Radiometric normalization", "Resampling", "SAVI",
    ]),
    ("iogp-epsg", "CoordinateSystems", [
        "Albers Equal Area", "CGCS2000", "Coordinate transformation", "Datum",
        "Datum shift", "EPSG:3857", "EPSG:4326", "Ellipsoid",
        "Geographic coordinate system", "Geoid", "Grid shift", "Lambert Conformal Conic",
        "Projected coordinate system", "UTM", "WGS84",
    ]),
    ("iso-ogc-standards", "Standards", [
        "CEOS-ARD", "CEOS-WGISS", "CF Conventions", "COG specification",
        "CSW 3.0", "EPSG Geodetic Parameter Dataset", "FAIR principles", "GEO DAB",
        "GEOSS", "GeoParquet 1.1", "INSPIRE Directive", "ISO 19115",
        "ISO 19119", "ISO 19136", "ISO 19139", "ISO 27001",
        "ISO 9001", "ISO/TC 211", "OGC API - Coverages", "OGC API - EDR",
        "OGC API - Features", "OGC API - Maps", "OGC API - Processes", "OGC API - Records",
        "OGC API - Tiles", "OGC Compliance", "OGC GeoPackage 1.3", "STAC 1.0.0",
        "STAC API", "WCS 2.0", "WFS 2.0", "WMS 1.3.0",
        "WMTS 1.0.0", "Zarr v3",
    ]),
    ("un-frameworks", "PolicyFrameworks", [
        "2030 Agenda", "Data for Now", "Global Statistical Geospatial Framework", "IGIF Nine Strategic Pathways",
        "Integrated Geospatial Information Framework", "Kunming-Montreal Global Biodiversity Framework", "New Urban Agenda", "Paris Agreement",
        "Ramsar Convention", "Sendai Framework", "UN-GGKIC", "UN-IGIF",
        "UNCCD", "UNFCCC", "Voluntary Local Review", "Voluntary National Review",
        "World Heritage Convention",
    ]),
    ("un-frameworks", "SDGFramework", [
        "Capacity building", "Data disaggregation", "Global indicator framework", "IAEG-SDGs",
        "Indicator framework", "Means of implementation", "Tier classification", "UN-GGKIC",
        "UN-IGIF", "Voluntary National Review",
    ]),
]


def _collect() -> list[list[str]]:
    """由内联数据生成行（source, category, term）。"""
    rows: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for source_id, category, terms in VOCABULARY:
        for term in terms:
            key = (category, term)
            if key in seen:
                raise ValueError(f"术语重复: {category}/{term}")
            seen.add(key)
            rows.append([source_id, category, term])
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


def render(rows: list[list[str]]) -> str:
    from collections import Counter
    by_src = Counter(r[0] for r in rows)
    header = (
        "# GeoKG 术语表（原 CONCEPTS + EXTENDED_CONCEPTS）\n"
        "# 生成: python scripts/build_vocabulary.py   —— 请勿手工编辑\n"
        "#\n"
        "# 逐类标注来源。'geokg-authored' 表示这是**本仓库自编术语表**\n"
        "# （Apache-2.0），而非从外部数据集提取——这是如实分类，不是免除引用。\n"
        "# 外部来源：\n"
        "#   iogp-epsg          EPSG 代码属 IOGP（T1）\n"
        "#   iso-ogc-standards  标准编号属 ISO / OGC（T1）\n"
        "#   un-frameworks      联合国文件（T2）\n"
        "# 每行 3 列，制表符分隔: " + "\t".join(COLUMNS) + "\n"
        "#\n"
        "# 条目数按来源: " + ", ".join(f"{k}={v}" for k, v in sorted(by_src.items())) + "\n"
    )
    return header + "\n".join("\t".join(r) for r in rows) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    rows = _collect()
    text = render(rows)

    if args.check:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            print(f"  ✅ 与磁盘一致（{len(rows)} 条）")
            return 0
        print("  ⚠️ 与磁盘不一致")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"  ✅ 已写入 {OUT.name}（{len(rows)} 条, {OUT.stat().st_size:,} bytes）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
