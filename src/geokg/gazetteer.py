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
# 4. 领域词汇扩充
# --------------------------------------------------------------------------- #
EXTENDED_CONCEPTS: dict[str, list[str]] = {
    "Sensors": [
        "MSI","OLI","TIRS","ETM+","TM","MSS","VIIRS","MODIS","AVHRR","SLSTR","OLCI","SRAL",
        "TROPOMI","IASI","AIRS","CrIS","OMPS","PALSAR","PALSAR-2","C-SAR","X-SAR","L-SAR",
        "SENTINEL-1 SAR","SENTINEL-2 MSI","SENTINEL-3 OLCI","SENTINEL-5P TROPOMI",
        "GF-1 PMC","GF-2 PMS","GF-3 SAR","GF-4 PMI","GF-5 AHSI","GF-6 PMS","GF-7 LAS",
        "ZY-3 TLC","ZY-1 AHSI","CBERS MUX","CBERS WFI","CBERS IRS","HJ-1 CCD","HJ-2 CCD",
        "WorldView-3 WV110","GeoEye-1 GIS","Pléiades HiRI","SPOT NAOMI","SkySat-C",
        "TerraSAR-X","TanDEM-X","RADARSAT-2","RCM SAR","ALOS-2 PALSAR-2","SAOCOM L-SAR",
        "KOMPSAT AESA","Cartosat PAN","RISAT C-SAR","PROBA-V Vegetation","SDGSAT GIS",
    ],
    "DataProducts": [
        "NDVI composite","EVI composite","SAVI composite","NDWI water mask","MNDWI water mask",
        "NDBI built-up","NDMI moisture","NBR burn severity","dNBR","NBR2",
        "Land cover classification","Cropland extent","Forest cover","Tree canopy height",
        "Impervious surface","Built-up area","Population grid","GDP grid","Nighttime lights",
        "Digital Elevation Model","Digital Surface Model","Canopy Height Model",
        "Slope","Aspect","Hillshade","Curvature","Flow accumulation","Watershed boundary",
        "Flood extent","Flood depth","Burn scar","Drought index","Vegetation condition index",
        "Land surface temperature","Sea surface temperature","Chlorophyll-a","Turbidity",
        "Snow cover","Ice extent","Glacier outline","Coastline","Bathymetry",
        "Surface water occurrence","Surface water seasonality","Water quality index",
    ],
    "AnalysisMethods": [
        "Supervised classification","Unsupervised classification","Random Forest","SVM",
        "Maximum likelihood","Object-based image analysis","Segmentation",
        "Change vector analysis","Post-classification comparison","CVA","Image differencing",
        "Principal component analysis","Tasseled cap transformation","Vegetation indices",
        "Spectral unmixing","Endmember extraction","Sub-pixel analysis",
        "Time series analysis","Harmonic regression","BFAST","LandTrendr","CCDC",
        "Machine learning","Deep learning","Convolutional neural network","Recurrent neural network",
        "Transformer","Attention mechanism","Transfer learning","Domain adaptation",
        "Uncertainty quantification","Cross validation","Accuracy assessment","Confusion matrix",
        "Kappa coefficient","ROC curve","Feature importance","SHAP",
    ],
    "Standards": [
        "ISO 19115","ISO 19139","ISO 19119","ISO 19136","ISO/TC 211",
        "OGC API - Features","OGC API - Coverages","OGC API - Processes",
        "OGC API - Records","OGC API - Tiles","OGC API - Maps","OGC API - EDR",
        "WMS 1.3.0","WMTS 1.0.0","WFS 2.0","WCS 2.0","CSW 3.0",
        "STAC 1.0.0","STAC API","COG specification","Zarr v3","GeoParquet 1.1",
        "CF Conventions","EPSG Geodetic Parameter Dataset","OGC GeoPackage 1.3",
        "INSPIRE Directive","CEOS-ARD","CEOS-WGISS","GEOSS","GEO DAB",
        "FAIR principles","OGC Compliance","ISO 9001","ISO 27001",
    ],
    "GeospatialConcepts": [
        "Coordinate reference system","Map projection","Geodesic","Great circle",
        "Spatial resolution","Temporal resolution","Radiometric resolution","Spectral resolution",
        "Ground sample distance","Swath width","Revisit time","Orbit inclination",
        "Sun-synchronous orbit","Geostationary orbit","Polar orbit","Equatorial crossing time",
        "Nadir","Off-nadir","Incidence angle","Azimuth angle","Elevation angle",
        "Atmospheric window","Signal-to-noise ratio","Radiometric calibration coefficient",
        "Top of atmosphere reflectance","Surface reflectance","Brightness temperature",
        "Digital number","Bit depth","Dynamic range","Saturation",
        "Spatial autocorrelation","Moran's I","Geary's C","Variogram","Semivariance",
        "Scale effect","Modifiable areal unit problem","Ecological fallacy",
        "Edge effect","Boundary effect","Mixed pixel","Point spread function",
    ],
    "DisasterRisk": [
        "Hazard","Exposure","Vulnerability","Risk","Resilience","Adaptive capacity",
        "Sendai Framework","Early warning system","Rapid mapping","Damage assessment",
        "Emergency response","Post-disaster recovery","Disaster risk reduction",
        "Flood hazard map","Landslide susceptibility","Wildfire risk","Drought risk",
        "Cyclone track","Storm surge","Tsunami inundation","Earthquake intensity",
    ],
    "PolicyFrameworks": [
        "2030 Agenda","Paris Agreement","Sendai Framework","New Urban Agenda",
        "Kunming-Montreal Global Biodiversity Framework","UNCCD","UNFCCC","Ramsar Convention",
        "World Heritage Convention","UN-GGKIC","UN-IGIF","IGIF Nine Strategic Pathways",
        "Voluntary National Review","Voluntary Local Review","Data for Now",
        "Global Statistical Geospatial Framework","Integrated Geospatial Information Framework",
    ],
}


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
def expansion_stats() -> dict[str, int]:
    """返回扩充数据的条目数统计（一级行政区已改由 GeoNames 提供，不计入本模块）。"""
    concepts = sum(len(v) for v in EXTENDED_CONCEPTS.values())
    return {
        "extended_concepts": concepts,
        "monitored_indicators": len(MONITORED_INDICATORS),
        "required_input_types": len(REQUIRED_INPUTS),
    }