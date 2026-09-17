"""GeoKG 参考数据集 — 权威结构化数据，用于知识图谱批量灌数。

数据来源（逐项标注，见 PROVENANCE）：
- SDG 框架：已改由 UN SDG 官方 API 生成（见 geokg.sdg）
- 国家：ISO 3166-1
- 卫星目录：已改由 WMO OSCAR/Space 提供（见 geokg.satellites）
- 概念/术语表：已改为逐条标注来源（见 geokg.vocabulary）

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
# ISO 3166-1 国家与地区（249 条）
# 格式: (ISO3, 英文名, 大区, 次区域)
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
    #: sovereign | SAR | province —— 依据一个中国原则标注归属状态
    admin_status: str = "sovereign"
    #: 归属的 ISO3（空 = 主权实体）。HKG / MAC / TWN 均为 "CHN"。
    part_of: str = ""


def load_countries(path: str | Path | None = None) -> list[Country]:
    """从数据文件加载国家/地区表（制表符分隔，13 列，``#`` 行为注释）。"""
    src = Path(path) if path else COUNTRY_DATA_FILE
    out: list[Country] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) != 13:
            raise ValueError(f"{src.name}: 期望 13 列，实际 {len(f)} 列 -> {line[:60]!r}")
        out.append(Country(
            iso3=f[0], name=f[1], region=f[2], subregion=f[3], intermediate=f[4],
            m49=f[5], iso2=f[6],
            ldc=bool(f[7]), lldc=bool(f[8]), sids=bool(f[9]), development=f[10],
            admin_status=f[11] or "sovereign", part_of=f[12],
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
# 统计汇总
# --------------------------------------------------------------------------- #
def reference_data_stats() -> dict[str, int]:
    from .sdg import sdg_stats
    from .vocabulary import vocabulary_stats

    """返回各参考数据集的条目数。"""
    return {
        "sdg_goals": sdg_stats()["goals"],
        "sdg_targets": sdg_stats()["targets"],
        "sdg_indicators": sdg_stats()["indicators"],
        "geospatial_indicators": len(GEOSPATIAL_INDICATORS),
        "countries": len(COUNTRIES),
        "concepts": vocabulary_stats()["terms_total"],
    }