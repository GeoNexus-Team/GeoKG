"""GeoKG 参考数据集 — 权威结构化数据，用于知识图谱批量灌数。

数据来源：
- UN SDG 框架：17 目标 / 169 具体目标 / 231 唯一指标（联合国官方编号体系）
- ISO 3166-1：249 个国家与地区（含 ISO3 / 大区 / 次区域）
- 对地观测卫星目录：主要光学与 SAR 卫星（含载荷与波段）
- 行政区划：主要国家一级行政区（GADM level-1 结构）

说明：本模块只收录结构性事实数据（框架、编号、名称、层级），不含
任何观测值。观测数据必须来自真实数据源（Sentinel Hub / OSM / 统计库）。
"""

from __future__ import annotations

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
def _countries() -> list[tuple[str, str, str, str]]:
    """返回 ISO 3166-1 国家列表（按大区分组）。"""
    data: list[tuple[str, str, str, str]] = [
        # Africa (54)
        ("DZA", "Algeria", "Africa", "Northern Africa"),
        ("EGY", "Egypt", "Africa", "Northern Africa"),
        ("LBY", "Libya", "Africa", "Northern Africa"),
        ("MAR", "Morocco", "Africa", "Northern Africa"),
        ("SDN", "Sudan", "Africa", "Northern Africa"),
        ("TUN", "Tunisia", "Africa", "Northern Africa"),
        ("ESH", "Western Sahara", "Africa", "Northern Africa"),
        ("BDI", "Burundi", "Africa", "Eastern Africa"),
        ("COM", "Comoros", "Africa", "Eastern Africa"),
        ("DJI", "Djibouti", "Africa", "Eastern Africa"),
        ("ERI", "Eritrea", "Africa", "Eastern Africa"),
        ("ETH", "Ethiopia", "Africa", "Eastern Africa"),
        ("KEN", "Kenya", "Africa", "Eastern Africa"),
        ("MDG", "Madagascar", "Africa", "Eastern Africa"),
        ("MWI", "Malawi", "Africa", "Eastern Africa"),
        ("MUS", "Mauritius", "Africa", "Eastern Africa"),
        ("MYT", "Mayotte", "Africa", "Eastern Africa"),
        ("MOZ", "Mozambique", "Africa", "Eastern Africa"),
        ("REU", "Réunion", "Africa", "Eastern Africa"),
        ("RWA", "Rwanda", "Africa", "Eastern Africa"),
        ("SYC", "Seychelles", "Africa", "Eastern Africa"),
        ("SOM", "Somalia", "Africa", "Eastern Africa"),
        ("SSD", "South Sudan", "Africa", "Eastern Africa"),
        ("UGA", "Uganda", "Africa", "Eastern Africa"),
        ("TZA", "United Republic of Tanzania", "Africa", "Eastern Africa"),
        ("ZMB", "Zambia", "Africa", "Eastern Africa"),
        ("ZWE", "Zimbabwe", "Africa", "Eastern Africa"),
        ("AGO", "Angola", "Africa", "Middle Africa"),
        ("CMR", "Cameroon", "Africa", "Middle Africa"),
        ("CAF", "Central African Republic", "Africa", "Middle Africa"),
        ("TCD", "Chad", "Africa", "Middle Africa"),
        ("COG", "Congo", "Africa", "Middle Africa"),
        ("COD", "Democratic Republic of the Congo", "Africa", "Middle Africa"),
        ("GNQ", "Equatorial Guinea", "Africa", "Middle Africa"),
        ("GAB", "Gabon", "Africa", "Middle Africa"),
        ("STP", "Sao Tome and Principe", "Africa", "Middle Africa"),
        ("BWA", "Botswana", "Africa", "Southern Africa"),
        ("SWZ", "Eswatini", "Africa", "Southern Africa"),
        ("LSO", "Lesotho", "Africa", "Southern Africa"),
        ("NAM", "Namibia", "Africa", "Southern Africa"),
        ("ZAF", "South Africa", "Africa", "Southern Africa"),
        ("BEN", "Benin", "Africa", "Western Africa"),
        ("BFA", "Burkina Faso", "Africa", "Western Africa"),
        ("CPV", "Cabo Verde", "Africa", "Western Africa"),
        ("CIV", "Côte d'Ivoire", "Africa", "Western Africa"),
        ("GMB", "Gambia", "Africa", "Western Africa"),
        ("GHA", "Ghana", "Africa", "Western Africa"),
        ("GIN", "Guinea", "Africa", "Western Africa"),
        ("GNB", "Guinea-Bissau", "Africa", "Western Africa"),
        ("LBR", "Liberia", "Africa", "Western Africa"),
        ("MLI", "Mali", "Africa", "Western Africa"),
        ("MRT", "Mauritania", "Africa", "Western Africa"),
        ("NER", "Niger", "Africa", "Western Africa"),
        ("NGA", "Nigeria", "Africa", "Western Africa"),
        ("SHN", "Saint Helena", "Africa", "Western Africa"),
        ("SEN", "Senegal", "Africa", "Western Africa"),
        ("SLE", "Sierra Leone", "Africa", "Western Africa"),
        ("TGO", "Togo", "Africa", "Western Africa"),
        # Asia (48+)
        ("KAZ", "Kazakhstan", "Asia", "Central Asia"),
        ("KGZ", "Kyrgyzstan", "Asia", "Central Asia"),
        ("TJK", "Tajikistan", "Asia", "Central Asia"),
        ("TKM", "Turkmenistan", "Asia", "Central Asia"),
        ("UZB", "Uzbekistan", "Asia", "Central Asia"),
        ("CHN", "China", "Asia", "Eastern Asia"),
        ("HKG", "China, Hong Kong SAR", "Asia", "Eastern Asia"),
        ("MAC", "China, Macao SAR", "Asia", "Eastern Asia"),
        ("PRK", "Democratic People's Republic of Korea", "Asia", "Eastern Asia"),
        ("JPN", "Japan", "Asia", "Eastern Asia"),
        ("MNG", "Mongolia", "Asia", "Eastern Asia"),
        ("KOR", "Republic of Korea", "Asia", "Eastern Asia"),
        ("TWN", "Taiwan", "Asia", "Eastern Asia"),
        ("BRN", "Brunei Darussalam", "Asia", "South-eastern Asia"),
        ("KHM", "Cambodia", "Asia", "South-eastern Asia"),
        ("IDN", "Indonesia", "Asia", "South-eastern Asia"),
        ("LAO", "Lao People's Democratic Republic", "Asia", "South-eastern Asia"),
        ("MYS", "Malaysia", "Asia", "South-eastern Asia"),
        ("MMR", "Myanmar", "Asia", "South-eastern Asia"),
        ("PHL", "Philippines", "Asia", "South-eastern Asia"),
        ("SGP", "Singapore", "Asia", "South-eastern Asia"),
        ("THA", "Thailand", "Asia", "South-eastern Asia"),
        ("TLS", "Timor-Leste", "Asia", "South-eastern Asia"),
        ("VNM", "Viet Nam", "Asia", "South-eastern Asia"),
        ("AFG", "Afghanistan", "Asia", "Southern Asia"),
        ("BGD", "Bangladesh", "Asia", "Southern Asia"),
        ("BTN", "Bhutan", "Asia", "Southern Asia"),
        ("IND", "India", "Asia", "Southern Asia"),
        ("IRN", "Iran (Islamic Republic of)", "Asia", "Southern Asia"),
        ("MDV", "Maldives", "Asia", "Southern Asia"),
        ("NPL", "Nepal", "Asia", "Southern Asia"),
        ("PAK", "Pakistan", "Asia", "Southern Asia"),
        ("LKA", "Sri Lanka", "Asia", "Southern Asia"),
        ("ARM", "Armenia", "Asia", "Western Asia"),
        ("AZE", "Azerbaijan", "Asia", "Western Asia"),
        ("BHR", "Bahrain", "Asia", "Western Asia"),
        ("CYP", "Cyprus", "Asia", "Western Asia"),
        ("GEO", "Georgia", "Asia", "Western Asia"),
        ("IRQ", "Iraq", "Asia", "Western Asia"),
        ("ISR", "Israel", "Asia", "Western Asia"),
        ("JOR", "Jordan", "Asia", "Western Asia"),
        ("KWT", "Kuwait", "Asia", "Western Asia"),
        ("LBN", "Lebanon", "Asia", "Western Asia"),
        ("OMN", "Oman", "Asia", "Western Asia"),
        ("QAT", "Qatar", "Asia", "Western Asia"),
        ("SAU", "Saudi Arabia", "Asia", "Western Asia"),
        ("PSE", "State of Palestine", "Asia", "Western Asia"),
        ("SYR", "Syrian Arab Republic", "Asia", "Western Asia"),
        ("TUR", "Türkiye", "Asia", "Western Asia"),
        ("ARE", "United Arab Emirates", "Asia", "Western Asia"),
        ("YEM", "Yemen", "Asia", "Western Asia"),
        # Europe (44)
        ("BLR", "Belarus", "Europe", "Eastern Europe"),
        ("BGR", "Bulgaria", "Europe", "Eastern Europe"),
        ("CZE", "Czechia", "Europe", "Eastern Europe"),
        ("HUN", "Hungary", "Europe", "Eastern Europe"),
        ("POL", "Poland", "Europe", "Eastern Europe"),
        ("MDA", "Republic of Moldova", "Europe", "Eastern Europe"),
        ("ROU", "Romania", "Europe", "Eastern Europe"),
        ("RUS", "Russian Federation", "Europe", "Eastern Europe"),
        ("SVK", "Slovakia", "Europe", "Eastern Europe"),
        ("UKR", "Ukraine", "Europe", "Eastern Europe"),
        ("DNK", "Denmark", "Europe", "Northern Europe"),
        ("EST", "Estonia", "Europe", "Northern Europe"),
        ("FRO", "Faroe Islands", "Europe", "Northern Europe"),
        ("FIN", "Finland", "Europe", "Northern Europe"),
        ("ISL", "Iceland", "Europe", "Northern Europe"),
        ("IRL", "Ireland", "Europe", "Northern Europe"),
        ("IMN", "Isle of Man", "Europe", "Northern Europe"),
        ("LVA", "Latvia", "Europe", "Northern Europe"),
        ("LTU", "Lithuania", "Europe", "Northern Europe"),
        ("NOR", "Norway", "Europe", "Northern Europe"),
        ("SWE", "Sweden", "Europe", "Northern Europe"),
        ("GBR", "United Kingdom", "Europe", "Northern Europe"),
        ("ALB", "Albania", "Europe", "Southern Europe"),
        ("AND", "Andorra", "Europe", "Southern Europe"),
        ("BIH", "Bosnia and Herzegovina", "Europe", "Southern Europe"),
        ("HRV", "Croatia", "Europe", "Southern Europe"),
        ("GIB", "Gibraltar", "Europe", "Southern Europe"),
        ("GRC", "Greece", "Europe", "Southern Europe"),
        ("ITA", "Italy", "Europe", "Southern Europe"),
        ("MLT", "Malta", "Europe", "Southern Europe"),
        ("MNE", "Montenegro", "Europe", "Southern Europe"),
        ("MKD", "North Macedonia", "Europe", "Southern Europe"),
        ("PRT", "Portugal", "Europe", "Southern Europe"),
        ("SMR", "San Marino", "Europe", "Southern Europe"),
        ("SRB", "Serbia", "Europe", "Southern Europe"),
        ("SVN", "Slovenia", "Europe", "Southern Europe"),
        ("ESP", "Spain", "Europe", "Southern Europe"),
        ("AUT", "Austria", "Europe", "Western Europe"),
        ("BEL", "Belgium", "Europe", "Western Europe"),
        ("FRA", "France", "Europe", "Western Europe"),
        ("DEU", "Germany", "Europe", "Western Europe"),
        ("LIE", "Liechtenstein", "Europe", "Western Europe"),
        ("LUX", "Luxembourg", "Europe", "Western Europe"),
        ("MCO", "Monaco", "Europe", "Western Europe"),
        ("NLD", "Netherlands", "Europe", "Western Europe"),
        ("CHE", "Switzerland", "Europe", "Western Europe"),
        # Americas (35 + 13)
        ("CAN", "Canada", "Americas", "Northern America"),
        ("BMU", "Bermuda", "Americas", "Northern America"),
        ("GRL", "Greenland", "Americas", "Northern America"),
        ("SPM", "Saint Pierre and Miquelon", "Americas", "Northern America"),
        ("USA", "United States of America", "Americas", "Northern America"),
        ("BLZ", "Belize", "Americas", "Central America"),
        ("CRI", "Costa Rica", "Americas", "Central America"),
        ("SLV", "El Salvador", "Americas", "Central America"),
        ("GTM", "Guatemala", "Americas", "Central America"),
        ("HND", "Honduras", "Americas", "Central America"),
        ("MEX", "Mexico", "Americas", "Central America"),
        ("NIC", "Nicaragua", "Americas", "Central America"),
        ("PAN", "Panama", "Americas", "Central America"),
        ("ARG", "Argentina", "Americas", "South America"),
        ("BOL", "Bolivia (Plurinational State of)", "Americas", "South America"),
        ("BRA", "Brazil", "Americas", "South America"),
        ("CHL", "Chile", "Americas", "South America"),
        ("COL", "Colombia", "Americas", "South America"),
        ("ECU", "Ecuador", "Americas", "South America"),
        ("FLK", "Falkland Islands", "Americas", "South America"),
        ("GUF", "French Guiana", "Americas", "South America"),
        ("GUY", "Guyana", "Americas", "South America"),
        ("PRY", "Paraguay", "Americas", "South America"),
        ("PER", "Peru", "Americas", "South America"),
        ("SUR", "Suriname", "Americas", "South America"),
        ("URY", "Uruguay", "Americas", "South America"),
        ("VEN", "Venezuela (Bolivarian Republic of)", "Americas", "South America"),
        ("ATG", "Antigua and Barbuda", "Americas", "Caribbean"),
        ("BHS", "Bahamas", "Americas", "Caribbean"),
        ("BRB", "Barbados", "Americas", "Caribbean"),
        ("CUB", "Cuba", "Americas", "Caribbean"),
        ("DMA", "Dominica", "Americas", "Caribbean"),
        ("DOM", "Dominican Republic", "Americas", "Caribbean"),
        ("GRD", "Grenada", "Americas", "Caribbean"),
        ("HTI", "Haiti", "Americas", "Caribbean"),
        ("JAM", "Jamaica", "Americas", "Caribbean"),
        ("PRI", "Puerto Rico", "Americas", "Caribbean"),
        ("KNA", "Saint Kitts and Nevis", "Americas", "Caribbean"),
        ("LCA", "Saint Lucia", "Americas", "Caribbean"),
        ("VCT", "Saint Vincent and the Grenadines", "Americas", "Caribbean"),
        ("TTO", "Trinidad and Tobago", "Americas", "Caribbean"),
        ("ABW", "Aruba", "Americas", "Caribbean"),
        ("CUW", "Curaçao", "Americas", "Caribbean"),
        # Oceania (14 + 13)
        ("AUS", "Australia", "Oceania", "Australia and New Zealand"),
        ("NZL", "New Zealand", "Oceania", "Australia and New Zealand"),
        ("NOR_", "Norfolk Island", "Oceania", "Australia and New Zealand"),
        ("FJI", "Fiji", "Oceania", "Melanesia"),
        ("NCL", "New Caledonia", "Oceania", "Melanesia"),
        ("PNG", "Papua New Guinea", "Oceania", "Melanesia"),
        ("SLB", "Solomon Islands", "Oceania", "Melanesia"),
        ("VUT", "Vanuatu", "Oceania", "Melanesia"),
        ("FSM", "Micronesia (Federated States of)", "Oceania", "Micronesia"),
        ("GUM", "Guam", "Oceania", "Micronesia"),
        ("KIR", "Kiribati", "Oceania", "Micronesia"),
        ("MHL", "Marshall Islands", "Oceania", "Micronesia"),
        ("NRU", "Nauru", "Oceania", "Micronesia"),
        ("PLW", "Palau", "Oceania", "Micronesia"),
        ("ASM", "American Samoa", "Oceania", "Polynesia"),
        ("COK", "Cook Islands", "Oceania", "Polynesia"),
        ("PYF", "French Polynesia", "Oceania", "Polynesia"),
        ("NIU", "Niue", "Oceania", "Polynesia"),
        ("PCN", "Pitcairn", "Oceania", "Polynesia"),
        ("WSM", "Samoa", "Oceania", "Polynesia"),
        ("TKL", "Tokelau", "Oceania", "Polynesia"),
        ("TON", "Tonga", "Oceania", "Polynesia"),
        ("TUV", "Tuvalu", "Oceania", "Polynesia"),
        ("WLF", "Wallis and Futuna Islands", "Oceania", "Polynesia"),
    ]
    return [c for c in data if not c[0].endswith("_")]


COUNTRIES: list[tuple[str, str, str, str]] = _countries()


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


# --------------------------------------------------------------------------- #
# 主要国家一级行政区（GADM level-1 抽样，用于区域层级实体）
# --------------------------------------------------------------------------- #
ADMIN1_REGIONS: dict[str, list[str]] = {
    "CHN": ["Beijing","Tianjin","Hebei","Shanxi","Inner Mongolia","Liaoning","Jilin","Heilongjiang",
            "Shanghai","Jiangsu","Zhejiang","Anhui","Fujian","Jiangxi","Shandong","Henan","Hubei",
            "Hunan","Guangdong","Guangxi","Hainan","Chongqing","Sichuan","Guizhou","Yunnan","Tibet",
            "Shaanxi","Gansu","Qinghai","Ningxia","Xinjiang","Hong Kong","Macao","Taiwan"],
    "USA": ["Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware",
            "Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky",
            "Louisiana","Maine","Maryland","Massachusetts","Michigan","Minnesota","Mississippi",
            "Missouri","Montana","Nebraska","Nevada","New Hampshire","New Jersey","New Mexico",
            "New York","North Carolina","North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania",
            "Rhode Island","South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
            "Virginia","Washington","West Virginia","Wisconsin","Wyoming","District of Columbia"],
    "IND": ["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat",
            "Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh",
            "Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan",
            "Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
            "Andaman and Nicobar Islands","Chandigarh","Dadra and Nagar Haveli","Delhi","Jammu and Kashmir",
            "Ladakh","Lakshadweep","Puducherry"],
    "BRA": ["Acre","Alagoas","Amapá","Amazonas","Bahia","Ceará","Distrito Federal","Espírito Santo",
            "Goiás","Maranhão","Mato Grosso","Mato Grosso do Sul","Minas Gerais","Pará","Paraíba",
            "Paraná","Pernambuco","Piauí","Rio de Janeiro","Rio Grande do Norte","Rio Grande do Sul",
            "Rondônia","Roraima","Santa Catarina","São Paulo","Sergipe","Tocantins"],
    "ZAF": ["Eastern Cape","Free State","Gauteng","KwaZulu-Natal","Limpopo","Mpumalanga",
            "Northern Cape","North West","Western Cape"],
    "KEN": ["Baringo","Bomet","Bungoma","Busia","Elgeyo-Marakwet","Embu","Garissa","Homa Bay",
            "Isiolo","Kajiado","Kakamega","Kericho","Kiambu","Kilifi","Kirinyaga","Kisii","Kisumu",
            "Kitui","Kwale","Laikipia","Lamu","Machakos","Makueni","Mandera","Marsabit","Meru",
            "Migori","Mombasa","Murang'a","Nairobi","Nakuru","Nandi","Narok","Nyamira","Nyandarua",
            "Nyeri","Samburu","Siaya","Taita-Taveta","Tana River","Tharaka-Nithi","Trans Nzoia",
            "Turkana","Uasin Gishu","Vihiga","Wajir","West Pokot"],
    "NGA": ["Abia","Adamawa","Akwa Ibom","Anambra","Bauchi","Bayelsa","Benue","Borno","Cross River",
            "Delta","Ebonyi","Edo","Ekiti","Enugu","FCT Abuja","Gombe","Imo","Jigawa","Kaduna",
            "Kano","Katsina","Kebbi","Kogi","Kwara","Lagos","Nasarawa","Niger","Ogun","Ondo",
            "Osun","Oyo","Plateau","Rivers","Sokoto","Taraba","Yobe","Zamfara"],
    "IDN": ["Aceh","Bali","Bangka Belitung","Banten","Bengkulu","DI Yogyakarta","DKI Jakarta",
            "Gorontalo","Jambi","Jawa Barat","Jawa Tengah","Jawa Timur","Kalimantan Barat",
            "Kalimantan Selatan","Kalimantan Tengah","Kalimantan Timur","Kalimantan Utara",
            "Kepulauan Riau","Lampung","Maluku","Maluku Utara","Nusa Tenggara Barat",
            "Nusa Tenggara Timur","Papua","Papua Barat","Riau","Sulawesi Barat","Sulawesi Selatan",
            "Sulawesi Tengah","Sulawesi Tenggara","Sulawesi Utara","Sumatera Barat","Sumatera Selatan",
            "Sumatera Utara"],
    "VNM": ["An Giang","Bà Rịa-Vũng Tàu","Bắc Giang","Bắc Kạn","Bạc Liêu","Bắc Ninh","Bến Tre",
            "Bình Định","Bình Dương","Bình Phước","Bình Thuận","Cà Mau","Cao Bằng","Đắk Lắk",
            "Đắk Nông","Điện Biên","Đồng Nai","Đồng Tháp","Gia Lai","Hà Giang","Hà Nam","Hà Nội",
            "Hà Tĩnh","Hải Dương","Hải Phòng","Hậu Giang","Hòa Bình","Hưng Yên","Khánh Hòa",
            "Kiên Giang","Kon Tum","Lai Châu","Lâm Đồng","Lạng Sơn","Lào Cai","Long An","Nam Định",
            "Nghệ An","Ninh Bình","Ninh Thuận","Phú Thọ","Phú Yên","Quảng Bình","Quảng Nam",
            "Quảng Ngãi","Quảng Ninh","Quảng Trị","Sóc Trăng","Sơn La","Tây Ninh","Thái Bình",
            "Thái Nguyên","Thanh Hóa","Thừa Thiên-Huế","Tiền Giang","Trà Vinh","Tuyên Quang",
            "Vĩnh Long","Vĩnh Phúc","Yên Bái","Cần Thơ","Đà Nẵng","Hồ Chí Minh"],
    "THA": ["Amnat Charoen","Ang Thong","Bueng Kan","Buriram","Chachoengsao","Chai Nat","Chaiyaphum",
            "Chanthaburi","Chiang Mai","Chiang Rai","Chonburi","Chumphon","Kalasin","Kamphaeng Phet",
            "Kanchanaburi","Khon Kaen","Krabi","Lampang","Lamphun","Loei","Lopburi","Mae Hong Son",
            "Maha Sarakham","Mukdahan","Nakhon Nayok","Nakhon Pathom","Nakhon Phanom",
            "Nakhon Ratchasima","Nakhon Sawan","Nakhon Si Thammarat","Nan","Narathiwat",
            "Nong Bua Lamphu","Nong Khai","Nonthaburi","Pathum Thani","Pattani","Phang Nga",
            "Phatthalung","Phayao","Phetchabun","Phetchaburi","Phichit","Phitsanulok","Phra Nakhon Si Ayutthaya",
            "Phrae","Phuket","Prachinburi","Prachuap Khiri Khan","Ranong","Ratchaburi","Rayong",
            "Roi Et","Sa Kaeo","Sakon Nakhon","Samut Prakan","Samut Sakhon","Samut Songkhram",
            "Saraburi","Satun","Sing Buri","Sisaket","Songkhla","Sukhothai","Suphan Buri",
            "Surat Thani","Surin","Tak","Trang","Trat","Ubon Ratchathani","Udon Thani",
            "Uthai Thani","Uttaradit","Yala","Yasothon","Bangkok"],
    "MMR": ["Ayeyarwady","Bago","Chin","Kachin","Kayah","Kayin","Magway","Mandalay","Mon","Naypyidaw",
            "Rakhine","Sagaing","Shan","Tanintharyi","Yangon"],
    "BGD": ["Barisal","Chittagong","Dhaka","Khulna","Mymensingh","Rajshahi","Rangpur","Sylhet"],
    "PAK": ["Azad Jammu and Kashmir","Balochistan","Gilgit-Baltistan","Islamabad","Khyber Pakhtunkhwa",
            "Punjab","Sindh"],
    "EGY": ["Alexandria","Aswan","Asyut","Beheira","Beni Suef","Cairo","Dakahlia","Damietta",
            "Faiyum","Gharbia","Giza","Ismailia","Kafr El Sheikh","Luxor","Matruh","Minya",
            "Monufia","New Valley","North Sinai","Port Said","Qalyubia","Qena","Red Sea",
            "Sharqia","Sohag","South Sinai","Suez"],
    "ETH": ["Addis Ababa","Afar","Amhara","Benishangul-Gumuz","Dire Dawa","Gambela","Harari",
            "Oromia","Sidama","Somali","South West Ethiopia","Southern Nations","Tigray"],
    "TZA": ["Arusha","Dar es Salaam","Dodoma","Geita","Iringa","Kagera","Katavi","Kigoma","Kilimanjaro",
            "Lindi","Manyara","Mara","Mbeya","Morogoro","Mtwara","Mwanza","Njombe","Pemba North",
            "Pemba South","Pwani","Rukwa","Ruvuma","Shinyanga","Simiyu","Singida","Songwe","Tabora",
            "Tanga","Unguja North","Unguja South","Zanzibar Urban"],
    "GHA": ["Ahafo","Ashanti","Bono","Bono East","Central","Eastern","Greater Accra","North East",
            "Northern","Oti","Savannah","Upper East","Upper West","Volta","Western","Western North"],
    "AUS": ["Australian Capital Territory","New South Wales","Northern Territory","Queensland",
            "South Australia","Tasmania","Victoria","Western Australia"],
    "CAN": ["Alberta","British Columbia","Manitoba","New Brunswick","Newfoundland and Labrador",
            "Northwest Territories","Nova Scotia","Nunavut","Ontario","Prince Edward Island",
            "Quebec","Saskatchewan","Yukon"],
    "MEX": ["Aguascalientes","Baja California","Baja California Sur","Campeche","Chiapas","Chihuahua",
            "Ciudad de México","Coahuila","Colima","Durango","Guanajuato","Guerrero","Hidalgo",
            "Jalisco","México","Michoacán","Morelos","Nayarit","Nuevo León","Oaxaca","Puebla",
            "Querétaro","Quintana Roo","San Luis Potosí","Sinaloa","Sonora","Tabasco","Tamaulipas",
            "Tlaxcala","Veracruz","Yucatán","Zacatecas"],
    "DEU": ["Baden-Württemberg","Bayern","Berlin","Brandenburg","Bremen","Hamburg","Hessen",
            "Mecklenburg-Vorpommern","Niedersachsen","Nordrhein-Westfalen","Rheinland-Pfalz",
            "Saarland","Sachsen","Sachsen-Anhalt","Schleswig-Holstein","Thüringen"],
    "FRA": ["Auvergne-Rhône-Alpes","Bourgogne-Franche-Comté","Bretagne","Centre-Val de Loire",
            "Corse","Grand Est","Hauts-de-France","Île-de-France","Normandie",
            "Nouvelle-Aquitaine","Occitanie","Pays de la Loire","Provence-Alpes-Côte d'Azur"],
    "GBR": ["England","Scotland","Wales","Northern Ireland"],
    "RUS": ["Central","Far Eastern","North Caucasian","Northwestern","Siberian","Southern","Ural",
            "Volga"],
    "UKR": ["Cherkasy","Chernihiv","Chernivtsi","Dnipropetrovsk","Donetsk","Ivano-Frankivsk",
            "Kharkiv","Kherson","Khmelnytskyi","Kirovohrad","Kyiv","Luhansk","Lviv","Mykolaiv",
            "Odesa","Poltava","Rivne","Sumy","Ternopil","Vinnytsia","Volyn","Zakarpattia",
            "Zaporizhzhia","Zhytomyr","Crimea"],
    "IRN": ["Alborz","Ardabil","Bushehr","Chaharmahal and Bakhtiari","East Azerbaijan","Esfahan",
            "Fars","Gilan","Golestan","Hamadan","Hormozgan","Ilam","Kerman","Kermanshah",
            "Khuzestan","Kohgiluyeh and Boyer-Ahmad","Kurdistan","Lorestan","Markazi","Mazandaran",
            "North Khorasan","Qazvin","Qom","Razavi Khorasan","Semnan","Sistan and Baluchestan",
            "South Khorasan","Tehran","West Azerbaijan","Yazd","Zanjan"],
    "SAU": ["Al Bahah","Al Jawf","Al Madinah","Al Qassim","Asir","Eastern Province","Hail",
            "Jazan","Najran","Northern Borders","Riyadh","Tabuk"],
    "TUR": ["Adana","Adıyaman","Afyonkarahisar","Ağrı","Aksaray","Amasya","Ankara","Antalya",
            "Ardahan","Artvin","Aydın","Balıkesir","Bartın","Batman","Bayburt","Bilecik","Bingöl",
            "Bitlis","Bolu","Burdur","Bursa","Çanakkale","Çankırı","Çorum","Denizli","Diyarbakır",
            "Düzce","Edirne","Elazığ","Erzincan","Erzurum","Eskişehir","Gaziantep","Giresun",
            "Gümüşhane","Hakkâri","Hatay","Iğdır","Isparta","İstanbul","İzmir","Kahramanmaraş",
            "Karabük","Karaman","Kars","Kastamonu","Kayseri","Kırıkkale","Kırklareli","Kırşehir",
            "Kilis","Kocaeli","Konya","Kütahya","Malatya","Manisa","Mardin","Mersin","Muğla","Muş",
            "Nevşehir","Niğde","Ordu","Osmaniye","Rize","Sakarya","Samsun","Siirt","Sinop","Sivas",
            "Şanlıurfa","Şırnak","Tekirdağ","Tokat","Trabzon","Tunceli","Uşak","Van","Yalova",
            "Yozgat","Zonguldak"],
}


# --------------------------------------------------------------------------- #
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
        "admin1_regions": sum(len(v) for v in ADMIN1_REGIONS.values()),
        "concepts": sum(len(v) for v in CONCEPTS.values()),
    }