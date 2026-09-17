#!/usr/bin/env python
"""构建 L3 地球系统本体：土地覆盖 / 气候 / 灾害。

## 与 fetch_*.py 的区别（重要）

``fetch_un_m49.py`` 与 ``fetch_geonames_admin1.py`` 是**下载**机器可读数据；
本脚本是**transcribe（转录）**：三个分类体系都只以论文/技术报告形式发布，
没有官方机器可读清单。因此**本脚本就是转录的权威记录**——校验方式是把它与
下面引用的原始文献逐条比对，而不是重跑脚本比对哈希。

每个分类都标注了 ``source_id``、级别与父级，供图谱建立层级关系。

## 三个来源

1. **土地覆盖** — ESA WorldCover（11 类，CC BY 4.0）
   产品文档: https://docs.planet.com/data/public-data/other-datasets/esa-worldcover/
   分类遵循 FAO LCCS 方案。类别编号即产品栅格值。

2. **气候** — Köppen-Geiger（Beck et al. 2018, *Scientific Data*, CC BY 4.0）
   https://doi.org/10.1038/sdata.2018.214
   30 个气候型 + 5 个主群；代码与描述取自该文 Table 1。

3. **灾害** — IRDR Peril Classification（IRDR DATA Publication No. 1, 2014）
   https://www.irdrinternational.org/pdf/uploads/files/sc11/IRDR_DATA-Project-Report-No.-1.pdf
   三级：6 个 family / 20 个 main event / 47 个 peril。

   ⚠️ 该文献明确指出 peril 与 main event **不是一对一关系**
   （"there is not an exclusive one-to-one relationship"），
   因此本脚本**不为 peril 强行指定 main event 父级**——那会是我们编造的关系。

用法::

    python scripts/build_l3_ontology.py [--check]
"""

from __future__ import annotations

import argparse
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "src" / "geokg" / "data"

# --------------------------------------------------------------------------- #
# 1. 土地覆盖 —— ESA WorldCover（FAO LCCS 方案）
# --------------------------------------------------------------------------- #
LANDCOVER_SOURCE = "esa-worldcover"
LANDCOVER_ATTR = ("© ESA WorldCover project / Contains modified Copernicus Sentinel "
                  "data (2020/2021) processed by ESA WorldCover consortium")
LANDCOVER: list[tuple[str, str, str]] = [
    # (值, 名称, 说明)
    ("10", "Tree cover", "任何高于 5 m 的木本植被；对应 LCCS 的树木覆盖"),
    ("20", "Shrubland", "低于 5 m 的木本植被"),
    ("30", "Grassland", "草本植物为主，无乔木灌木覆盖"),
    ("40", "Cropland", "耕地（含一年生作物与水田）"),
    ("50", "Built-up", "人工建成地表（建筑、道路等）"),
    ("60", "Bare / sparse vegetation", "裸地或植被稀疏的沙、砾、岩"),
    ("70", "Snow and ice", "常年冰雪覆盖"),
    ("80", "Permanent water bodies", "内陆与沿海永久水体"),
    ("90", "Herbaceous wetland", "草本湿地"),
    ("95", "Mangroves", "红树林"),
    ("100", "Moss and lichen", "苔藓与地衣"),
]

# --------------------------------------------------------------------------- #
# 2. 气候 —— Köppen-Geiger（Beck et al. 2018）
# --------------------------------------------------------------------------- #
CLIMATE_SOURCE = "koppen-geiger-beck2018"
CLIMATE_GROUPS: list[tuple[str, str, str]] = [
    ("A", "Tropical", "最冷月平均气温 ≥ 18 °C"),
    ("B", "Arid", "降水量不足以维持植被"),
    ("C", "Temperate", "最热月 > 10 °C 且最冷月 0–18 °C"),
    ("D", "Cold", "最热月 > 10 °C 且最冷月 < 0 °C"),
    ("E", "Polar", "最热月 < 10 °C"),
]
#: (代码, 主群, 描述) —— 转录自 Beck et al. 2018 Table 1，顺序与原表一致
CLIMATE: list[tuple[str, str, str]] = [
    ("Af", "A", "热带，雨林"),
    ("Am", "A", "热带，季风"),
    ("Aw", "A", "热带，草原（冬干）"),
    ("BWh", "B", "干旱，沙漠，炎热"),
    ("BWk", "B", "干旱，沙漠，寒冷"),
    ("BSh", "B", "干旱，草原，炎热"),
    ("BSk", "B", "干旱，草原，寒冷"),
    ("Csa", "C", "温带，夏干，热夏"),
    ("Csb", "C", "温带，夏干，暖夏"),
    ("Csc", "C", "温带，夏干，冷夏"),
    ("Cwa", "C", "温带，冬干，热夏"),
    ("Cwb", "C", "温带，冬干，暖夏"),
    ("Cwc", "C", "温带，冬干，冷夏"),
    ("Cfa", "C", "温带，无干季，热夏"),
    ("Cfb", "C", "温带，无干季，暖夏"),
    ("Cfc", "C", "温带，无干季，冷夏"),
    ("Dsa", "D", "冷，夏干，热夏"),
    ("Dsb", "D", "冷，夏干，暖夏"),
    ("Dsc", "D", "冷，夏干，冷夏"),
    ("Dsd", "D", "冷，夏干，寒冬"),
    ("Dwa", "D", "冷，冬干，热夏"),
    ("Dwb", "D", "冷，冬干，暖夏"),
    ("Dwc", "D", "冷，冬干，冷夏"),
    ("Dwd", "D", "冷，冬干，寒冬"),
    ("Dfa", "D", "冷，无干季，热夏"),
    ("Dfb", "D", "冷，无干季，暖夏"),
    ("Dfc", "D", "冷，无干季，冷夏"),
    ("Dfd", "D", "冷，无干季，寒冬"),
    ("ET", "E", "极地，苔原"),
    ("EF", "E", "极地，冰霜"),
]

# --------------------------------------------------------------------------- #
# 3. 灾害 —— IRDR Peril Classification (2014)
# --------------------------------------------------------------------------- #
HAZARD_SOURCE = "irdr-peril-classification-2014"
HAZARD_FAMILIES: list[tuple[str, str, str]] = [
    ("Geophysical", "固体地球起源的灾害（同 geological hazard）"),
    ("Hydrological", "由地表与地下淡水/咸水的出现、运动与分布引起"),
    ("Meteorological", "短历时、微到中尺度的极端天气与大气条件（分钟至天）"),
    ("Climatological", "长历时、中到大尺度大气过程（季节内至多年代际气候变率）"),
    ("Biological", "暴露于生物体、其毒性物质或媒介传播疾病"),
    ("Extraterrestrial", "小行星、流星体、彗星，或行星际条件变化对地球磁层/电离层/热层的影响"),
]
HAZARD_MAIN_EVENTS: list[tuple[str, str]] = [
    ("Earthquake", "Geophysical"),
    ("Mass Movement", "Geophysical"),
    ("Volcanic Activity", "Geophysical"),
    ("Flood", "Hydrological"),
    ("Landslide", "Hydrological"),
    ("Wave Action", "Hydrological"),
    ("Convective Storm", "Meteorological"),
    ("Extratropical Storm", "Meteorological"),
    ("Extreme Temperature", "Meteorological"),
    ("Fog", "Meteorological"),
    ("Tropical Cyclone", "Meteorological"),
    ("Drought", "Climatological"),
    ("Glacial Lake Outburst", "Climatological"),
    ("Wildfire", "Climatological"),
    ("Animal Incident", "Biological"),
    ("Disease", "Biological"),
    ("Insect Infestation", "Biological"),
    ("Impact", "Extraterrestrial"),
    ("Space Weather", "Extraterrestrial"),
    ("Airburst", "Extraterrestrial"),
]
#: IRDR peril 层。**不指定 main event 父级**——原文献说明该关联非一对一，
#: 强行指定等于编造关系。peril 与 family 的对应需按具体事件判定。
HAZARD_PERILS: list[str] = [
    "Airburst", "Ashfall", "Avalanche: Snow, Debris", "Bacterial Disease",
    "Coastal Erosion", "Coastal Flood", "Cold Wave", "Collision",
    "Debris/Mud Flow/Rockfall", "Derecho", "Energetic Particles",
    "Expansive Soil", "Fire following EQ", "Flash Flood", "Forest Fire",
    "Frost/Freeze", "Fungal Disease", "Geomagnetic Storm", "Ground Movement",
    "Hail", "Heat Wave", "Ice Jam Flood", "Lahar",
    "Land Fire: Brush, Bush, Pasture", "Landslide following EQ", "Lava Flow",
    "Lightning", "Liquefaction", "Parasitic Disease", "Prion Disease",
    "Pyroclastic Flow", "Radio Disturbance", "Rain", "Riverine Flood",
    "Rogue Wave", "Sandstorm/Dust Storm", "Seiche", "Shockwave", "Sinkhole",
    "Snow/Ice", "Storm Surge", "Subsidence", "Tornado", "Tsunami",
    "Viral Disease", "Wind", "Winter Storm/Blizzard",
]

HEADER = (
    "# {title}\n"
    "# 来源: {url}\n"
    "# 许可: {lic}\n"
    "# 生成: python scripts/build_l3_ontology.py   —— 转录自上述文献，请勿手工编辑\n"
    "# 每行 6 列: source_id\tlevel\ticode\tname\tparent\tdescription\n"
)


def _rows() -> dict[str, str]:
    out: dict[str, str] = {}

    lc = [("source_id", "level", "code", "name", "parent", "description")]
    for code, name, desc in LANDCOVER:
        lc.append((LANDCOVER_SOURCE, "class", code, name, "", desc))
    out["worldcover_landcover.tsv"] = HEADER.format(
        title="ESA WorldCover 土地覆盖分类（遵循 FAO LCCS 方案，11 类）",
        url="https://docs.planet.com/data/public-data/other-datasets/esa-worldcover/",
        lic="Creative Commons Attribution 4.0 (CC BY 4.0)",
    ) + "\n".join("\t".join(r) for r in lc) + "\n"

    cl = [("source_id", "level", "code", "name", "parent", "description")]
    for code, name, desc in CLIMATE_GROUPS:
        cl.append((CLIMATE_SOURCE, "group", code, name, "", desc))
    for code, grp, desc in CLIMATE:
        cl.append((CLIMATE_SOURCE, "class", code, desc, grp, ""))
    out["koppen_geiger_climate.tsv"] = HEADER.format(
        title="Köppen-Geiger 气候分类（Beck et al. 2018, Scientific Data）",
        url="https://doi.org/10.1038/sdata.2018.214",
        lic="Creative Commons Attribution 4.0 (CC BY 4.0)",
    ) + "\n".join("\t".join(r) for r in cl) + "\n"

    hz = [("source_id", "level", "code", "name", "parent", "description")]
    for name, desc in HAZARD_FAMILIES:
        hz.append((HAZARD_SOURCE, "family", name, name, "", desc))
    for name, fam in HAZARD_MAIN_EVENTS:
        hz.append((HAZARD_SOURCE, "main_event", name, name, fam, ""))
    for name in HAZARD_PERILS:
        hz.append((HAZARD_SOURCE, "peril", name, name, "", ""))
    out["irdr_hazards.tsv"] = HEADER.format(
        title="IRDR 灾害分类（Peril Classification and Hazard Glossary, 2014）",
        url="https://www.irdrinternational.org/pdf/uploads/files/sc11/"
            "IRDR_DATA-Project-Report-No.-1.pdf",
        lic="IRDR 公开技术报告（引用 IRDR DATA Publication No. 1）",
    ) + "\n".join("\t".join(r) for r in hz) + "\n"

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    files = _rows()
    rc = 0
    for name, text in files.items():
        n = len([ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]) - 1
        p = OUT_DIR / name
        if args.check:
            ok = p.exists() and p.read_text(encoding="utf-8") == text
            print(f"  {'✅' if ok else '⚠️'} {name:28} {n:>3} 条"
                  f"{'' if ok else '  —— 与磁盘不一致'}")
            rc |= 0 if ok else 1
            continue
        p.write_text(text, encoding="utf-8")
        print(f"  ✅ {name:28} {n:>3} 条  ({p.stat().st_size:,} bytes)")

    total = sum(len([ln for ln in t.splitlines() if ln.strip() and not ln.startswith("#")]) - 1
                for t in files.values())
    print(f"\n  合计 {total} 条 L3 本体条目")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
