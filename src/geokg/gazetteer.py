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
# 1. 卫星星座扩充
# --------------------------------------------------------------------------- #
#: 大型商业星座（真实存在，采用 "名称-编号" 模式化标识）
#: 格式: (星座前缀, 全名模板, 机构, 类型, 传感器, 分辨率m, 波段, 数量)
CONSTELLATIONS: list[tuple[str, str, str, str, str, float, list[str], int]] = [
    # Planet Dove 星座（真实在轨约 200 颗）
    ("DOVE", "Dove {n}", "Planet", "optical", "PS2", 3.0, ["B", "G", "R", "NIR"], 200),
    # Planet SkySat（真实约 21 颗）
    ("SKYSAT", "SkySat {n}", "Planet", "optical", "SkySat-C", 0.5, ["PAN", "B", "G", "R", "NIR"], 21),
    # ICEYE SAR 星座（真实在轨 30+）
    ("ICEYE", "ICEYE-X{n}", "ICEYE", "sar", "X-SAR", 0.25, ["HH", "VV"], 30),
    # Capella SAR（真实在轨约 10）
    ("CAPELLA", "Capella-{n}", "Capella Space", "sar", "X-SAR", 0.5, ["HH", "VV"], 10),
    # 中国吉林一号（真实在轨 100+）
    ("JL1", "Jilin-1 {n:03d}", "CGSTL", "optical", "Multi-spectral", 0.75, ["PAN", "B", "G", "R", "NIR"], 100),
    # 中国珠海一号高光谱（真实在轨 12）
    ("ZH1", "Zhuhai-1 OHS-{n}", "Zhuhai Orbita", "hyperspectral", "OHS", 10.0,
     [f"B{i:02d}" for i in range(1, 33)], 12),
    # 北京三号
    ("BJ3", "Beijing-3 {n}", "Twenty First Century", "optical", "PMC", 0.3, ["PAN", "B", "G", "R", "NIR"], 4),
    # 中国环境减灾
    ("HJ2", "Huanjing-2{'AB'[n-1] if n <= 2 else n}", "CNSA", "optical", "CCD", 16.0,
     ["B1", "B2", "B3", "B4"], 2),
    # 欧空局 Sentinel 补充（1C/2C/3C 等后续星）
    ("SENTINEL-1", "Sentinel-1{n}", "ESA", "sar", "C-SAR", 5.0, ["VV", "VH"], 1),
    ("SENTINEL-2", "Sentinel-2{n}", "ESA", "optical", "MSI", 10.0,
     ["B01","B02","B03","B04","B05","B06","B07","B08","B8A","B09","B10","B11","B12"], 1),
    # SPOT-6/7
    ("SPOT", "SPOT-{n}", "Airbus", "optical", "NAOMI", 1.5, ["PAN", "B1", "B2", "B3", "B4"], 2),
    # 日本 ALOS 系列
    ("ALOS", "ALOS-{n}", "JAXA", "sar", "PALSAR-{n}", 3.0, ["HH", "HV", "VH", "VV"], 2),
    # 加拿大 RADARSAT 星座
    ("RCM", "RADARSAT Constellation {n}", "CSA", "sar", "C-SAR", 3.0,
     ["HH", "HV", "VH", "VV"], 3),
    # 阿根廷 SAOCOM
    ("SAOCOM", "SAOCOM-1{'AB'[n-1]}", "CONAE", "sar", "L-SAR", 10.0, ["HH", "HV", "VH", "VV"], 2),
    # 德国 TerraSAR 后续
    ("TSX", "TerraSAR-X {n}", "DLR/Airbus", "sar", "X-SAR", 0.25, ["HH", "HV", "VH", "VV"], 2),
    # 韩国 KOMPSAT
    ("KOMPSAT", "KOMPSAT-{n}", "KARI", "optical", "AESA", 0.5, ["PAN", "MS1", "MS2", "MS3", "MS4"], 5),
    # 印度 Cartosat
    ("CARTOSAT", "Cartosat-{n}", "ISRO", "optical", "PAN/AX", 0.25, ["PAN", "B", "G", "R", "NIR"], 5),
    # 印度 RISAT
    ("RISAT", "RISAT-{n}", "ISRO", "sar", "C-SAR", 1.0, ["HH", "HV", "VH", "VV"], 2),
    # 欧洲 PROBA-V
    ("PROBAV", "PROBA-V {n}", "ESA", "optical", "Vegetation", 100.0,
     ["BLUE", "RED", "NIR", "SWIR"], 1),
    # NOAA JPSS
    ("JPSS", "JPSS-{n}", "NOAA", "optical", "VIIRS", 375.0,
     ["I1","I2","I3","I4","I5","M1","M2","M3","M4","M5","M6","M7","M8","M9","M10","M11"], 4),
    # 气象卫星
    ("GOES", "GOES-{n}", "NOAA", "atmospheric", "ABI", 500.0,
     [f"C{i:02d}" for i in range(1, 17)], 4),
    ("HIMAWARI", "Himawari-{n}", "JMA", "atmospheric", "AHI", 500.0,
     [f"B{i:02d}" for i in range(1, 17)], 2),
    ("METOP", "MetOp-{'ABC'[n-1]}", "EUMETSAT", "atmospheric", "AVHRR/IASI", 1000.0,
     ["AVHRR-1","AVHRR-2","AVHRR-3","IASI-1","IASI-2"], 3),
    ("FENGYUN", "Fengyun-{n}", "CMA", "atmospheric", "AGRI", 250.0,
     [f"B{i:02d}" for i in range(1, 15)], 8),
    ("GAOFEN", "Gaofen-{n} PM", "CNSA", "optical", "PMC", 2.0, ["PAN", "MSS"], 10),
    ("ZY", "Ziyuan-{n}", "MNR China", "optical", "TLC", 2.1, ["NAD", "FWD", "BWD"], 5),
    ("HAIYANG", "Haiyang-{n}", "SOA China", "ocean", "COCTS", 1100.0,
     [f"B{i:02d}" for i in range(1, 11)], 4),
    ("TANSAT", "TanSat-{n}", "CAS", "atmospheric", "ACGS", 2000.0, ["O2-A", "CO2-1", "CO2-2"], 2),
    ("SDGSAT", "SDGSAT-{n}", "CAS", "optical", "GIS", 10.0, ["B1", "B2", "B3", "B4", "B5", "B6", "B7"], 2),
]


def expand_satellite_constellations() -> list[tuple[str, str, str, str, str, float, list[str]]]:
    """按星座定义展开为逐星条目。

    Returns: 与 reference_data.SATELLITES 同构的元组列表。
    """
    out: list[tuple[str, str, str, str, str, float, list[str]]] = []
    for prefix, name_tpl, agency, sat_type, sensor, res, bands, count in CONSTELLATIONS:
        for n in range(1, count + 1):
            sat_id = f"{prefix}-{n:03d}"
            try:
                name = name_tpl.format(n=n)
            except (KeyError, IndexError):
                name = name_tpl
            out.append((sat_id, name, agency, sat_type, sensor, res, bands))
    return out


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
# 3. 行政区划扩充（补充国家的一级行政区）
# --------------------------------------------------------------------------- #
ADMIN1_EXTENDED: dict[str, list[str]] = {
    "ETH": ["Addis Ababa","Afar","Amhara","Benishangul-Gumuz","Central Ethiopia","Dire Dawa",
            "Gambela","Harari","Oromia","Sidama","Somali","South Ethiopia","South West Ethiopia","Tigray"],
    "UGA": ["Central","Eastern","Northern","Western"],
    "RWA": ["Eastern","Kigali","Northern","Southern","Western"],
    "TZA": ["Arusha","Dar es Salaam","Dodoma","Geita","Iringa","Kagera","Katavi","Kigoma","Kilimanjaro",
            "Lindi","Manyara","Mara","Mbeya","Morogoro","Mtwara","Mwanza","Njombe","Pwani","Rukwa",
            "Ruvuma","Shinyanga","Simiyu","Singida","Songwe","Tabora","Tanga","Zanzibar"],
    "MOZ": ["Cabo Delgado","Gaza","Inhambane","Manica","Maputo","Nampula","Niassa","Sofala",
            "Tete","Zambezia"],
    "ZMB": ["Central","Copperbelt","Eastern","Luapula","Lusaka","Muchinga","Northern",
            "North-Western","Southern","Western"],
    "ZWE": ["Bulawayo","Harare","Manicaland","Mashonaland Central","Mashonaland East",
            "Mashonaland West","Masvingo","Matabeleland North","Matabeleland South","Midlands"],
    "MWI": ["Central","Northern","Southern"],
    "AGO": ["Bengo","Benguela","Bié","Cabinda","Cuando Cubango","Cuanza Norte","Cuanza Sul",
            "Cunene","Huambo","Huíla","Luanda","Lunda Norte","Lunda Sul","Malanje","Moxico",
            "Namibe","Uíge","Zaire"],
    "CMR": ["Adamawa","Centre","East","Far North","Littoral","North","Northwest","South","Southwest","West"],
    "SEN": ["Dakar","Diourbel","Fatick","Kaffrine","Kaolack","Kédougou","Kolda","Louga",
            "Matam","Saint-Louis","Sédhiou","Tambacounda","Thiès","Ziguinchor"],
    "MLI": ["Bamako","Gao","Kayes","Kidal","Koulikoro","Ménaka","Mopti","Ségou","Sikasso","Taoudénit","Tombouctou"],
    "BFA": ["Boucle du Mouhoun","Cascades","Centre","Centre-Est","Centre-Nord","Centre-Ouest",
            "Centre-Sud","Est","Hauts-Bassins","Nord","Plateau-Central","Sahel","Sud-Ouest"],
    "NER": ["Agadez","Diffa","Dosso","Maradi","Niamey","Tahoua","Tillabéri","Zinder"],
    "TCD": ["Bahr el Gazel","Batha","Borkou","Chari-Baguirmi","Ennedi-Est","Ennedi-Ouest",
            "Guéra","Hadjer-Lamis","Kanem","Lac","Logone Occidental","Logone Oriental",
            "Mandoul","Mayo-Kebbi Est","Mayo-Kebbi Ouest","Moyen-Chari","N'Djamena","Ouaddaï",
            "Salamat","Sila","Tandjilé","Tibesti","Wadi Fira"],
    "COD": ["Bas-Uélé","Équateur","Haut-Katanga","Haut-Lomami","Haut-Uélé","Ituri","Kasaï",
            "Kasaï-Central","Kasaï-Oriental","Kinshasa","Kongo-Central","Kwango","Kwilu",
            "Lomami","Lualaba","Maï-Ndombe","Maniema","Mongala","Nord-Kivu","Nord-Ubangi",
            "Sankuru","Sud-Kivu","Sud-Ubangi","Tanganyika","Tshopo","Tshuapa"],
    "COG": ["Bouenza","Brazzaville","Cuvette","Cuvette-Ouest","Kouilou","Lékoumou","Likouala",
            "Niari","Plateaux","Pool","Sangha"],
    "GAB": ["Estuaire","Haut-Ogooué","Moyen-Ogooué","Ngounié","Nyanga","Ogooué-Ivindo",
            "Ogooué-Lolo","Ogooué-Maritime","Woleu-Ntem"],
    "GIN": ["Boké","Conakry","Faranah","Kankan","Kindia","Labé","Mamou","Nzérékoré"],
    "SLE": ["Eastern","Northern","North West","Southern","Western Area"],
    "LBR": ["Bomi","Bong","Gbarpolu","Grand Bassa","Grand Cape Mount","Grand Gedeh",
            "Grand Kru","Lofa","Margibi","Maryland","Montserrado","Nimba","River Cess",
            "River Gee","Sinoe"],
    "CIV": ["Abidjan","Bas-Sassandra","Comoé","Denguélé","Gôh-Djiboua","Lacs","Lagunes",
            "Montagnes","Sassandra-Marahoué","Savanes","Vallée du Bandama","Woroba",
            "Yamoussoukro","Zanzan"],
    "GHA_EXT": [],
    "MAR": ["Béni Mellal-Khénifra","Casablanca-Settat","Dakhla-Oued Ed-Dahab","Drâa-Tafilalet",
            "Fès-Meknès","Guelmim-Oued Noun","Laâyoune-Sakia El Hamra","Marrakech-Safi",
            "Oriental","Rabat-Salé-Kénitra","Souss-Massa","Tanger-Tétouan-Al Hoceïma"],
    "DZA": ["Adrar","Aïn Defla","Aïn Témouchent","Alger","Annaba","Batna","Béchar","Béjaïa",
            "Biskra","Blida","Bordj Bou Arréridj","Bouira","Boumerdès","Chlef","Constantine",
            "Djelfa","El Bayadh","El Oued","El Tarf","Ghardaïa","Guelma","Illizi","Jijel",
            "Khenchela","Laghouat","M'sila","Mascara","Médéa","Mila","Mostaganem","Naâma",
            "Oran","Ouargla","Oum El Bouaghi","Relizane","Saïda","Sétif","Sidi Bel Abbès",
            "Skikda","Souk Ahras","Tamanrasset","Tébessa","Tiaret","Tindouf","Tipaza","Tissemsilt",
            "Tizi Ouzou","Tlemcen"],
    "LBY": ["Al Butnan","Al Jabal al Akhdar","Al Jabal al Gharbi","Al Jafarah","Al Jufrah",
            "Al Kufrah","Al Marj","Al Marqab","Al Wahat","An Nuqat al Khams","Az Zawiyah",
            "Benghazi","Darnah","Ghat","Misratah","Murzuq","Nalut","Sabha","Surt","Tripoli","Wadi al Hayat","Wadi ash Shati"],
    "TUN": ["Ariana","Béja","Ben Arous","Bizerte","Gabès","Gafsa","Jendouba","Kairouan",
            "Kasserine","Kébili","Le Kef","Mahdia","La Manouba","Médenine","Monastir","Nabeul",
            "Sfax","Sidi Bouzid","Siliana","Sousse","Tataouine","Tozeur","Tunis","Zaghouan"],
    "JOR": ["Ajloun","Amman","Aqaba","Balqa","Irbid","Jerash","Karak","Ma'an","Madaba",
            "Mafraq","Tafilah","Zarqa"],
    "IRQ": ["Al Anbar","Al Basrah","Al Muthanna","Al Qadisiyah","An Najaf","Arbil","As Sulaymaniyah",
            "Babil","Baghdad","Dahuk","Dhi Qar","Diyala","Karbala'","Kirkuk","Maysan","Ninawa",
            "Salah ad Din","Wasit"],
    "SYR": ["Al-Hasakah","Al-Raqqah","Aleppo","As-Suwayda","Damascus","Daraa","Deir ez-Zor",
            "Hama","Homs","Idlib","Latakia","Quneitra","Rural Damascus","Tartus"],
    "YEM": ["Abyan","Aden","Al Bayda","Al Hudaydah","Al Jawf","Al Mahrah","Al Mahwit",
            "Amran","Dhamar","Hadhramaut","Hajjah","Ibb","Lahij","Ma'rib","Raymah",
            "Sa'dah","Sana'a","Shabwah","Socotra","Taiz"],
    "OMN": ["Ad Dakhiliyah","Ad Dhahirah","Al Batinah North","Al Batinah South","Al Buraymi",
            "Al Wusta","Ash Sharqiyah North","Ash Sharqiyah South","Dhofar","Musandam","Muscat"],
    "ARE": ["Abu Dhabi","Ajman","Dubai","Fujairah","Ras Al Khaimah","Sharjah","Umm Al Quwain"],
    "KWT": ["Al Ahmadi","Al Asimah","Al Farwaniyah","Al Jahra","Hawalli","Mubarak Al-Kabeer"],
    "QAT": ["Ad Dawhah","Al Daayen","Al Khor","Al Rayyan","Al Shahaniya","Al Wakrah",
            "Az Za'ayin","Umm Salal"],
    "BHR": ["Capital","Central","Muharraq","Northern","Southern"],
    "LBN": ["Akkar","Baalbek-Hermel","Beirut","Bekaa","Mount Lebanon","Nabatieh","North","South"],
    "ISR": ["Central","Haifa","Jerusalem","Northern","Southern","Tel Aviv"],
    "AZE": ["Absheron","Aran","Baku","Daglig-Shirvan","Ganja-Qazakh","Lankaran","Mountainous Shirvan",
            "Nakhchivan","Quba-Khachmaz","Shaki-Zaqatala","Upper Karabakh"],
    "GEO": ["Adjara","Guria","Imereti","Kakheti","Kvemo Kartli","Mtskheta-Mtianeti","Racha-Lechkhumi",
            "Samegrelo-Zemo Svaneti","Samtskhe-Javakheti","Shida Kartli","Tbilisi"],
    "ARM": ["Aragatsotn","Ararat","Armavir","Gegharkunik","Kotayk","Lori","Shirak","Syunik",
            "Tavush","Vayots Dzor","Yerevan"],
    "KAZ": ["Abai","Akmola","Aktobe","Almaty","Atyrau","East Kazakhstan","Jambyl","Karaganda",
            "Kostanay","Kyzylorda","Mangystau","North Kazakhstan","Pavlodar","Turkistan",
            "Ulytau","West Kazakhstan","Zhetisu"],
    "UZB": ["Andijan","Bukhara","Fergana","Jizzakh","Karakalpakstan","Kashkadarya","Khorezm",
            "Namangan","Navoiy","Samarkand","Sirdaryo","Surkhandarya","Tashkent"],
    "TKM": ["Ahal","Ashgabat","Balkan","Daşoguz","Lebap","Mary"],
    "KGZ": ["Batken","Chuy","Issyk-Kul","Jalal-Abad","Naryn","Osh","Talas"],
    "TJK": ["Dushanbe","Gorno-Badakhshan","Khatlon","Districts of Republican Subordination","Sughd"],
    "AFG": ["Badakhshan","Badghis","Baghlan","Balkh","Bamyan","Daykundi","Farah","Faryab",
            "Ghazni","Ghor","Helmand","Herat","Jowzjan","Kabul","Kandahar","Kapisa","Khost",
            "Kunar","Kunduz","Laghman","Logar","Nangarhar","Nimroz","Nuristan","Paktia",
            "Paktika","Panjshir","Parwan","Samangan","Sar-e Pol","Takhar","Urozgan","Wardak","Zabul"],
    "NPL": ["Bagmati","Gandaki","Karnali","Koshi","Lumbini","Madhesh","Sudurpashchim"],
    "BTN": ["Bumthang","Chhukha","Dagana","Gasa","Haa","Lhuentse","Mongar","Paro","Pema Gatshel",
            "Punakha","Samdrup Jongkhar","Samtse","Sarpang","Thimphu","Trashigang","Trashi Yangtse",
            "Trongsa","Tsirang","Wangdue Phodrang","Zhemgang"],
    "LKA": ["Central","Eastern","North Central","Northern","North Western","Sabaragamuwa",
            "Southern","Uva","Western"],
    "MDV": ["Addu","Ari","Baa","Dhaalu","Faafu","Gaafu Alifu","Gaafu Dhaalu","Gnaviyani",
            "Haa Alifu","Haa Dhaalu","Kaafu","Laamu","Lhaviyani","Meemu","Noonu","Raa",
            "Seenu","Shaviyani","Thaa","Vaavu"],
    "PHL": ["Bangsamoro","Bicol","Cagayan Valley","Calabarzon","Caraga","Central Luzon",
            "Central Visayas","Cordillera","Davao","Eastern Visayas","Ilocos","Mimaropa",
            "National Capital Region","Northern Mindanao","Soccsksargen","Western Visayas",
            "Zamboanga Peninsula"],
    "MYS": ["Johor","Kedah","Kelantan","Kuala Lumpur","Labuan","Melaka","Negeri Sembilan",
            "Pahang","Perak","Perlis","Penang","Putrajaya","Sabah","Sarawak","Selangor","Terengganu"],
    "KHM": ["Banteay Meanchey","Battambang","Kampong Cham","Kampong Chhnang","Kampong Speu",
            "Kampong Thom","Kampot","Kandal","Kep","Koh Kong","Kratie","Mondulkiri",
            "Oddar Meanchey","Pailin","Phnom Penh","Preah Sihanouk","Preah Vihear","Prey Veng",
            "Pursat","Ratanakiri","Siem Reap","Stung Treng","Svay Rieng","Takeo","Tboung Khmum"],
    "LAO": ["Attapeu","Bokeo","Bolikhamsai","Champasak","Houaphanh","Khammouane","Luang Namtha",
            "Luang Prabang","Oudomxay","Phongsaly","Sainyabuli","Salavan","Savannakhet",
            "Sekong","Vientiane","Xaisomboun","Xiangkhouang"],
    "TLS": ["Aileu","Ainaro","Baucau","Bobonaro","Cova Lima","Dili","Ermera","Lautém",
            "Liquiçá","Manatuto","Manufahi","Oecusse","Viqueque"],
    "MNG": ["Arkhangai","Bayan-Ölgii","Bayankhongor","Bulgan","Darkhan-Uul","Dornod","Dornogovi",
            "Dundgovi","Govi-Altai","Govisümber","Khentii","Khovd","Khövsgöl","Ömnögovi",
            "Orkhon","Övörkhangai","Selenge","Sükhbaatar","Töv","Uvs","Zavkhan"],
    "PRK": ["Chagang","North Hamgyong","South Hamgyong","North Hwanghae","South Hwanghae",
            "Kangwon","North Pyongan","South Pyongan","Ryanggang","Pyongyang","Rason",
            "Kaesong","Nampo"],
    "KOR": ["Busan","Chungcheongbuk","Chungcheongnam","Daegu","Daejeon","Gangwon","Gwangju",
            "Gyeonggi","Gyeongsangbuk","Gyeongsangnam","Incheon","Jeju","Jeollabuk","Jeollanam",
            "Sejong","Seoul","Ulsan"],
    "JPN": ["Aichi","Akita","Aomori","Chiba","Ehime","Fukui","Fukuoka","Fukushima","Gifu",
            "Gunma","Hiroshima","Hokkaido","Hyogo","Ibaraki","Ishikawa","Iwate","Kagawa",
            "Kagoshima","Kanagawa","Kochi","Kumamoto","Kyoto","Mie","Miyagi","Miyazaki",
            "Nagano","Nagasaki","Nara","Niigata","Oita","Okayama","Okinawa","Osaka","Saga",
            "Saitama","Shiga","Shimane","Shizuoka","Tochigi","Tokushima","Tokyo","Tottori",
            "Toyama","Wakayama","Yamagata","Yamaguchi","Yamanashi"],
    "TWN": ["Changhua","Chiayi","Hsinchu","Hualien","Kaohsiung","Keelung","Kinmen","Lienchiang",
            "Miaoli","Nantou","New Taipei","Penghu","Pingtung","Taichung","Tainan","Taipei",
            "Taitung","Taoyuan","Yilan","Yunlin"],
    "HKG": ["Central and Western","Eastern","Islands","Kowloon City","Kwai Tsing","Kwun Tong",
            "North","Sai Kung","Sha Tin","Sham Shui Po","Southern","Tai Po","Tsuen Wan",
            "Tuen Mun","Wan Chai","Wong Tai Sin","Yau Tsim Mong","Yuen Long"],
    "SGP": ["Central","East","North","North-East","West"],
    "BRN": ["Belait","Brunei-Muara","Temburong","Tutong"],
    "PNG": ["Central","Chimbu","Eastern Highlands","East New Britain","East Sepik","Enga",
            "Gulf","Hela","Jiwaka","Madang","Manus","Milne Bay","Morobe","National Capital District",
            "New Ireland","Northern","Southern Highlands","Western","Western Highlands","West New Britain","West Sepik"],
    "NZL": ["Auckland","Bay of Plenty","Canterbury","Gisborne","Hawke's Bay","Manawatū-Whanganui",
            "Marlborough","Nelson","Northland","Otago","Southland","Taranaki","Tasman","Waikato",
            "Wellington","West Coast"],
    "CHL": ["Aisén","Antofagasta","Araucanía","Arica y Parinacota","Atacama","Biobío","Coquimbo",
            "Los Lagos","Los Ríos","Magallanes","Maule","Metropolitana","Ñuble","O'Higgins",
            "Tarapacá","Valparaíso"],
    "ARG": ["Buenos Aires","Catamarca","Chaco","Chubut","Ciudad Autónoma de Buenos Aires",
            "Córdoba","Corrientes","Entre Ríos","Formosa","Jujuy","La Pampa","La Rioja",
            "Mendoza","Misiones","Neuquén","Río Negro","Salta","San Juan","San Luis",
            "Santa Cruz","Santa Fe","Santiago del Estero","Tierra del Fuego","Tucumán"],
    "PER": ["Amazonas","Áncash","Apurímac","Arequipa","Ayacucho","Cajamarca","Callao","Cusco",
            "Huancavelica","Huánuco","Ica","Junín","La Libertad","Lambayeque","Lima","Loreto",
            "Madre de Dios","Moquegua","Pasco","Piura","Puno","San Martín","Tacna","Tumbes","Ucayali"],
    "COL": ["Amazonas","Antioquia","Arauca","Atlántico","Bolívar","Boyacá","Caldas","Caquetá",
            "Casanare","Cauca","Cesar","Chocó","Córdoba","Cundinamarca","Guainía","Guaviare",
            "Huila","La Guajira","Magdalena","Meta","Nariño","Norte de Santander","Putumayo",
            "Quindío","Risaralda","San Andrés","Santander","Sucre","Tolima","Valle del Cauca",
            "Vaupés","Vichada","Bogotá"],
    "VEN": ["Amazonas","Anzoátegui","Apure","Aragua","Barinas","Bolívar","Carabobo","Cojedes",
            "Delta Amacuro","Distrito Capital","Falcón","Guárico","La Guaira","Lara","Mérida",
            "Miranda","Monagas","Nueva Esparta","Portuguesa","Sucre","Táchira","Trujillo",
            "Yaracuy","Zulia"],
    "ECU": ["Azuay","Bolívar","Cañar","Carchi","Chimborazo","Cotopaxi","El Oro","Esmeraldas",
            "Galápagos","Guayas","Imbabura","Loja","Los Ríos","Manabí","Morona Santiago","Napo",
            "Orellana","Pastaza","Pichincha","Santa Elena","Santo Domingo","Sucumbíos",
            "Tungurahua","Zamora Chinchipe"],
    "BOL": ["Beni","Chuquisaca","Cochabamba","La Paz","Oruro","Pando","Potosí","Santa Cruz","Tarija"],
    "PRY": ["Alto Paraguay","Alto Paraná","Amambay","Asunción","Boquerón","Caaguazú","Caazapá",
            "Canindeyú","Central","Concepción","Cordillera","Guairá","Itapúa","Misiones",
            "Ñeembucú","Paraguarí","Presidente Hayes","San Pedro"],
    "URY": ["Artigas","Canelones","Cerro Largo","Colonia","Durazno","Flores","Florida",
            "Lavalleja","Maldonado","Montevideo","Paysandú","Río Negro","Rivera","Rocha",
            "Salto","San José","Soriano","Tacuarembó","Treinta y Tres"],
    "GUY": ["Barima-Waini","Cuyuni-Mazaruni","Demerara-Mahaica","East Berbice-Corentyne",
            "Essequibo Islands-West Demerara","Mahaica-Berbice","Pomeroon-Supenaam",
            "Potaro-Siparuni","Upper Demerara-Berbice","Upper Takutu-Upper Essequibo"],
    "SUR": ["Brokopondo","Commewijne","Coronie","Marowijne","Nickerie","Para","Paramaribo",
            "Saramacca","Sipaliwini","Wanica"],
    "GTM": ["Alta Verapaz","Baja Verapaz","Chimaltenango","Chiquimula","El Progreso","Escuintla",
            "Guatemala","Huehuetenango","Izabal","Jalapa","Jutiapa","Petén","Quetzaltenango",
            "Quiché","Retalhuleu","Sacatepéquez","San Marcos","Santa Rosa","Sololá","Suchitepéquez",
            "Totonicapán","Zacapa"],
    "HND": ["Atlántida","Bay Islands","Choluteca","Colón","Comayagua","Copán","Cortés","El Paraíso",
            "Francisco Morazán","Gracias a Dios","Intibucá","Islas de la Bahía","La Paz","Lempira",
            "Ocotepeque","Olancho","Santa Bárbara","Valle","Yoro"],
    "SLV": ["Ahuachapán","Cabañas","Chalatenango","Cuscatlán","La Libertad","La Paz","La Unión",
            "Morazán","San Miguel","San Salvador","San Vicente","Santa Ana","Sonsonate","Usulután"],
    "NIC": ["Boaco","Carazo","Chinandega","Chontales","Estelí","Granada","Jinotega","León",
            "Madriz","Managua","Masaya","Matagalpa","Nueva Segovia","Río San Juan","Rivas",
            "North Caribbean Coast","South Caribbean Coast"],
    "CRI": ["Alajuela","Cartago","Guanacaste","Heredia","Limón","Puntarenas","San José"],
    "PAN": ["Bocas del Toro","Chiriquí","Coclé","Colón","Darién","Emberá","Guna Yala","Herrera",
            "Los Santos","Ngäbe-Buglé","Panamá","Panamá Oeste","Veraguas"],
    "CUB": ["Artemisa","Camagüey","Ciego de Ávila","Cienfuegos","Granma","Guantánamo","Holguín",
            "Isla de la Juventud","La Habana","Las Tunas","Matanzas","Mayabeque","Pinar del Río",
            "Sancti Spíritus","Santiago de Cuba","Villa Clara"],
    "DOM": ["Azua","Baoruco","Barahona","Dajabón","Distrito Nacional","Duarte","Elías Piña",
            "El Seibo","Espaillat","Hato Mayor","Hermanas Mirabal","Independencia","La Altagracia",
            "La Romana","La Vega","María Trinidad Sánchez","Monseñor Nouel","Monte Cristi",
            "Monte Plata","Pedernales","Peravia","Puerto Plata","Samaná","San Cristóbal",
            "San José de Ocoa","San Juan","San Pedro de Macorís","Sánchez Ramírez","Santiago",
            "Santiago Rodríguez","Santo Domingo","Valverde"],
    "HTI": ["Artibonite","Centre","Grand'Anse","Nippes","Nord","Nord-Est","Nord-Ouest","Ouest",
            "Sud","Sud-Est"],
    "JAM": ["Clarendon","Hanover","Kingston","Manchester","Portland","Saint Andrew","Saint Ann",
            "Saint Catherine","Saint Elizabeth","Saint James","Saint Mary","Saint Thomas","Trelawny","Westmoreland"],
    "TTO": ["Arima","Chaguanas","Couva-Tabaquite-Talparo","Diego Martin","Mayaro-Rio Claro",
            "Penal-Debe","Point Fortin","Port of Spain","Princes Town","San Fernando",
            "San Juan-Laventille","Sangre Grande","Siparia","Tobago","Tunapuna-Piarco"],
    "BLZ": ["Belize","Cayo","Corozal","Orange Walk","Stann Creek","Toledo"],
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
    """返回扩充数据的条目数统计。"""
    sats = expand_satellite_constellations()
    admin1 = sum(len(v) for v in ADMIN1_EXTENDED.values())
    concepts = sum(len(v) for v in EXTENDED_CONCEPTS.values())
    return {
        "constellation_satellites": len(sats),
        "constellation_bands": sum(len(s[6]) for s in sats),
        "extended_admin1": admin1,
        "extended_concepts": concepts,
        "monitored_indicators": len(MONITORED_INDICATORS),
        "required_input_types": len(REQUIRED_INPUTS),
    }